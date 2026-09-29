from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from croniter import croniter

MIN_FIELDS = 5
MAX_FIELDS = 6
_INTERVAL_SAMPLES = 8


class CronExpressionError(ValueError):
    pass


class TimezoneError(ValueError):
    pass


class CronUtils:
    @staticmethod
    def resolve_timezone(name: str) -> ZoneInfo:
        cleaned = (name or "").strip()
        if not cleaned:
            raise TimezoneError("Timezone is required")
        try:
            return ZoneInfo(cleaned)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise TimezoneError(f"Unknown timezone '{name}'") from exc

    @staticmethod
    def validate_expression(expression: str, *, min_interval_seconds: int = 0) -> None:
        cleaned = (expression or "").strip()
        if not cleaned:
            raise CronExpressionError("Cron expression is required")
        fields = cleaned.split()
        if not MIN_FIELDS <= len(fields) <= MAX_FIELDS:
            raise CronExpressionError(f"Cron expression must have {MIN_FIELDS} or {MAX_FIELDS} fields, got {len(fields)}: '{expression}'")
        if not croniter.is_valid(cleaned, **CronUtils._cron_kwargs(cleaned)):
            raise CronExpressionError(f"Invalid cron expression: '{expression}'")
        if min_interval_seconds > 0:
            gap = CronUtils._sub_minimum_gap(cleaned, min_interval_seconds)
            if gap is not None:
                raise CronExpressionError(f"Cron expression fires every {gap:g}s, which is below the minimum interval of {min_interval_seconds}s")

    @staticmethod
    def next_fire_times(expression: str, timezone: str, count: int, *, base: datetime | None = None) -> list[datetime]:
        start = base or datetime.now(UTC)
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        local_base = start.astimezone(CronUtils.resolve_timezone(timezone))
        iterator = croniter(expression, local_base, **CronUtils._cron_kwargs(expression))
        return [iterator.get_next(datetime).astimezone(UTC) for _ in range(max(count, 1))]

    @staticmethod
    def next_fire_time(expression: str, timezone: str, *, base: datetime | None = None) -> datetime:
        return CronUtils.next_fire_times(expression, timezone, 1, base=base)[0]

    @staticmethod
    def _cron_kwargs(expression: str) -> dict:
        # croniter puts the seconds field last by default; users expect the usual seconds-first
        # ordering for 6-field expressions, so opt into it whenever a seconds field is present.
        return {"second_at_beginning": True} if len(expression.split()) == MAX_FIELDS else {}

    @staticmethod
    @lru_cache(maxsize=1)
    def available_timezones() -> list[str]:
        names = {
            name
            for name in available_timezones()
            if "/" in name and not name.startswith(("posix/", "right/"))
        }
        names.add("UTC")
        return sorted(names)

    @staticmethod
    def _sub_minimum_gap(expression: str, threshold: int) -> float | None:
        """First gap below the threshold within the sampled occurrences, else None."""
        iterator = croniter(expression, datetime.now(UTC), **CronUtils._cron_kwargs(expression))
        previous = iterator.get_next(datetime)
        for _ in range(_INTERVAL_SAMPLES - 1):
            current = iterator.get_next(datetime)
            gap = (current - previous).total_seconds()
            if gap < threshold:
                return gap
            previous = current
        return None
