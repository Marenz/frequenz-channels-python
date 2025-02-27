# License: MIT
# Copyright © 2022 Frequenz Energy-as-a-Service GmbH

"""Tests for the timer."""

from __future__ import annotations

import asyncio
import enum
from collections.abc import Iterator
from datetime import timedelta

import async_solipsism
import hypothesis
import pytest
from hypothesis import strategies as st

from frequenz.channels.util import (
    SkipMissedAndDrift,
    SkipMissedAndResync,
    Timer,
    TriggerAllMissed,
)


# Setting 'autouse' has no effect as this method replaces the event loop for all tests in the file.
@pytest.fixture()
def event_loop() -> Iterator[async_solipsism.EventLoop]:
    """Replace the loop with one that doesn't interact with the outside world."""
    loop = async_solipsism.EventLoop()
    yield loop
    loop.close()


_max_timedelta_microseconds = (
    int(
        timedelta.max.total_seconds() * 1_000_000,
    )
    - 1
)

_min_timedelta_microseconds = (
    int(
        timedelta.min.total_seconds() * 1_000_000,
    )
    + 1
)

_calculate_next_tick_time_args = {
    "now": st.integers(),
    "scheduled_tick_time": st.integers(),
    "interval": st.integers(min_value=1, max_value=_max_timedelta_microseconds),
}


def _assert_tick_is_aligned(
    next_tick_time: int, now: int, scheduled_tick_time: int, interval: int
) -> None:
    # Can be equals if scheduled_tick_time == now
    assert next_tick_time <= now + interval
    assert (next_tick_time - scheduled_tick_time) % interval == pytest.approx(0.0)


@hypothesis.given(**_calculate_next_tick_time_args)
def test_policy_trigger_all_missed(
    now: int, scheduled_tick_time: int, interval: int
) -> None:
    """Test the TriggerAllMissed policy."""
    hypothesis.assume(now >= scheduled_tick_time)
    assert (
        TriggerAllMissed().calculate_next_tick_time(
            now=now, interval=interval, scheduled_tick_time=scheduled_tick_time
        )
        == scheduled_tick_time + interval
    )


def test_policy_trigger_all_missed_examples() -> None:
    """Test the TriggerAllMissed policy with minimal examples.

    This is just a sanity check to make sure we are not missing to test any important
    properties with the hypothesis tests.
    """
    policy = TriggerAllMissed()
    assert (
        policy.calculate_next_tick_time(
            now=10_200_000, scheduled_tick_time=9_000_000, interval=1_000_000
        )
        == 10_000_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_000_000, scheduled_tick_time=9_000_000, interval=1_000_000
        )
        == 10_000_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_500_000, scheduled_tick_time=1_000_000, interval=1_000_000
        )
        == 2_000_000
    )


@hypothesis.given(**_calculate_next_tick_time_args)
def test_policy_skip_missed_and_resync(
    now: int, scheduled_tick_time: int, interval: int
) -> None:
    """Test the SkipMissedAndResync policy."""
    hypothesis.assume(now >= scheduled_tick_time)

    next_tick_time = SkipMissedAndResync().calculate_next_tick_time(
        now=now, interval=interval, scheduled_tick_time=scheduled_tick_time
    )
    assert next_tick_time > now
    _assert_tick_is_aligned(next_tick_time, now, scheduled_tick_time, interval)


def test_policy_skip_missed_and_resync_examples() -> None:
    """Test the SkipMissedAndResync policy with minimal examples.

    This is just a sanity check to make sure we are not missing to test any important
    properties with the hypothesis tests.
    """
    policy = SkipMissedAndResync()
    assert (
        policy.calculate_next_tick_time(
            now=10_200_000, scheduled_tick_time=9_000_000, interval=1_000_000
        )
        == 11_000_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_000_000, scheduled_tick_time=9_000_000, interval=1_000_000
        )
        == 11_000_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_500_000, scheduled_tick_time=1_000_000, interval=1_000_000
        )
        == 11_000_000
    )


@hypothesis.given(
    tolerance=st.integers(min_value=_min_timedelta_microseconds, max_value=-1)
)
def test_policy_skip_missed_and_drift_invalid_tolerance(tolerance: int) -> None:
    """Test the SkipMissedAndDrift policy raises an error for invalid tolerances."""
    with pytest.raises(ValueError, match="delay_tolerance must be positive"):
        SkipMissedAndDrift(delay_tolerance=timedelta(microseconds=tolerance))


