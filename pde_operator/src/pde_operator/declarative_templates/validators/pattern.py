from __future__ import annotations

import re

from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.declarative_templates.contract.models import FieldSpec


class PatternValidator:
    @staticmethod
    def validate(field: FieldSpec, value: str) -> None:
        for validator in field.validators:
            if validator.type == "pattern" and re.match(validator.value, value) is None:
                raise DeclarativeContractError(f"Field '{field.name}' failed validation: {validator.message}")
