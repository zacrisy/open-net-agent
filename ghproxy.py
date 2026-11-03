# -*- coding: utf-8 -*-
"""稳定 GitHub 连接：本地 CONNECT 代理，多 IP 探测 + 故障切换，绕过 DNS。

按域名分别选路：主站、api、codeload 各走自己的 GitHub IP 段；
raw / objects / avatars / camo 走 Fastly；assets 走静态资源 CDN。
非 GitHub 域名原样直连，不影响其他站点。
"""
import select, socket, ssl, threading, time

GITHUB_IPS = ["140.82.112.3", "140.82.116.3", "140.82.114.3",
              "140.82.113.3", "20.205.243.166", "20.27.177.113"]
API_IPS = ["140.82.112.6", "140.82.113.6", "140.82.114.6", "20.205.243.168"]
CODELOAD_IPS = ["140.82.113.9", "140.82.112.9", "20.205.243.165", "140.82.114.9"]
FASTLY_IPS = ["185.199.108.133", "185.199.109.133",
              "185.199.110.133", "185.199.111.133"]
ASSET_IPS = ["185.199.%d.215" % i for i in range(108, 112)]

# 各域名必须用自己的 IP 段：主站 .3、api .6、codeload .9。
# 混用会被边缘节点重定向到主站，下载链路会变成 404。
MAP_HOSTS = {
    "github.com": GITHUB_IPS,
    "www.github.com": GITHUB_IPS,
    "api.github.com": API_IPS,
    "codeload.github.com": CODELOAD_IPS,
    "raw.githubusercontent.com": FASTLY_IPS,
    "objects.githubusercontent.com": FASTLY_IPS,
    "avatars.githubusercontent.com": FASTLY_IPS,
    "user-images.githubusercontent.com": FASTLY_IPS,
    "camo.githubusercontent.com": FASTLY_IPS,
    "github.githubassets.com": ASSET_IPS,
}

PORT = 8899
TTL = 120                      # 选中 IP 的缓存时间（秒）
_lock = threading.Lock()
_cached = {}                   # host -> (ip, ts)
_cooldown = {}                 # host -> 失败冷却截止时间
COOLDOWN = 20                  # 全候选失败后的冷却秒数：既避免反复重试，又能较快自动恢复


_ssl_ctx = ssl.create_default_context()


def probe(ip, timeout=1.2):
    """TCP 层粗筛：快速排除完全不通的 IP。"""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, 443))
        return True
    except Exception:
        return False
    finally:
        s.close()


def http_alive(host, ip, timeout=3):
    """TLS 层校验：必须真的返回 HTTP 状态行。

    仅 TCP 可连并不可靠——被干扰的 IP 常常握手成功却永远不返回响应，
    只看 TCP 会选中这种「假活」地址。
    """
    raw = tls = None
    try:
        raw = socket.create_connection((ip, 443), timeout=timeout)
        tls = _ssl_ctx.wrap_socket(raw, server_hostname=host)
        tls.settimeout(timeout)
        tls.sendall(("HEAD / HTTP/1.0\r\nHost: %s\r\nUser-Agent: ghproxy\r\n\r\n" % host).encode())
        return tls.recv(32).startswith(b"HTTP/")
    except Exception:
        return False
    finally:
        for x in (tls, raw):
            try:
                if x:
                    x.close()
            except Exception:
                pass


def best_ip(host, force=False, exclude=None):
    """为该域名挑一个当前可连的 IP；无候选则返回 None（回退系统 DNS）。

    全候选失败后进入冷却期直接返回 None，让上层立刻失败，
    而不是让浏览器卡在长达几十秒的重试上。
    """
    ips = MAP_HOSTS.get(host)
    if not ips:
        return None
    now = time.time()
    with _lock:
        ip, ts = _cached.get(host, (None, 0.0))
        cooling = _cooldown.get(host, 0.0) > now
    if ip and not force and now - ts < TTL and ip != exclude:
        return ip
    if cooling and not force:
        return None

    deadline = now + 6          # 探测总预算，防止单个请求长时间挂起
    for cand in ips:
        if cand == exclude:
            continue
        if time.time() > deadline:
            break
        if probe(cand, 1.0) and http_alive(host, cand, 2.5):
            with _lock:
                _cached[host] = (cand, time.time())
                _cooldown.pop(host, None)
            return cand
    with _lock:
        _cooldown[host] = time.time() + COOLDOWN
    return None


def pipe(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 30)
            if not r:
                continue
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.close()
            except Exception:
                pass


def connect_upstream(host, port):
    """按域名选路建立上游连接。

    已映射的域名（GitHub 系）只走探测出的 IP：探测不到就立刻失败，
    不再回退系统 DNS——那只会连到同一个被封地址白等一次超时。
    其他域名一律直连，不受影响。
    """
    if port == 443 and host in MAP_HOSTS:
        ip = best_ip(host)
        if not ip:
            raise OSError("no reachable IP for %s" % host)
        try:
            return socket.create_connection((ip, port), timeout=8)
        except Exception:
            alt = best_ip(host, force=True, exclude=ip)
            if not alt:
                raise
            return socket.create_connection((alt, port), timeout=8)
    return socket.create_connection((host, port), timeout=10)


def handle(c):
    try:
        data = c.recv(8192)
        if not data:
            c.close()
            return
        line = data.split(b"\r\n")[0].decode(errors="ignore")

        # HTTPS：CONNECT 隧道
        if line.startswith("CONNECT"):
            host, port = line.split()[1].split(":")
            up = connect_upstream(host, int(port))
            c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            pipe(c, up)
            return

        # 明文 HTTP 代理请求：GET http://host/path HTTP/1.1
        parts = line.split()
        if len(parts) < 3 or not parts[1].lower().startswith("http://"):
            c.close()
            return
        rest = parts[1][7:]
        if "/" in rest:
            hostport, path = rest.split("/", 1)
            path = "/" + path
        else:
            hostport, path = rest, "/"
        host, _, p = hostport.partition(":")
        port = int(p) if p.isdigit() else 80

        up = connect_upstream(host, port)
        # 把 absolute-URI 改写成 origin-form 再转发
        head = ("%s %s %s" % (parts[0], path, parts[2])).encode()
        up.sendall(head + data[data.index(b"\r\n"):])
        pipe(c, up)
    except Exception:
        try:
            c.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
        try:
            c.close()
        except Exception:
            pass


def main():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PORT))
    s.listen(80)
    print("ghproxy 127.0.0.1:%d hosts=%d" % (PORT, len(MAP_HOSTS)), flush=True)
    while True:
        c, _ = s.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