@hypothesis.given(
    tolerance=st.integers(min_value=0, max_value=_max_timedelta_microseconds),
    **_calculate_next_tick_time_args,
)
def test_policy_skip_missed_and_drift(
    tolerance: int, now: int, scheduled_tick_time: int, interval: int
) -> None:
    """Test the SkipMissedAndDrift policy."""
    hypothesis.assume(now >= scheduled_tick_time)

    next_tick_time = SkipMissedAndDrift(
        delay_tolerance=timedelta(microseconds=tolerance)
    ).calculate_next_tick_time(
        now=now, interval=interval, scheduled_tick_time=scheduled_tick_time
    )
    if tolerance < interval:
        assert next_tick_time > now
    drift = now - scheduled_tick_time
    if drift > tolerance:
        assert next_tick_time == now + interval
    else:
        _assert_tick_is_aligned(next_tick_time, now, scheduled_tick_time, interval)


def test_policy_skip_missed_and_drift_examples() -> None:
    """Test the SkipMissedAndDrift policy with minimal examples.

    This is just a sanity check to make sure we are not missing to test any important
    properties with the hypothesis tests.
    """
    tolerance = 100_000
    policy = SkipMissedAndDrift(delay_tolerance=timedelta(microseconds=tolerance))
    assert (
        policy.calculate_next_tick_time(
            now=10_200_000, scheduled_tick_time=9_000_000, interval=1_000_000
        )
        == 11_200_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_000_000, scheduled_tick_time=9_000_000, interval=1_000_000
        )
        == 11_000_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_500_000, scheduled_tick_time=1_000_000, interval=1_000_000
        )
        == 11_500_000
    )
    assert (
        policy.calculate_next_tick_time(
            now=10_000_000 + tolerance,
            scheduled_tick_time=10_000_000,
            interval=1_000_000,
        )
        == 11_000_000
    )


async def test_timer_contruction_defaults() -> None:
    """Test the construction of a periodic timer with default values."""
    timer = Timer(timedelta(seconds=1.0), TriggerAllMissed())
    assert timer.interval == timedelta(seconds=1.0)
    assert isinstance(timer.missed_tick_policy, TriggerAllMissed)
    assert timer.loop is asyncio.get_running_loop()
    assert timer.is_running is True


def test_timer_contruction_no_async() -> None:
    """Test the construction outside of async (using a custom loop)."""
    loop = async_solipsism.EventLoop()
    timer = Timer(timedelta(seconds=1.0), TriggerAllMissed(), loop=loop)
    assert timer.interval == timedelta(seconds=1.0)
    assert isinstance(timer.missed_tick_policy, TriggerAllMissed)
    assert timer.loop is loop
    assert timer.is_running is True


def test_timer_contruction_no_event_loop() -> None:
    """Test the construction outside of async (without a custom loop) fails."""
    with pytest.raises(RuntimeError, match="no running event loop"):
        Timer(timedelta(seconds=1.0), TriggerAllMissed())


async def test_timer_contruction_auto_start() -> None:
    """Test the construction of a periodic timer with auto_start=False."""
    policy = TriggerAllMissed()
    timer = Timer(
        timedelta(seconds=5.0),
        policy,
        auto_start=False,
        loop=None,
    )
    assert timer.interval == timedelta(seconds=5.0)
    assert timer.missed_tick_policy is policy
    assert timer.loop is asyncio.get_running_loop()
    assert timer.is_running is False


async def test_timer_contruction_custom_args() -> None:
    """Test the construction of a periodic timer with custom arguments."""
    policy = TriggerAllMissed()
    timer = Timer(
        timedelta(seconds=5.0),
        policy,
        auto_start=True,
        loop=None,
    )
    assert timer.interval == timedelta(seconds=5.0)
    assert timer.missed_tick_policy is policy
    assert timer.loop is asyncio.get_running_loop()
    assert timer.is_running is True


async def test_timer_contruction_timeout_custom_args() -> None:
    """Test the construction of a timeout timer with custom arguments."""
    timer = Timer.timeout(
        timedelta(seconds=5.0),
        auto_start=True,
        loop=None,
    )
    assert timer.interval == timedelta(seconds=5.0)
    assert isinstance(timer.missed_tick_policy, SkipMissedAndDrift)
    assert timer.missed_tick_policy.delay_tolerance == timedelta(0)
    assert timer.loop is asyncio.get_running_loop()
    assert timer.is_running is True


