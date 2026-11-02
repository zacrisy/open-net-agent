# -*- coding: utf-8 -*-
"""异步落库：队列 + 后台写线程。"""
import queue, threading
import db

Q = queue.Queue()


def _run():
    while True:
        item = Q.get()
        if item is None:
            Q.task_done(); break
        fn, args = item
        try: fn(*args)
        except Exception: pass
        finally: Q.task_done()


threading.Thread(target=_run, daemon=True).start()


def log_node(*a): Q.put((db.log_node, a))
def log_task(*a): Q.put((db.log_task, a))
def log_result(*a): Q.put((db.log_result, a))
def flush(): Q.join()
