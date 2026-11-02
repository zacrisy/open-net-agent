# -*- coding: utf-8 -*-
"""稳定 GitHub 连接：本地 CONNECT 代理，多 IP 探测 + 故障切换，绕过 DNS。"""
import select, socket, subprocess, threading, time

CANDIDATES = ["140.82.113.3", "140.82.116.3", "140.82.112.3", "140.82.114.3", "20.205.243.166"]
MAP_HOSTS = ("github.com", "www.github.com", "gist.github.com", "codeload.github.com")
PORT = 8899
_lock = threading.Lock()
_cached = (None, 0.0)


def probe(ip, timeout=1.5):
    s = socket.socket(); s.settimeout(timeout)
    try:
        s.connect((ip, 443)); return True
    except Exception:
        return False
    finally:
        s.close()


def valid(ip):
    try:
        r = subprocess.run(["curl", "-4", "-sI", "--resolve", f"github.com:443:{ip}",
                            "--max-time", "6", "https://github.com"],
                           capture_output=True, text=True, timeout=8)
        first = (r.stdout or "").splitlines()[0] if r.stdout else ""
        return "200" in first
    except Exception:
        return False


def best_ip(force=False):
    global _cached
    with _lock:
        ip, ts = _cached
        if ip and not force and time.time() - ts < 120:
            return ip
        for cand in CANDIDATES:
            if probe(cand) and valid(cand):
                _cached = (cand, time.time())
                return cand
        return CANDIDATES[0]


def pipe(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 30)
            if not r: continue
            for s in r:
                data = s.recv(65536)
                if not data: return
                (b if s is a else a).sendall(data)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try: s.close()
            except Exception: pass


def handle(c):
    try:
        data = c.recv(8192)
        line = data.split(b"\r\n")[0].decode(errors="ignore")
        if not line.startswith("CONNECT"):
            c.close(); return
        host, port = line.split()[1].split(":")
        target = host
        if host in MAP_HOSTS:
            target = best_ip()
        try:
            up = socket.create_connection((target, int(port)), timeout=10)
        except Exception:
            if host in MAP_HOSTS:
                target = best_ip(force=True)
                up = socket.create_connection((target, int(port)), timeout=10)
            else:
                raise
        c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        pipe(c, up)
    except Exception:
        try: c.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception: pass
        try: c.close()
        except Exception: pass


def main():
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PORT)); s.listen(80)
    print(f"ghproxy 127.0.0.1:{PORT} candidates={CANDIDATES}", flush=True)
    while True:
        c, _ = s.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
