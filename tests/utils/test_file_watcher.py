# License: MIT
# Copyright © 2022 Frequenz Energy-as-a-Service GmbH

"""Tests for `channel.FileWatcher`."""

from __future__ import annotations

import pathlib
from collections.abc import AsyncGenerator, Iterator, Sequence
from typing import Any
from unittest import mock

import hypothesis
import hypothesis.strategies as st
import pytest
from watchfiles import Change
from watchfiles.main import FileChange

from frequenz.channels.util import FileWatcher


class _FakeAwatch:
    """Fake awatch class to mock the awatch function."""

    def __init__(self, changes: Sequence[FileChange] = ()) -> None:
        """Create a `_FakeAwatch` instance.

        Args:
            changes: A sequence of file changes to be returned by the fake awatch
                function.
        """
        self.changes: Sequence[FileChange] = changes

    async def fake_awatch(
        self, *paths: str, **kwargs: Any  # pylint: disable=unused-argument
    ) -> AsyncGenerator[set[FileChange], None]:
        """Fake awatch function.

        Args:
            paths: Paths to watch.
            kwargs: Keyword arguments to pass to the awatch function.
        """
        for change in self.changes:
            yield {change}


@pytest.fixture
def fake_awatch() -> Iterator[_FakeAwatch]:
    """Fixture to mock the awatch function."""
    fake = _FakeAwatch()
    with mock.patch(
        "frequenz.channels.util._file_watcher.awatch",
        autospec=True,
        side_effect=fake.fake_awatch,
    ):
        yield fake


async def test_file_watcher_receive_updates(
    fake_awatch: _FakeAwatch,  # pylint: disable=redefined-outer-name
) -> None:
    """Test the file watcher receive the expected events."""
    filename = "test-file"
    changes = (
        (Change.added, filename),
        (Change.deleted, filename),
        (Change.modified, filename),
    )
    fake_awatch.changes = changes
    file_watcher = FileWatcher(paths=[filename])

    for change in changes:
        recv_changes = await file_watcher.receive()
        event_type = FileWatcher.EventType(change[0])
        path = pathlib.Path(change[1])
        assert recv_changes == FileWatcher.Event(type=event_type, path=path)


@hypothesis.given(event_types=st.sets(st.sampled_from(FileWatcher.EventType)))
async def test_file_watcher_filter_events(
    event_types: set[FileWatcher.EventType],
) -> None:
    """Test the file watcher events filtering."""
    good_path = "good-file"

    # We need to reset the mock explicitly because hypothesis runs all the produced
    # inputs in the same context.
    with mock.patch(
        "frequenz.channels.util._file_watcher.awatch", autospec=True
    ) as awatch_mock:
        file_watcher = FileWatcher(paths=[good_path], event_types=event_types)

        filter_events = file_watcher._filter_events  # pylint: disable=protected-access

        assert awatch_mock.mock_calls == [
            mock.call(
                pathlib.Path(good_path), stop_event=mock.ANY, watch_filter=filter_events
            )
        ]
        for event_type in FileWatcher.EventType:
            assert filter_events(event_type.value, good_path) == (
                event_type in event_types
            )
