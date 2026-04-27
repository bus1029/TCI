from __future__ import annotations

from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
import time
import uuid

import pytest

from tci.api.routes import github_webhooks, gitlab_webhooks


class _ConcurrentAccessDetector:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    @contextmanager
    def enter(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("concurrent rate limiter mutation")
        try:
            time.sleep(0.001)
            yield
        finally:
            self._lock.release()


class _GuardedDeque:
    def __init__(self, detector: _ConcurrentAccessDetector) -> None:
        self._detector = detector
        self._items: list[float] = []

    def __bool__(self) -> bool:
        with self._detector.enter():
            return bool(self._items)

    def __getitem__(self, index: int) -> float:
        with self._detector.enter():
            return self._items[index]

    def __len__(self) -> int:
        with self._detector.enter():
            return len(self._items)

    def append(self, value: float) -> None:
        with self._detector.enter():
            self._items.append(value)

    def popleft(self) -> float:
        with self._detector.enter():
            return self._items.pop(0)


class _GuardedOrderedDict:
    def __init__(self, detector: _ConcurrentAccessDetector) -> None:
        self._detector = detector
        self._items: OrderedDict[object, object] = OrderedDict()

    def clear(self) -> None:
        self._items.clear()

    def get(self, key, default=None):
        with self._detector.enter():
            return self._items.get(key, default)

    def items(self):
        with self._detector.enter():
            return list(self._items.items())

    def move_to_end(self, key) -> None:
        with self._detector.enter():
            self._items.move_to_end(key)

    def pop(self, key, default=None):
        with self._detector.enter():
            return self._items.pop(key, default)

    def popitem(self, last=True):
        with self._detector.enter():
            return self._items.popitem(last=last)

    def __contains__(self, key) -> bool:
        with self._detector.enter():
            return key in self._items

    def __getitem__(self, key):
        with self._detector.enter():
            return self._items[key]

    def __setitem__(self, key, value) -> None:
        with self._detector.enter():
            self._items[key] = value

    def __len__(self) -> int:
        with self._detector.enter():
            return len(self._items)


@pytest.mark.parametrize(
    ("module", "allow_name", "connection_store_name", "source_store_name"),
    [
        (
            github_webhooks,
            "_allow_github_webhook_request",
            "_github_webhook_connection_request_times",
            "_github_webhook_source_request_times",
        ),
        (
            gitlab_webhooks,
            "_allow_gitlab_webhook_request",
            "_gitlab_webhook_connection_request_times",
            "_gitlab_webhook_source_request_times",
        ),
    ],
)
def test_in_memory_webhook_rate_limiter_serializes_concurrent_mutation(
    monkeypatch,
    module,
    allow_name: str,
    connection_store_name: str,
    source_store_name: str,
) -> None:
    detector = _ConcurrentAccessDetector()
    monkeypatch.setattr(
        module,
        connection_store_name,
        _GuardedOrderedDict(detector),
    )
    monkeypatch.setattr(
        module,
        source_store_name,
        _GuardedOrderedDict(detector),
    )
    monkeypatch.setattr(module, "deque", lambda: _GuardedDeque(detector))
    connection_id = uuid.uuid4()
    allow = getattr(module, allow_name)

    def invoke(index: int) -> bool:
        return allow(
            connection_id=connection_id,
            source_key="proxy",
            now_monotonic=100.0 + (index * 0.001),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(invoke, range(16)))

    assert len(results) == 16
    assert all(isinstance(result, bool) for result in results)


@pytest.mark.parametrize(
    ("module", "allow_name", "source_store_name"),
    [
        (
            github_webhooks,
            "_allow_github_webhook_request",
            "_github_webhook_source_request_times",
        ),
        (
            gitlab_webhooks,
            "_allow_gitlab_webhook_request",
            "_gitlab_webhook_source_request_times",
        ),
    ],
)
def test_in_memory_webhook_rate_limiter_prunes_expired_source_buckets(
    module,
    allow_name: str,
    source_store_name: str,
) -> None:
    source_store = getattr(module, source_store_name)
    source_store.clear()
    source_store["198.51.100.1"] = deque([1.0])

    assert getattr(module, allow_name)(
        connection_id=uuid.uuid4(),
        source_key="198.51.100.2",
        now_monotonic=10_000.0,
    )

    assert "198.51.100.1" not in source_store


@pytest.mark.parametrize(
    ("module", "allow_name", "connection_store_name", "source_store_name", "max_name"),
    [
        (
            github_webhooks,
            "_allow_github_webhook_request",
            "_github_webhook_connection_request_times",
            "_github_webhook_source_request_times",
            "GITHUB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS",
        ),
        (
            gitlab_webhooks,
            "_allow_gitlab_webhook_request",
            "_gitlab_webhook_connection_request_times",
            "_gitlab_webhook_source_request_times",
            "GITLAB_WEBHOOK_RATE_LIMIT_MAX_SOURCE_REQUESTS",
        ),
    ],
)
def test_in_memory_webhook_rate_limiter_caps_shared_source_across_connections(
    monkeypatch,
    module,
    allow_name: str,
    connection_store_name: str,
    source_store_name: str,
    max_name: str,
) -> None:
    getattr(module, connection_store_name).clear()
    getattr(module, source_store_name).clear()
    monkeypatch.setattr(module, max_name, 2)
    allow = getattr(module, allow_name)

    assert allow(
        connection_id=uuid.uuid4(),
        source_key="proxy",
        now_monotonic=100.0,
    )
    assert allow(
        connection_id=uuid.uuid4(),
        source_key="proxy",
        now_monotonic=101.0,
    )
    assert not allow(
        connection_id=uuid.uuid4(),
        source_key="proxy",
        now_monotonic=102.0,
    )
    assert allow(
        connection_id=uuid.uuid4(),
        source_key="proxy",
        now_monotonic=200.0,
    )
