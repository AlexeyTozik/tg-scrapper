import argparse
import json
import unittest
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

from telethon import errors

from tg_scrapper.export_messages import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_SLEEP,
    DEFAULT_HISTORY_WAIT,
    ExportConfig,
    ExportRuntimeOptions,
    build_iter_messages_kwargs,
    iter_history_messages,
    resolve_runtime_options,
)
from tg_scrapper.telegram_export import serialize_message


def make_config(**overrides: object) -> ExportConfig:
    values: dict[str, object] = {
        "batch_size": DEFAULT_BATCH_SIZE,
        "history_wait": DEFAULT_HISTORY_WAIT,
        "batch_sleep": DEFAULT_BATCH_SLEEP,
        "max_messages": 0,
        "channel": "x",
        "session": "s",
        "out": "o",
        "state": "st",
    }
    values.update(overrides)
    return ExportConfig.from_args(argparse.Namespace(**values))


class ResolveRuntimeOptionsTests(unittest.TestCase):
    def test_default_runtime_is_fast_and_takeout_enabled(self) -> None:
        runtime = resolve_runtime_options(make_config())
        self.assertEqual(
            runtime,
            ExportRuntimeOptions(
                batch_size=DEFAULT_BATCH_SIZE,
                history_wait=DEFAULT_HISTORY_WAIT,
                batch_sleep=DEFAULT_BATCH_SLEEP,
                use_takeout=True,
            ),
        )

    def test_explicit_overrides_win_over_defaults(self) -> None:
        runtime = resolve_runtime_options(
            make_config(
                batch_size=321,
                history_wait=0.75,
                batch_sleep=0.25,
            )
        )
        self.assertEqual(
            runtime,
            ExportRuntimeOptions(
                batch_size=321,
                history_wait=0.75,
                batch_sleep=0.25,
                use_takeout=True,
            ),
        )


class BuildIterMessagesKwargsTests(unittest.TestCase):
    def test_builds_expected_iter_messages_kwargs(self) -> None:
        kwargs = build_iter_messages_kwargs("entity", limit_left=123, min_id=456, history_wait=0.0)
        self.assertEqual(
            kwargs,
            {
                "entity": "entity",
                "limit": 123,
                "reverse": True,
                "min_id": 456,
                "wait_time": 0.0,
            },
        )


class SerializeMessageTests(unittest.TestCase):
    def test_serializes_action_payload_with_bytes(self) -> None:
        class FakeAction:
            def to_dict(self) -> dict[str, object]:
                return {
                    "_": "MessageActionPaymentSentMe",
                    "payload": b"\x00\xff",
                    "nested": {"when": datetime(2026, 1, 1, tzinfo=UTC)},
                }

        message = SimpleNamespace(
            id=1,
            date=datetime(2026, 1, 2, tzinfo=UTC),
            message=None,
            raw_text=None,
            sender_id=10,
            chat_id=-100,
            views=None,
            forwards=None,
            replies=None,
            reply_to=None,
            post_author=None,
            grouped_id=None,
            media=None,
            action=FakeAction(),
            buttons=None,
        )

        row = serialize_message(message)

        json.dumps(row)
        self.assertEqual(row["action_type"], "FakeAction")
        self.assertEqual(row["action"]["payload"], "00ff")
        self.assertEqual(row["action"]["nested"]["when"], "2026-01-01T00:00:00+00:00")


class FakeTakeoutContext:
    def __init__(self, messages: list[int]) -> None:
        self.messages = messages
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeTakeoutContext":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    async def iter_messages(self, **kwargs: object) -> AsyncIterator[int]:
        self.calls.append(kwargs)
        for message in self.messages:
            yield message


class DelayedTakeoutContext:
    async def __aenter__(self) -> "DelayedTakeoutContext":
        raise errors.TakeoutInitDelayError(request=None, capture=7)

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class PendingTakeoutContext:
    async def __aenter__(self) -> "PendingTakeoutContext":
        raise ValueError("Can't send a takeout request while another takeout is pending")

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class FakeClient:
    def __init__(self, *, messages: list[int], takeout_context: object | None = None) -> None:
        self.messages = messages
        self.calls: list[dict[str, object]] = []
        self.takeout_context = takeout_context
        self.takeout_calls: list[dict[str, object]] = []

    async def iter_messages(self, **kwargs: object) -> AsyncIterator[int]:
        self.calls.append(kwargs)
        for message in self.messages:
            yield message

    def takeout(self, **kwargs: object) -> object:
        self.takeout_calls.append(kwargs)
        if self.takeout_context is None:
            raise AssertionError("takeout() should not be called")
        return self.takeout_context


class IterHistoryMessagesTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_normal_client_when_takeout_disabled(self) -> None:
        client = FakeClient(messages=[1, 2, 3])
        runtime = ExportRuntimeOptions(batch_size=1, history_wait=0.5, batch_sleep=0.0, use_takeout=False)

        result = [
            message
            async for message in iter_history_messages(
                client,
                "entity",
                limit_left=10,
                min_id=99,
                runtime=runtime,
            )
        ]

        self.assertEqual(result, [1, 2, 3])
        self.assertEqual(client.takeout_calls, [])
        self.assertEqual(client.calls[0]["wait_time"], 0.5)
        self.assertEqual(client.calls[0]["min_id"], 99)

    async def test_uses_takeout_when_enabled(self) -> None:
        takeout = FakeTakeoutContext(messages=[4, 5])
        client = FakeClient(messages=[1, 2, 3], takeout_context=takeout)
        runtime = ExportRuntimeOptions(batch_size=1, history_wait=0.0, batch_sleep=0.0, use_takeout=True)

        result = [
            message
            async for message in iter_history_messages(
                client,
                "entity",
                limit_left=None,
                min_id=123,
                runtime=runtime,
            )
        ]

        self.assertEqual(result, [4, 5])
        self.assertEqual(client.calls, [])
        self.assertEqual(client.takeout_calls, [{"channels": True, "megagroups": True}])
        self.assertEqual(takeout.calls[0]["wait_time"], 0.0)
        self.assertEqual(takeout.calls[0]["min_id"], 123)

    async def test_falls_back_to_normal_client_when_takeout_is_delayed(self) -> None:
        client = FakeClient(messages=[7, 8], takeout_context=DelayedTakeoutContext())
        runtime = ExportRuntimeOptions(batch_size=1, history_wait=0.25, batch_sleep=0.0, use_takeout=True)

        result = [
            message
            async for message in iter_history_messages(
                client,
                "entity",
                limit_left=50,
                min_id=77,
                runtime=runtime,
            )
        ]

        self.assertEqual(result, [7, 8])
        self.assertEqual(client.takeout_calls, [{"channels": True, "megagroups": True}])
        self.assertEqual(client.calls[0]["limit"], 50)
        self.assertEqual(client.calls[0]["wait_time"], 0.25)

    async def test_falls_back_to_normal_client_when_takeout_is_pending(self) -> None:
        client = FakeClient(messages=[9, 10], takeout_context=PendingTakeoutContext())
        runtime = ExportRuntimeOptions(batch_size=1, history_wait=0.1, batch_sleep=0.0, use_takeout=True)

        result = [
            message
            async for message in iter_history_messages(
                client,
                "entity",
                limit_left=25,
                min_id=88,
                runtime=runtime,
            )
        ]

        self.assertEqual(result, [9, 10])
        self.assertEqual(client.takeout_calls, [{"channels": True, "megagroups": True}])
        self.assertEqual(client.calls[0]["limit"], 25)
        self.assertEqual(client.calls[0]["min_id"], 88)


if __name__ == "__main__":
    unittest.main()
