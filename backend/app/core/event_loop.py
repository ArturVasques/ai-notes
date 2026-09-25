"""
Windows-safe asyncio event loop selection.

psycopg cannot run in async mode on Windows' default ProactorEventLoop:

    Psycopg cannot use the 'ProactorEventLoop' to run in async mode

Every entry point that opens the asynchronous database pool must therefore
run on SelectorEventLoop instead. uvicorn builds its loop through a
loop_factory rather than an event-loop *policy*, so setting a policy in
main.py is not sufficient on its own.

Used by:
- uvicorn's `--loop` option, as an import string:
  `uvicorn main:app --loop app.core.event_loop:loop_factory`.
  A custom `--loop` import string is used by uvicorn as a ready-to-call,
  zero-argument loop factory (see uvicorn.config.Config.get_loop_factory),
  which is exactly the shape `loop_factory` below has.
- any script that opens the pool, passed directly as
  `asyncio.run(coro(), loop_factory=loop_factory)`.
- tests/integration/conftest.py, via configure_windows_event_loop_policy(),
  so pytest-asyncio creates its loops the same way.
"""

import asyncio
import sys


def loop_factory() -> asyncio.AbstractEventLoop:
    """Return a new event loop that supports psycopg's async mode."""

    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()

    return asyncio.new_event_loop()


def configure_windows_event_loop_policy() -> None:
    """
    Force every default-policy loop creation to use SelectorEventLoop.

    Needed for pytest-asyncio, which creates its event loops through the
    active event loop policy rather than through `loop_factory` above.
    """

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
