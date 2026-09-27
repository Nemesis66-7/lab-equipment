"""Base class shared by all SCPI instrument drivers."""

from __future__ import annotations

import logging
from typing import Any

import pyvisa

from .transport import (
    DEFAULT_BACKEND,
    build_resource_string,
    open_session,
    resolve_labgrid_session,
)

logger = logging.getLogger(__name__)


class ScpiInstrument:
    """Common SCPI transport wrapper around a pyVISA session.

    A driver is created from a host (:meth:`from_ip`), an explicit resource
    string (:meth:`from_resource`), a labgrid target/driver
    (:meth:`from_labgrid`), or an already-open session (the constructor).

    Instances are context managers; exiting closes the session only when this
    object owns it (i.e. not for labgrid-provided sessions).
    """

    #: Default I/O timeout for this instrument class, in milliseconds.
    default_timeout_ms = 5000

    def __init__(
        self,
        session: pyvisa.resources.MessageBasedResource,
        *,
        owns_session: bool = True,
    ) -> None:
        self._session = session
        self._owns_session = owns_session

    # -- construction ----------------------------------------------------

    @classmethod
    def from_resource(
        cls,
        resource: str,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        backend: str = DEFAULT_BACKEND,
        timeout_ms: int | None = None,
        read_termination: str | None = "\n",
        write_termination: str | None = "\n",
        **kwargs: Any,
    ) -> "ScpiInstrument":
        """Build a driver from a VISA resource string."""
        session = open_session(
            resource,
            resource_manager=resource_manager,
            backend=backend,
            timeout_ms=timeout_ms or cls.default_timeout_ms,
            read_termination=read_termination,
            write_termination=write_termination,
        )
        return cls(session, owns_session=True, **kwargs)

    @classmethod
    def from_ip(
        cls,
        host: str,
        *,
        socket: bool = False,
        socket_port: int = 5025,
        **kwargs: Any,
    ) -> "ScpiInstrument":
        """Build a driver from a host (IP or hostname).

        Transport keywords (``resource_manager``, ``backend``, ``timeout_ms``,
        terminations) and any instrument-specific keywords are forwarded to
        :meth:`from_resource`.
        """
        resource = build_resource_string(
            host, socket=socket, socket_port=socket_port
        )
        return cls.from_resource(resource, **kwargs)

    @classmethod
    def from_labgrid(
        cls, target_or_driver: Any, **kwargs: Any
    ) -> "ScpiInstrument":
        """Build a driver from a labgrid target/driver or open session.

        The labgrid driver owns the session, so it is not closed on exit.
        """
        session = resolve_labgrid_session(target_or_driver)
        return cls(session, owns_session=False, **kwargs)

    # -- low-level I/O ---------------------------------------------------

    @property
    def session(self) -> pyvisa.resources.MessageBasedResource:
        """The underlying pyVISA session."""
        return self._session

    @property
    def timeout_ms(self) -> float:
        return self._session.timeout

    @timeout_ms.setter
    def timeout_ms(self, value: float) -> None:
        self._session.timeout = value

    def write(self, command: str) -> None:
        """Send a command with no response expected."""
        logger.debug("%s <- %s", type(self).__name__, command)
        self._session.write(command)

    def query(self, command: str) -> str:
        """Send a query and return the stripped text response."""
        response = self._session.query(command).strip()
        logger.debug("%s -> %s", type(self).__name__, response)
        return response

    def query_float(self, command: str) -> float:
        """Send a query and return the response parsed as a float."""
        return float(self.query(command))

    # -- common SCPI verbs ----------------------------------------------

    def idn(self) -> str:
        """Return the ``*IDN?`` identification string."""
        return self.query("*IDN?")

    def reset(self) -> None:
        """Reset the instrument (``*RST``)."""
        self.write("*RST")

    def clear_status(self) -> None:
        """Clear status/event registers (``*CLS``)."""
        self.write("*CLS")

    def wait_for_complete(self) -> None:
        """Block until pending operations complete (``*OPC?``)."""
        self.query("*OPC?")

    def get_error(self) -> str:
        """Return the next entry from the error queue (``SYST:ERR?``)."""
        return self.query("SYST:ERR?")

    def raise_on_error(self) -> None:
        """Drain the error queue, raising if any non-zero error is present."""
        errors = []
        for _ in range(32):  # bounded drain to avoid a runaway loop
            entry = self.get_error()
            code = entry.split(",", 1)[0].strip()
            if code in ("0", "+0", '"0"'):
                break
            errors.append(entry)
        if errors:
            raise InstrumentError(
                f"{type(self).__name__} reported errors: {'; '.join(errors)}"
            )

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Close the session if this instrument owns it."""
        if self._owns_session and self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "ScpiInstrument":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class InstrumentError(RuntimeError):
    """Raised when an instrument reports an error via its SCPI error queue."""
