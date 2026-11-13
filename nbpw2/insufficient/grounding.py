# -*- coding: utf-8 -*-
"""Cheap answer-grounding check used by the insufficient-evidence analysis.

The extractive reader always returns a span from one of the selected paragraphs.
That does not mean the paragraph answers the question.  This check asks whether
the answer-bearing paragraph is connected to the question or to another
selected paragraph by a title/entity mention.

It is deliberately simple and local (no LLM): it is a candidate abstain signal,
not a correctness judge.
"""
import re

STOP = {
    "the", "a", "an", "what", "which", "who", "whom", "whose", "when", "where",
    "why", "how", "is", "are", "was", "were", "did", "does", "do", "of", "in",
    "on", "at", "to", "for", "from", "by", "with", "and", "or", "that", "this",
    "these", "those", "it", "its", "he", "she", "they", "his", "her", "their",
    "other", "than", "also", "same", "city", "current", "population", "sport",
}


def question_entities(q):
    runs = re.findall(r"\b[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+)*", q or "")
    out = []
    for r in runs:
        r = r.strip()
        if not r or r.lower() in STOP:
            continue
        out.append(r)
    return out


def is_grounded(question, selected, source_title, source_text):
    """True if the answer paragraph is linked to the question or the selection."""
    q = (question or "").lower()
    st = (source_title or "").lower()
    text = (source_text or "").lower()
    if st and st in q:
        return True
    for s in selected or []:
        t = (s.get("title") or "").lower()
        if not t or t == st:
            continue
        sn = (s.get("snippet") or "").lower()
        if st and st in sn:
            return True
        if t in text:
            return True
    for ent in question_entities(question):
        if ent.lower() in text:
            return True
    return False
