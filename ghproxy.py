# -*- coding: utf-8 -*-
"""稳定 GitHub 连接：本地 CONNECT / HTTP 代理。

设计前提：该网络对 GitHub 的 443 出口是「成阵抖动」的——同一时刻不同 IP 有的通、
有的不通，状态几分钟就换一轮。因此这里不缓存单一 IP，而是后台持续探测，
维护一份「当前时刻可用 IP 集合」，新连接从集合里挑；
集合为空时现场快检一次，仍失败则立刻返回 502，绝不让浏览器干等几十秒。

GitHub 各域名必须用自己的 IP 段（主站 .3 / api .6 / codeload .9），
混用会被边缘节点重定向到主站，下载链路会变成 404。
非 GitHub 域名原样直连，不受任何影响。
"""
import concurrent.futures as cf
import select, socket, ssl, threading, time

GITHUB_IPS = ["140.82.112.3", "140.82.113.3", "140.82.114.3", "140.82.116.3",
              "140.82.121.3", "20.205.243.166", "20.27.177.113", "20.200.245.247"]
API_IPS = ["140.82.112.6", "140.82.113.6", "140.82.114.6", "20.205.243.168"]
CODELOAD_IPS = ["140.82.113.9", "140.82.112.9", "20.205.243.165", "140.82.114.9"]
FASTLY_IPS = ["185.199.108.133", "185.199.109.133",
              "185.199.110.133", "185.199.111.133"]
ASSET_IPS = ["185.199.%d.215" % i for i in range(108, 112)]

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
HEALTH_INTERVAL = 8.0      # 后台健康探测周期（秒）
HEALTH_TIMEOUT = 2.5       # 单次 TCP / TLS 校验超时
CONNECT_TIMEOUT = 4.0      # 建立上游连接超时
ONDEMAND_THROTTLE = 5.0    # 现场快环节流间隔，避免请求把探测打爆
MAX_TRY = 4                # 每次连接最多依次尝试几个可用 IP
IDLE_TIMEOUT = 75.0        # 隧道空闲超时：避免封锁期建立的死连接长期堆积、被浏览器反复复用

_ssl_ctx = ssl.create_default_context()
_lock = threading.Lock()
_health = {}               # host -> [当前可用 ip, ...]
_preferred = {}            # host -> 上次成功的 ip
_last_ondemand = {}        # host -> 上次现场快检时间
_next_check = {}           # host -> 下次健康探测时间
_backoff = {}              # host -> 当前退避间隔


def probe(ip, timeout=1.2):
    """TCP 层粗筛。"""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, 443))
        return True
    except Exception:
        return False
    finally:
        s.close()


def http_alive(host, ip, timeout=HEALTH_TIMEOUT):
    """TLS 层校验：必须真的收到 HTTP 状态行。

    只测 TCP 不够——被干扰的 IP 常常 TCP 能连、TLS 也能握手，
    却永远不返回任何 HTTP 响应。只看 TCP 会选中这种「假活」地址，
    结果就是浏览器一直转圈。
    """
    raw = tls = None
    try:
        raw = socket.create_connection((ip, 443), timeout=timeout)
        tls = _ssl_ctx.wrap_socket(raw, server_hostname=host)
        tls.settimeout(timeout)
        tls.sendall(("HEAD / HTTP/1.0\r\nHost: %s\r\nUser-Agent: ghproxy\r\n\r\n"
                     % host).encode())
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


def check(host, ip):
    """完整校验：TCP 可连且 TLS 层有真实 HTTP 响应。"""
    return ip if (probe(ip) and http_alive(host, ip)) else None


def scan(host):
    """并发扫描一个域名的全部候选，返回当前可用列表（保持候选顺序）。"""
    ips = MAP_HOSTS.get(host, [])
    if not ips:
        return []
    alive = set()
    with cf.ThreadPoolExecutor(max_workers=min(8, len(ips))) as ex:
        futs = {ex.submit(check, host, ip): ip for ip in ips}
        for f in cf.as_completed(list(futs)):
            try:
                if f.result():
                    alive.add(futs[f])
            except Exception:
                pass
    return [ip for ip in ips if ip in alive]


