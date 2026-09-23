"""
Regression test for the Windows event loop bug.

`uvicorn main:app` without `--reload` used to fail on Windows because uvicorn
builds a ProactorEventLoop there, which psycopg cannot use in async mode.
The shared loop factory must always produce a psycopg-compatible loop.
"""

import asyncio
import sys

from app.core.event_loop import loop_factory


def test_loop_factory_returns_a_usable_loop() -> None:
    loop = loop_factory()

    try:
        assert isinstance(loop, asyncio.AbstractEventLoop)
        assert loop.run_until_complete(asyncio.sleep(0, result="ok")) == "ok"
    finally:
        loop.close()


def test_loop_factory_never_returns_proactor_loop_on_windows() -> None:
    if sys.platform != "win32":
        return

    loop = loop_factory()

    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
        assert not isinstance(loop, asyncio.ProactorEventLoop)
    finally:
        loop.close()