async def test_timer_contruction_periodic_defaults() -> None:
    """Test the construction of a periodic timer."""
    timer = Timer.periodic(timedelta(seconds=5.0))
    assert timer.interval == timedelta(seconds=5.0)
    assert isinstance(timer.missed_tick_policy, TriggerAllMissed)
    assert timer.loop is asyncio.get_running_loop()
    assert timer.is_running is True


async def test_timer_contruction_periodic_custom_args() -> None:
    """Test the construction of a timeout timer with custom arguments."""
    timer = Timer.periodic(
        timedelta(seconds=5.0),
        skip_missed_ticks=True,
        auto_start=True,
        loop=None,
    )
    assert timer.interval == timedelta(seconds=5.0)
    assert isinstance(timer.missed_tick_policy, SkipMissedAndResync)
    assert timer.loop is asyncio.get_running_loop()
    assert timer.is_running is True


async def test_timer_autostart(
    event_loop: async_solipsism.EventLoop,  # pylint: disable=redefined-outer-name
) -> None:
    """Test the autostart of a periodic timer."""
    timer = Timer(timedelta(seconds=1.0), TriggerAllMissed())

    # We sleep some time, less than the interval, and then receive from the
    # timer, since it was automatically started at time 0, it should trigger at
    # time 1.0 without any drift
    await asyncio.sleep(0.5)
    drift = await timer.receive()
    assert drift == pytest.approx(timedelta(seconds=0.0))
    assert event_loop.time() == pytest.approx(1.0)


class _StartMethod(enum.Enum):
    RESET = enum.auto()
    RECEIVE = enum.auto()
    READY = enum.auto()
    ASYNC_ITERATOR = enum.auto()


@pytest.mark.parametrize("start_method", list(_StartMethod))
async def test_timer_no_autostart(
    start_method: _StartMethod,
    event_loop: async_solipsism.EventLoop,  # pylint: disable=redefined-outer-name
) -> None:
    """Test a periodic timer when it is not automatically started."""
    timer = Timer(
        timedelta(seconds=1.0),
        TriggerAllMissed(),
        auto_start=False,
    )

    # We sleep some time, less than the interval, and then start the timer and
    # receive from it, since it wasn't automatically started, it should trigger
    # shifted by the sleep time (without any drift)
    await asyncio.sleep(0.5)
    drift: timedelta | None = None
    if start_method == _StartMethod.RESET:
        timer.reset()
        drift = await timer.receive()
    elif start_method == _StartMethod.RECEIVE:
        drift = await timer.receive()
    elif start_method == _StartMethod.READY:
        assert await timer.ready() is True
        drift = timer.consume()
    elif start_method == _StartMethod.ASYNC_ITERATOR:
        async for _drift in timer:
            drift = _drift
            break
    else:
        assert False, f"Unknown start method {start_method}"

    assert drift == pytest.approx(timedelta(seconds=0.0))
    assert event_loop.time() == pytest.approx(1.5)


async def test_timer_trigger_all_missed(
    event_loop: async_solipsism.EventLoop,  # pylint: disable=redefined-outer-name
) -> None:
    """Test a timer using the TriggerAllMissed policy."""
    interval = 1.0
    timer = Timer(timedelta(seconds=interval), TriggerAllMissed())

    # We let the first tick be triggered on time
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Now we let the time pass interval plus a bit more, so we should get
    # a drift, but the next tick should be triggered still at a multiple of the
    # interval because we are using TRIGGER_ALL.
    await asyncio.sleep(interval + 0.1)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 2 + 0.1)
    assert drift == pytest.approx(timedelta(seconds=0.1))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 3)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Now we let the time pass by two times the interval, so we should get
    # a drift of a whole interval and then next tick should be triggered
    # immediately with no drift, because we are still at an interval boundary.
    await asyncio.sleep(2 * interval)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 5)
    assert drift == pytest.approx(timedelta(seconds=interval))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 5)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Finally we let the time pass by 5 times the interval plus some extra
    # delay (even when the tolerance should be irrelevant for this mode),
    # so we should catch up for the 4 missed ticks (the timer should trigger
    # immediately), with the drift of each trigger lowering. The last trigger
    # should have no drift once it catches up.
    extra_delay = 0.1
    await asyncio.sleep(5 * interval + extra_delay)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 10 + extra_delay)
    assert drift == pytest.approx(timedelta(seconds=interval * 4 + extra_delay))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 10 + extra_delay)
    assert drift == pytest.approx(timedelta(seconds=interval * 3 + extra_delay))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 10 + extra_delay)
    assert drift == pytest.approx(timedelta(seconds=interval * 2 + extra_delay))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 10 + extra_delay)
    assert drift == pytest.approx(timedelta(seconds=interval * 1 + extra_delay))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 10 + extra_delay)
    assert drift == pytest.approx(timedelta(seconds=interval * 0 + extra_delay))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 11)
    assert drift == pytest.approx(timedelta(seconds=0.0))


