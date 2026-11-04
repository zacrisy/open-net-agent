# -*- coding: utf-8 -*-
"""稳定 GitHub 连接：本地 CONNECT / HTTP 代理。

背景：该网络对 GitHub 的封锁是「成阵 + 按节点」的——
同一时刻某些 IP 完全不可达，另一些却完好；几十分钟后又会换一批。
因此这里不绑定任何固定 IP，而是后台持续探测全部候选，
按「此刻的真实响应延迟」排序，连接时优先用最快且可用的那个。

GitHub 各域名必须用自己的 IP 段（主站 / api / codeload 各自不同），
混用会被边缘节点重定向，下载链路会变成 404。
非 GitHub 域名原样直连，不受任何影响。
"""
import concurrent.futures as cf
import queue, select, socket, ssl, threading, time

# 主站：优先 Azure 节点（140.82.x 自有 AS 常被整段封）
GITHUB_IPS = ["20.29.134.23", "20.175.192.147",
              "140.82.112.4", "140.82.113.4",
              "140.82.112.3", "140.82.113.3", "140.82.114.3", "140.82.116.3",
              "20.205.243.166", "20.27.177.113", "20.200.245.247", "20.201.28.151"]
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
HEALTH_INTERVAL = 10.0     # 有可用 IP 时的复查周期
CONNECT_TIMEOUT = 3.0      # 单个上游连接超时（竞速时每个候选一个）
ONDEMAND_THROTTLE = 2.0    # 现场快检节流
MAX_TRY = 6                # 每次连接最多同时竞速几个 IP
IDLE_TIMEOUT = 75.0        # 隧道空闲超时，防止死连接被浏览器反复复用

_ssl_ctx = ssl.create_default_context()
_lock = threading.Lock()
_health = {}               # host -> [(ip, 延迟), ...] 按延迟升序
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


def http_alive(host, ip, timeout=2.5):
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
    """完整校验，成功返回 (ip, 耗时)，失败返回 None。"""
    t0 = time.time()
    if probe(ip) and http_alive(host, ip):
        return ip, time.time() - t0
    return None


def scan(host):
    """并发扫描某域名全部候选，按延迟升序返回可用 (ip, 延迟)。"""
    ips = MAP_HOSTS.get(host, [])
    if not ips:
        return []
    found = []
    with cf.ThreadPoolExecutor(max_workers=min(8, len(ips))) as ex:
        futs = [ex.submit(check, host, ip) for ip in ips]
        for f in cf.as_completed(futs):
            try:
                r = f.result()
            except Exception:
                continue
            if r:
                found.append(r)
    found.sort(key=lambda x: x[1])
    return found


def health_loop():
    """后台常驻：刷新各域名的可用 IP 列表（带自适应退避）。"""
    while True:
        now = time.time()
        with _lock:
            due = [h for h in MAP_HOSTS if _next_check.get(h, 0.0) <= now]
        if due:
            jobs = [(h, ip) for h in due for ip in MAP_HOSTS[h]]
            alive = {}
            try:
                with cf.ThreadPoolExecutor(max_workers=16) as ex:
                    futmap = {ex.submit(check, h, ip): (h, ip) for h, ip in jobs}
                    for f in cf.as_completed(list(futmap)):
                        try:
                            r = f.result()
                        except Exception:
                            continue
                        if r:
                            alive.setdefault(futmap[f][0], []).append(r)
            except Exception:
                pass
            with _lock:
                for h in due:
                    good = alive.get(h, [])
                    good.sort(key=lambda x: x[1])
                    _health[h] = good
                    if good:
                        _backoff[h] = HEALTH_INTERVAL
                        _next_check[h] = time.time() + HEALTH_INTERVAL
                    else:
                        back = min(15.0, max(HEALTH_INTERVAL,
                                             _backoff.get(h, HEALTH_INTERVAL) * 2))
                        _backoff[h] = back
                        _next_check[h] = time.time() + back
        time.sleep(1.0)


def candidates(host):
    """当前可用 IP（按延迟升序），上次成功的排最前。"""
    with _lock:
        good = list(_health.get(host, []))
        pref = _preferred.get(host)
    if pref:
        for i, (ip, _) in enumerate(good):
            if ip == pref:
                good.insert(0, good.pop(i))
                break
    return [ip for ip, _ in good]


def ondemand(host):
    """列表为空时现场扫一次，带节流。"""
    now = time.time()
    with _lock:
        if now - _last_ondemand.get(host, 0.0) < ONDEMAND_THROTTLE:
            return []
        _last_ondemand[host] = now
    good = scan(host)
    with _lock:
        _health[host] = good
    return [ip for ip, _ in good]


def race_connect(ips, port, timeout=CONNECT_TIMEOUT):
    """并发竞速：同时连所有候选，谁先握手成功就用谁。

    顺序重试在「多数节点被封」时会让每个死 IP 白等一次超时（实测 8 秒以上）。
    并发竞速把最坏情况压到一个超时周期。
    """
    if not ips:
        return None, None
    q = queue.Queue()
    won = threading.Event()

    def attempt(ip):
        try:
            s = socket.create_connection((ip, port), timeout=timeout)
        except Exception:
            q.put((ip, None))
            return
        if won.is_set():          # 已有赢家，丢弃多余连接，避免句柄泄漏
            try:
                s.close()
            except Exception:
                pass
            return
        won.set()
        q.put((ip, s))

    for ip in ips[:MAX_TRY]:
        threading.Thread(target=attempt, args=(ip,), daemon=True).start()

    deadline = time.time() + timeout + 0.5
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            ip, s = q.get(timeout=remaining)
        except queue.Empty:
            break
        if s:
            return ip, s
    return None, None


def connect_upstream(host, port):
    """为已映射域名选路建连；选不到就快速失败，不回退被封锁的 DNS 地址。"""
    if port == 443 and host in MAP_HOSTS:
        ips = candidates(host)
        if not ips:
            ips = ondemand(host)
        if not ips:
            raise OSError("no reachable IP for %s" % host)
        ip, sock_ = race_connect(ips, port)
        if sock_:
            with _lock:
                _preferred[host] = ip
            return sock_
        with _lock:  # 全部失败：清空列表，触发下次请求重新扫描
            _health[host] = []
        raise OSError("all candidates failed for %s" % host)
    return socket.create_connection((host, port), timeout=10)


def pipe(a, b):
    """双向搬运；空闲超过 IDLE_TIMEOUT 主动关闭，防止死连接堆积。"""
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
    print("ghproxy 127.0.0.1:%d hosts=%d interval=%.0fs"
          % (PORT, len(MAP_HOSTS), HEALTH_INTERVAL), flush=True)
    while True:
        c, _ = s.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
