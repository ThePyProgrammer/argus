# SLAM subprocess transport portability (#7)

The SLAM bridge now checks `zmq.has('ipc')`. It keeps the existing unique IPC
endpoint on supported builds and otherwise binds `tcp://127.0.0.1:*`. ZeroMQ
assigns the port; the bridge passes the resolved endpoint through `--zmq`.
Both the OpenVINS and DSO harnesses already connect to that argument, so their
message format and command-line interface are unchanged. An explicit IPC
endpoint on an unsupported build raises an actionable error before allocating
resources; callers can omit the override or select loopback TCP explicitly.

Binding and process-launch failures close the socket and context. Cleanup only
unlinks IPC files after a successful bind. Sends and receives both have bounded
timeouts, including when a spawned worker never connects.

The original Windows reproduction produced nine failures and two passes in
`tests/slam/test_subprocess_bridge.py`. Portable protocol, timeout, and shutdown
tests now bind loopback TCP. Added regressions cover capability selection,
resolved worker arguments, concurrent endpoint uniqueness, startup failure
cleanup, preservation of an unowned IPC file, and a real Python subprocess
round trip using the SLAM wire format. Two filesystem IPC tests are gated on
transport support; the default IPC selection test runs with a mocked capability.

On November 21, 2026, the complete SLAM suite passed: **122 passed, 2 skipped**
in 22.40 seconds. Command:

```powershell
.venv\Scripts\python.exe -m pytest tests/slam -q -p no:cacheprovider --basetemp=outputs/pytest-ipc-issue7-02
```

Earlier sandbox runs encountered pytest temporary-directory permission errors;
the successful suite ran outside the sandbox. The two skips are the actual IPC
socket cleanup checks, because this build reports no IPC support.

Validation is limited to tests, with no live exploration attempt or new video.
Native OpenVINS/DSO executables and actual IPC transport were not exercised on
this Windows build. Historical exploration notes retain their original suite
exclusions as records of those runs.
