"""pLCM transport import with graceful fallback.

Provides pLCMTransport when dimos is available, or None as a stub
for testing environments.
"""

try:
    from dimos.core.transport import pLCMTransport
except (ImportError, OSError):
    try:
        from dimos.dimos.core.transport import pLCMTransport  # type: ignore[no-redef]
    except (ImportError, OSError):
        pLCMTransport = None  # type: ignore[assignment, misc]
