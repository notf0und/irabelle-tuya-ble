# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog],
and this project adheres to [Semantic Versioning].

## [0.1.11] - 2026-11-07

### Fixed

- D-Bus connection leak that eventually broke **all** Bluetooth in Home
  Assistant. bleak's BlueZ backend opens a dedicated system D-Bus connection
  for every connection session and only closes it in `disconnect()` — also
  when the device has already dropped the connection itself. The integration
  skipped `disconnect()` for clients that were no longer connected: when a
  device disconnected unexpectedly (`_disconnected` only forgot the client),
  in `_release_client` and in `_execute_disconnect`. One D-Bus connection
  leaked per dropped session; after about a day Home Assistant held 245 of
  the 256 allowed (`max_connections_per_user`), dbus-daemon refused every new
  connection, and every BLE connect failed instantly with `EOFError` — a
  Fingerbot press did nothing. All paths now go through `_close_client`, which
  always calls `disconnect()`.
- Only one reconnect loop per device. Unexpected disconnects and failed sends
  each started their own `_reconnect` chain, and each chain re-scheduled
  itself on failure; `_reconnect` now retries in its own task and new requests
  join the running one (`_schedule_reconnect`).
- Failed connection attempts in `_ensure_connected` back off (0.5 s, growing
  to 5 s) instead of retrying back to back; an unreachable device was retried
  several times a second.

### Added

- `tests/test_connection_cleanup.py` (no Home Assistant needed:
  `python -m pytest tests/` with bleak, bleak-retry-connector, pycryptodome
  and pytest-asyncio).

## [0.1.10] - 2026-10-11

### Fixed

- Reconnect no longer leaks live BLE clients. Every failed attempt in
  `_ensure_connected` used to drop the reference (`self._client = None`) and
  open a new connection, leaving the previous client connected *and* still
  subscribed to `CHARACTERISTIC_NOTIFY`. Each leaked client made the device's
  notifications arrive one extra time, so the packet sequence numbers advanced
  too far and the reassembly could never re-sync — the integration then sat
  there timing out on every request while the entities kept their last values,
  and any button press blocked behind the connect lock. The old client is now
  stopped and disconnected (`_release_client`) before each retry.
- A duplicate/out-of-range fragment no longer wipes the partial response in
  `_notification_handler`; repeats are ignored, and only a genuine restart at
  packet 0 starts the assembly over.

## [0.1.0] - 2023-04-22

- Initial release


## [0.1.1] - 2023-04-26

### Added

- Added new product_id for Fingerbot Plus (#1)

### Fixed

- Fixed problem in options flow.

### Changed

- Updated strings.json


## [0.1.2] - 2023-04-26

### Changed

- Changed a way to obtain device credentials from Tuya IOT cloud, possible fix to (#2)

## [0.1.4] - 2023-04-30

### Added

- Added support of CUBETOUCH 1s, thanks @damiano75
- Added new product_ids for Fingerbot.
- Added new product_ids for Fingerbot Plus.
- First attempt to support Smart Lock device.

### Fixed

- Fixed possible disconnect of BLE device.

## [0.1.5] - 2023-06-01

### Added

- Added new product_ids for Fingerbot.
- Added event "fingerbot_button_pressed" which is fired on Fingerbot Plus touch button press.
- First attempt to add support of climate entity.

## [0.1.6] - 2023-06-01

### Added

- Added new product_ids for Fingerbot and Fingerbot Plus.

### Changed

- Updated sources to conform Python 3.11

## [0.1.7] - 2023-06-01

### Added

- Added new product_ids.
- Added full support of BLE TRV provided by @forabi
- Added support of programming mode for Fingerbot Plus, thanks @redphx for information.

### Changed

- Improved connection stability.

## [0.1.8] - 2023-07-09

### Added

- Added support of 'Irrigation computer', thanks to @SanMiggel.
- Added new product_ids for Smart locks, thanks to @drewpo28.

### Changed

- Connection to the device is postponed now. Previously some out of range device might prevents HA from fully booting.
- Improved connection stability.

## [0.1.9] - 2025-12-23

### Added

- Fixed integration with Home Assistant 2025.12
