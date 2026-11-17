"""Persistent telnet client for NAD receivers (e.g. T758).

The receiver pushes every change (``Main.Volume=-45``) on the open connection
and answers queries the same way, so lines are parsed by key instead of being
matched to the command that was sent. A periodic poll is the backstop and the
liveness check: no data for a while means the connection is dead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
import re

_LOGGER = logging.getLogger(__name__)

LINE_RE = re.compile(r"^(Main\.[A-Za-z0-9.]+)=(.*)$")
POLL_KEYS = ("Main.Power", "Main.Mute", "Main.Volume", "Main.Source")
CONNECT_TIMEOUT = 5
POLL_INTERVAL = 30
# Every poll gets an answer, so silence this long means a dead link
STALE_AFTER = POLL_INTERVAL * 3
RECONNECT_MIN = 5
RECONNECT_MAX = 60


class NadClient:
    """Keeps one telnet connection open and mirrors the receiver's state."""

    def __init__(
        self,
        host: str,
        port: int,
        on_change: Callable[[], None],
    ) -> None:
        self.host = host
        self.port = port
        self.state: dict[str, str] = {}
        self.connected = False
        self._on_change = on_change
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._run())

    async def stop(self) -> None:
        self._on_change = lambda: None  # the entity is going away
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def send(self, cmd: str) -> None:
        """Send a command (``Main.Power=On``) or query (``Main.Power?``)."""
        if not self._writer:
            _LOGGER.warning("NAD %s not connected, dropped %s", self.host, cmd)
            return
        _LOGGER.debug("NAD %s send %s", self.host, cmd)
        self._writer.write(f"\r{cmd}\r".encode())
        await self._writer.drain()

    async def query_all(self) -> None:
        for key in POLL_KEYS:
            await self.send(f"{key}?")

    async def _run(self) -> None:
        delay = RECONNECT_MIN
        while True:
            try:
                await self._session()
                delay = RECONNECT_MIN
            except asyncio.CancelledError:
                self._close()
                raise
            except (OSError, asyncio.TimeoutError, ConnectionError) as err:
                _LOGGER.debug("NAD %s connection error: %s", self.host, err)
            self._close()
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _session(self) -> None:
        loop = asyncio.get_running_loop()
        reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
        )
        _LOGGER.debug("NAD %s connected", self.host)
        poller = loop.create_task(self._poll())
        try:
            buf = ""
            while True:
                data = await asyncio.wait_for(reader.read(1024), STALE_AFTER)
                if not data:
                    raise ConnectionError("closed by receiver")
                buf += data.decode(errors="replace")
                *lines, buf = re.split(r"[\r\n]", buf)
                if self._parse(lines) or not self.connected:
                    self.connected = True
                    self._on_change()
        finally:
            poller.cancel()

    async def _poll(self) -> None:
        # A failed write surfaces as a read timeout in _session, which reconnects
        with contextlib.suppress(OSError, ConnectionError):
            while True:
                await self.query_all()
                await asyncio.sleep(POLL_INTERVAL)

    def _parse(self, lines: list[str]) -> bool:
        changed = False
        for line in lines:
            match = LINE_RE.match(line.strip())
            if not match:
                continue
            key, value = match.groups()
            if self.state.get(key) != value:
                self.state[key] = value
                changed = True
        return changed

    def _close(self) -> None:
        if self._writer:
            self._writer.close()
            self._writer = None
        if self.connected:
            self.connected = False
            self._on_change()
