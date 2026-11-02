# -*- coding: utf-8 -*-
"""TCP 代理：注入真实 RTT 与丢包，模拟 WAN。"""
import argparse, random, socket, threading, time

def pipe(src, dst, latency):
    try:
        while True:
            data = src.recv(65536)
            if not data: break
            if latency: time.sleep(latency)
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: dst.shutdown(socket.SHUT_WR)
        except Exception: pass

def handle(c, target, latency, loss):
    if random.random() < loss:
        c.close(); return
    try:
        s = socket.create_connection(target, timeout=5)
    except Exception:
        c.close(); return
    threading.Thread(target=pipe, args=(c, s, latency), daemon=True).start()
    pipe(s, c, latency)

def serve(port=8780, target=("127.0.0.1", 8765), latency_ms=30, loss=0.05):
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port)); srv.listen(128)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c, target, latency_ms / 1000.0, loss), daemon=True).start()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--target", default="127.0.0.1:8765")
    ap.add_argument("--latency-ms", type=float, default=30)
    ap.add_argument("--loss", type=float, default=0.05)
    a = ap.parse_args()
    host, p = a.target.split(":"); print(f"proxy :{a.port} -> {a.target} {a.latency_ms}ms loss {a.loss}", flush=True)
    serve(a.port, (host, int(p)), a.latency_ms, a.loss)