async def test_timer_skip_missed_and_resync(
    event_loop: async_solipsism.EventLoop,  # pylint: disable=redefined-outer-name
) -> None:
    """Test a timer using the SkipMissedAndResync policy."""
    interval = 1.0
    timer = Timer(timedelta(seconds=interval), SkipMissedAndResync())

    # We let the first tick be triggered on time
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Now we let the time pass interval plus a bit more, so we should get
    # a drift, but the next tick should be triggered still at a multiple of the
    # interval because we are using TRIGGER_ALL.
    await asyncio.sleep(interval + 0.1)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 2 + 0.1)
    assert drift == pytest.approx(timedelta(seconds=0.1))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 3)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Now we let the time pass by two times the interval, so we should get
    # a drift of a whole interval and then next tick should an interval later,
    # as the delayed tick will be skipped and the timer will resync.
    await asyncio.sleep(2 * interval)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 5)
    assert drift == pytest.approx(timedelta(seconds=interval))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 6)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Finally we let the time pass by 5 times the interval plus some extra
    # delay. The timer should fire immediately once with a drift of 4 intervals
    # plus the extra delay, and then it should resync and fire again with no
    # drift, skipping the missed ticks.
    extra_delay = 0.8
    await asyncio.sleep(5 * interval + extra_delay)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 11 + extra_delay)
    assert drift == pytest.approx(timedelta(seconds=interval * 4 + extra_delay))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 12)
    assert drift == pytest.approx(timedelta(seconds=0.0))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 13)
    assert drift == pytest.approx(timedelta(seconds=0.0))


async def test_timer_skip_missed_and_drift(
    event_loop: async_solipsism.EventLoop,  # pylint: disable=redefined-outer-name
) -> None:
    """Test a timer using the SkipMissedAndDrift policy."""
    interval = 1.0
    tolerance = 0.1
    timer = Timer(
        timedelta(seconds=interval),
        SkipMissedAndDrift(delay_tolerance=timedelta(seconds=tolerance)),
    )

    # We let the first tick be triggered on time
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval)
    assert drift == timedelta(seconds=0.0)

    # Now we let the time pass by the interval plus the tolerance so the drift
    # should be the tolerance and the next tick should be triggered still at
    # a multiple of the interval.
    await asyncio.sleep(interval + tolerance)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 2 + tolerance)
    assert drift == pytest.approx(timedelta(seconds=tolerance))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 3)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Now we let the time pass the interval plus two times the tolerance. Now
    # the timer should start to drift, and the next tick should be triggered at
    # a multiple of the interval plus the shift of two times the tolerance.
    await asyncio.sleep(interval + tolerance * 2)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 4 + tolerance * 2)
    assert drift == pytest.approx(timedelta(seconds=tolerance * 2))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 5 + tolerance * 2)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Now we let the time pass by two times the interval, so we should missed
    # one tick (the tick at time = 6 + tolerance * 2) and the next tick should
    # still be triggered at a multiple of the interval plus the shift of two
    # times the tolerance because the current trigger time was still aligned
    # to the shifted interval.
    await asyncio.sleep(2 * interval)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 7 + tolerance * 2)
    assert drift == pytest.approx(timedelta(seconds=interval))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 8 + tolerance * 2)
    assert drift == pytest.approx(timedelta(seconds=0.0))

    # Finally we let the time pass by 5 times the interval plus a tiny bit more
    # than the tolerance, so we should missed 4 ticks (the ticks at times 9+,
    # 10+, 11+ and 12+). The current trigger is also delayed more than the
    # tolerance, so the next tick should accumulate the drift again.
    await asyncio.sleep(5 * interval + tolerance + 0.001)
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 13 + tolerance * 3 + 0.001)
    assert drift == pytest.approx(timedelta(seconds=interval * 4 + tolerance + 0.001))
    drift = await timer.receive()
    assert event_loop.time() == pytest.approx(interval * 14 + tolerance * 3 + 0.001)
    assert drift == pytest.approx(timedelta(seconds=0.0))
