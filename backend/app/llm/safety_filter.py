import re

# This is defense-in-depth, not the primary guardrail. The real protection is
# that no tool in tool_executor.py ever returns these things — this filter
# only exists to catch the model discussing them if somehow prompted to.
_BLOCKED_PATTERNS = [
    re.compile(r"(?i)\bapi[_ -]?key\b"),
    re.compile(r"(?i)\bpassword\s*hash\b"),
    re.compile(r"(?i)\bsystem\s*prompt\b"),
    re.compile(r"(?i)\bdatabase\s*schema\b"),
    re.compile(r"(?i)\bembedding\s*model\b"),
]

_FALLBACK_REPLY = (
    "I can't share confidential account or system details. Is there something about your "
    "orders, products, or account I can help with instead?"
)


def filter_reply(text: str) -> str:
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return _FALLBACK_REPLY
    return text
