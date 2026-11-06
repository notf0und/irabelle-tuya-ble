"""Connection cleanup in TuyaBLEDevice: every BleakClient must be disconnect()ed.

bleak's BlueZ backend opens a dedicated system D-Bus connection per connection
session and only closes it in BleakClient.disconnect() - also when the device
already dropped the connection. These tests use a fake client that records
whether its D-Bus connection was released.

Run from the repository root:
    python -m pytest tests/ -v
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "tuya_ble"))

from tuya_ble import tuya_ble as tb  # noqa: E402  (inner package, no Home Assistant needed)


class FakeClient:
    """Mimics bleak: the D-Bus connection stays open until disconnect()."""

    def __init__(self, connected=True):
        self.is_connected = connected
        self.bus_open = True
        self.stop_notify_calls = 0
        self.disconnect_calls = 0

    async def stop_notify(self, _char):
        self.stop_notify_calls += 1

    async def disconnect(self):
        self.disconnect_calls += 1
        self.is_connected = False
        self.bus_open = False

    async def start_notify(self, *_args):
        pass


def make_device():
    ble_device = MagicMock()
    ble_device.address = "DC:23:53:55:CC:BD"
    return tb.TuyaBLEDevice(MagicMock(), ble_device)


@pytest.mark.asyncio
async def test_close_client_releases_bus_of_already_disconnected_client():
    dev = make_device()
    client = FakeClient(connected=False)
    await dev._close_client(client)
    assert client.disconnect_calls == 1 and not client.bus_open
    assert client.stop_notify_calls == 0  # nothing to unsubscribe


@pytest.mark.asyncio
async def test_close_client_unsubscribes_and_disconnects_connected_client():
    dev = make_device()
    client = FakeClient(connected=True)
    await dev._close_client(client)
    assert client.stop_notify_calls == 1 and client.disconnect_calls == 1 and not client.bus_open


@pytest.mark.asyncio
async def test_close_client_survives_errors():
    dev = make_device()
    client = FakeClient()

    async def boom():
        raise RuntimeError("bluez went away")

    client.disconnect = boom
    await dev._close_client(client)  # must not raise
    await dev._close_client(None)


@pytest.mark.asyncio
async def test_release_client_disconnects_even_when_not_connected():
    dev = make_device()
    client = FakeClient(connected=False)
    dev._client = client
    await dev._release_client()
    assert dev._client is None and not client.bus_open


@pytest.mark.asyncio
async def test_execute_disconnect_releases_dropped_client():
    dev = make_device()
    client = FakeClient(connected=False)
    dev._client = client
    await dev._execute_disconnect()
    assert dev._client is None and not client.bus_open


@pytest.mark.asyncio
async def test_unexpected_disconnect_releases_client_and_reconnects_once():
    """The leak behind max_connections_per_user: a device-side drop used to
    just forget the client, leaving its D-Bus connection open."""
    dev = make_device()
    started = asyncio.Event()
    calls = 0

    async def fake_reconnect():
        nonlocal calls
        calls += 1
        started.set()
        await asyncio.sleep(3600)  # still "running"

    first = FakeClient(connected=False)
    dev._client = first
    with patch.object(dev, "_reconnect", fake_reconnect):
        dev._disconnected(first)
        second = FakeClient(connected=False)
        dev._disconnected(second)  # another drop while the reconnect is pending
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.sleep(0)
        assert not first.bus_open and not second.bus_open
        assert dev._client is None
        assert calls == 1  # one reconnect loop, not one per event
        dev._reconnect_task.cancel()


@pytest.mark.asyncio
async def test_unexpected_disconnect_of_old_client_keeps_current_client():
    dev = make_device()
    current = FakeClient(connected=True)
    old = FakeClient(connected=False)
    dev._client = current
    with patch.object(dev, "_schedule_reconnect"):
        dev._disconnected(old)
        await asyncio.sleep(0)
    assert dev._client is current and current.bus_open
    assert not old.bus_open


@pytest.mark.asyncio
async def test_ensure_connected_closes_unconnected_client_and_backs_off():
    dev = make_device()
    unconnected = [FakeClient(connected=False), FakeClient(connected=False)]
    returned = list(unconnected)
    sleeps = []

    async def fake_establish(*_args, **_kwargs):
        if returned:
            return returned.pop(0)
        raise tb.BleakNotFoundError()

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 5:
            dev._expected_disconnect = True  # stop the loop
            raise asyncio.CancelledError

    with patch.object(tb, "establish_connection", fake_establish), patch.object(tb.asyncio, "sleep", fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await dev._ensure_connected()
    # clients that came back without a connection still had their D-Bus released
    assert all(not c.bus_open for c in unconnected)
    # failed attempts are spaced out instead of retried back to back
    backoffs = [s for s in sleeps if s >= tb.CONNECT_RETRY_BACKOFF]
    assert backoffs[:3] == [0.5, 1.0, 1.5]
    assert max(backoffs) <= tb.CONNECT_RETRY_BACKOFF_MAX
