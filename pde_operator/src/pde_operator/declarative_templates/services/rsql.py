from __future__ import annotations

import re
from typing import Any

from pde_operator.declarative_templates.contract.errors import DeclarativeContractError

# FIELD=='literal' | FIELD!='literal' | FIELD==OTHER | FIELD!=OTHER
_RSQL_RE = re.compile(
    r"^\s*(?P<left>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>==|!=)\s*(?:'(?P<literal>[^']*)'|(?P<right>[A-Za-z_][A-Za-z0-9_]*))\s*$"
)


class RsqlUtils:
    """Evaluate the supported RSQL subset for hide_condition / required_condition."""

    @staticmethod
    def evaluate(expression: str | None, values: dict[str, Any]) -> bool:
        if expression is None or not expression.strip():
            return False
        match = _RSQL_RE.match(expression)
        if match is None:
            raise DeclarativeContractError(f"Unsupported RSQL expression: {expression!r} (only == and != are supported)")
        left = match.group("left")
        op = match.group("op")
        if match.group("literal") is not None:
            right_value: Any = match.group("literal")
        else:
            right_name = match.group("right")
            right_value = values.get(right_name)
        left_value = values.get(left)
        equal = RsqlUtils._normalize(left_value) == RsqlUtils._normalize(right_value)
        return equal if op == "==" else not equal

    @staticmethod
    def _normalize(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
