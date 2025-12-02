from typing import Any, Dict

def v(d: Dict[str, Any], key: str):
    """Normalize values coming from xmltodict (may be lists)."""
    val = d.get(key)
    if isinstance(val, list):
        val = val[0]
    return val