def health_loop():
    """后台常驻：持续刷新可用 IP 集合。

    采用自适应退避：某域名有可用 IP 时每 8 秒复查；
    完全不可用（整域封锁）时逐步退避到 60 秒，避免空转和无谓流量。
    """
    while True:
        now = time.time()
        with _lock:
            due = [h for h in MAP_HOSTS if _next_check.get(h, 0.0) <= now]
        if due:
            jobs = [(h, ip) for h in due for ip in MAP_HOSTS[h]]
            alive = {}
            try:
                with cf.ThreadPoolExecutor(max_workers=16) as ex:
                    futs = {ex.submit(check, h, ip): (h, ip) for h, ip in jobs}
                    for f in cf.as_completed(list(futs)):
                        try:
                            ok = f.result()
                        except Exception:
                            continue
                        if ok:
                            alive.setdefault(futs[f][0], []).append(ok)
            except Exception:
                pass
            with _lock:
                for h in due:
                    ips = MAP_HOSTS[h]
                    good = alive.get(h, [])
                    good.sort(key=lambda ip: ips.index(ip) if ip in ips else 99)
                    _health[h] = good
                    if good:
                        _backoff[h] = HEALTH_INTERVAL
                        _next_check[h] = time.time() + HEALTH_INTERVAL
                    else:
                        back = min(60.0, max(HEALTH_INTERVAL, _backoff.get(h, HEALTH_INTERVAL) * 2))
                        _backoff[h] = back
                        _next_check[h] = time.time() + back
        time.sleep(1.0)


def candidates(host):
    """取当前可用 IP，把上次成功过的排在前面。"""
    with _lock:
        good = list(_health.get(host, []))
        pref = _preferred.get(host)
    if pref and pref in good:
        good.remove(pref)
        good.insert(0, pref)
    return good


def ondemand(host):
    """集合为空时现场扫一次，带节流，避免每个请求都全量探测。"""
    now = time.time()
    with _lock:
        if now - _last_ondemand.get(host, 0.0) < ONDEMAND_THROTTLE:
            return []
        _last_ondemand[host] = now
    good = scan(host)
    with _lock:
        _health[host] = good
    return good


def connect_upstream(host, port):
    """为已映射域名选路建连；选不到就快速失败，不回退被封锁的 DNS 地址。"""
    if port == 443 and host in MAP_HOSTS:
        ips = candidates(host)
        if not ips:
            ips = ondemand(host)
        if not ips:
            raise OSError("no reachable IP for %s" % host)
        last_err = None
        for ip in ips[:MAX_TRY]:
            try:
                s = socket.create_connection((ip, port), timeout=CONNECT_TIMEOUT)
                with _lock:
                    _preferred[host] = ip
                return s
            except Exception as e:
                last_err = e
                with _lock:  # 该 IP 已失效，从可用集合剔除，后续请求不再撞它
                    if ip in _health.get(host, []):
                        _health[host].remove(ip)
        raise last_err or OSError("connect failed for %s" % host)
    return socket.create_connection((host, port), timeout=10)


def pipe(a, b):
    """双向搬运数据；空闲超过 IDLE_TIMEOUT 主动关闭，防止死连接堆积。"""
    last = time.time()
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 5)
            if not r:
                if time.time() - last > IDLE_TIMEOUT:
                    return
                continue
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
                last = time.time()
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass


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

        # 明文 HTTP：把 absolute-URI 改写成 origin-form 再转发
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
    s.listen(128)
    threading.Thread(target=health_loop, daemon=True).start()
    print("ghproxy 127.0.0.1:%d hosts=%d health=%.0fs"
          % (PORT, len(MAP_HOSTS), HEALTH_INTERVAL), flush=True)
    while True:
        c, _ = s.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
