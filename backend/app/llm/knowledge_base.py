import json
import re
from pathlib import Path

_KB_PATH = Path(__file__).parent / "knowledge_base.json"
_ENTRIES: list[dict] = json.loads(_KB_PATH.read_text(encoding="utf-8"))

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


# Precompute each entry's searchable token set once at import time — the KB
# is small (~24 entries) and static, so a simple keyword-overlap score is
# enough. Same "no vector store" simplicity as conversation memory; swap
# for real search/embeddings only if the KB grows large enough to need it.
_INDEX = [(entry, _tokenize(f"{entry['title']} {entry['content']} {entry['category']}")) for entry in _ENTRIES]


def search(query: str, top_k: int = 3) -> list[dict]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = [(len(query_tokens & tokens), entry) for entry, tokens in _INDEX]
    scored = [(score, entry) for score, entry in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [
        {
            "category": entry["category"],
            "title": entry["title"],
            "content": entry["content"],
            "source_url": entry["source_url"],
        }
        for _, entry in scored[:top_k]
    ]
