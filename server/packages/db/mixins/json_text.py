"""JSON-in-Text column accessor helper.

Models that store JSON blobs in ``Text`` columns can use this helper to add
a typed ``@property`` that transparently round-trips through ``json.loads`` /
``json.dumps`` — the raw column remains fully accessible at all times.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def json_text(column_name: str) -> Any:  # type: ignore[return-value]
    """Return a ``@property`` that serialises/deserialises a ``Text`` column.

    Read: parses the stored JSON string (or returns ``None`` when empty).
    Write: accepts a Python object (dict, list, …) and stores its JSON encoding.
    """

    def fget(self: Any) -> Any:  # noqa: ANN401
        raw = getattr(self, column_name)
        if not raw:
            return None
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, TypeError):
            return None

    def fset(self: Any, value: Any) -> None:  # noqa: ANN401
        if value is None:
            setattr(self, column_name, None)
        else:
            setattr(self, column_name, json.dumps(value, ensure_ascii=False))

    return property(fget, fset)
