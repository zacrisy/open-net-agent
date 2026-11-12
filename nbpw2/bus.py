# -*- coding: utf-8 -*-
"""In-process BMB bus for tests and single-host simulation."""
from collections import defaultdict
from .protocol import envelope, EventLog

class Bus:
    def __init__(self, log=None):
        self.subs = defaultdict(list)
        self.log = log or EventLog()

    def subscribe(self, node, type_=None):
        self.subs[(node, type_)].append(node)

    def publish(self, msg):
        self.log.append(msg)
        for (node, type_), _ in list(self.subs.items()):
            if node == msg["dst"] and (type_ is None or type_ == msg["type"]):
                pass
        return msg

    def send(self, type_, src, dst="workspace", **kw):
        return self.publish(envelope(type_, src, dst, **kw))
