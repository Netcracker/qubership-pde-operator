from datetime import UTC, datetime

import pytest

from pde_operator.utils.cron_utils import CronExpressionError, CronUtils, TimezoneError


def test_five_and_six_field_expressions_are_accepted() -> None:
    CronUtils.validate_expression("0 9 * * *", min_interval_seconds=60)
    CronUtils.validate_expression("* * * * *", min_interval_seconds=60)
    CronUtils.validate_expression("0 0 9 * * *", min_interval_seconds=60)
    CronUtils.validate_expression("0 */5 * * * *", min_interval_seconds=60)


def test_six_field_seconds_come_first() -> None:
    base = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)

    # "second minute hour day month weekday": daily at 09:00:00, not every second on the 9th
    assert CronUtils.next_fire_times("0 0 9 * * *", "UTC", 2, base=base) == [
        datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        datetime(2026, 7, 2, 9, 0, tzinfo=UTC),
    ]
    assert CronUtils.next_fire_times("0 */5 * * * *", "UTC", 2, base=base) == [
        datetime(2026, 7, 1, 0, 5, tzinfo=UTC),
        datetime(2026, 7, 1, 0, 10, tzinfo=UTC),
    ]


def test_sub_minute_expressions_are_rejected_by_the_interval_check() -> None:
    with pytest.raises(CronExpressionError, match="minimum interval"):
        CronUtils.validate_expression("*/30 * * * * *", min_interval_seconds=60)
    with pytest.raises(CronExpressionError, match="minimum interval"):
        CronUtils.validate_expression("*/5 * * * * *", min_interval_seconds=60)


def test_every_minute_is_allowed_at_the_default_minimum() -> None:
    CronUtils.validate_expression("* * * * *", min_interval_seconds=60)
    CronUtils.validate_expression("0 * * * * *", min_interval_seconds=60)


def test_invalid_expressions_and_field_counts_are_rejected() -> None:
    for expression in ("", "   ", "not a cron", "0 0 * *", "0 0 * * * * *"):
        with pytest.raises(CronExpressionError):
            CronUtils.validate_expression(expression, min_interval_seconds=60)


def test_next_fire_times_follow_the_expression_timezone() -> None:
    summer = CronUtils.next_fire_times("0 9 * * *", "Europe/Berlin", 1, base=datetime(2026, 7, 1, tzinfo=UTC))
    winter = CronUtils.next_fire_times("0 9 * * *", "Europe/Berlin", 1, base=datetime(2026, 1, 1, tzinfo=UTC))

    assert summer == [datetime(2026, 7, 1, 7, 0, tzinfo=UTC)]  # CEST (UTC+2)
    assert winter == [datetime(2026, 1, 1, 8, 0, tzinfo=UTC)]  # CET (UTC+1)


def test_next_fire_times_survive_a_dst_spring_forward() -> None:
    # 02:30 local does not exist on 2026-03-29 in Berlin; whichever instant croniter picks for the
    # gap day, the surrounding days must stay anchored to 02:30 local and never double-fire.
    fires = CronUtils.next_fire_times(
        "30 2 * * *", "Europe/Berlin", 3, base=datetime(2026, 3, 28, 12, 0, tzinfo=UTC)
    )

    assert all(fire.tzinfo == UTC for fire in fires)  # always normalised back to UTC
    assert fires == sorted(fires)
    assert len({fire.date() for fire in fires}) == 3  # one fire per day, gap day included
    assert fires[1] == datetime(2026, 3, 30, 0, 30, tzinfo=UTC)  # back to CEST (UTC+2)
    assert fires[2] == datetime(2026, 3, 31, 0, 30, tzinfo=UTC)


def test_resolve_timezone_rejects_unknown_names() -> None:
    with pytest.raises(TimezoneError):
        CronUtils.resolve_timezone("Mars/Olympus")
    with pytest.raises(TimezoneError):
        CronUtils.resolve_timezone("")
    assert str(CronUtils.resolve_timezone("Europe/Berlin")) == "Europe/Berlin"


def test_available_timezones_excludes_internal_prefixes() -> None:
    timezones = CronUtils.available_timezones()

    assert "UTC" in timezones
    assert "Europe/Berlin" in timezones
    assert not any(name.startswith(("posix/", "right/")) for name in timezones)
    assert timezones == sorted(timezones)
