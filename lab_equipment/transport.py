"""VISA transport helpers.

Centralizes how a pyVISA session is opened so the instrument driver classes
stay free of connection details. Instruments are addressed by host (IP or
hostname); the resource string is built here.
"""

from __future__ import annotations

import logging
from typing import Any

import pyvisa

logger = logging.getLogger(__name__)

#: Default VISA backend. ``@py`` is the pure-Python PyVISA-py backend, which
#: needs no NI-VISA install and speaks TCPIP INSTR (VXI-11) and raw SOCKET.
DEFAULT_BACKEND = "@py"

#: Default raw-socket port for Siglent SCPI-over-TCP instruments.
DEFAULT_SOCKET_PORT = 5025

#: Default I/O timeout in milliseconds.
DEFAULT_TIMEOUT_MS = 5000


def build_resource_string(
    host: str,
    *,
    socket: bool = False,
    socket_port: int = DEFAULT_SOCKET_PORT,
) -> str:
    """Build a pyVISA resource string for a LAN instrument.

    Args:
        host: Instrument IP address or hostname.
        socket: If True, use a raw TCP socket
            (``TCPIP::<host>::<port>::SOCKET``) instead of VXI-11
            (``TCPIP::<host>::INSTR``). The raw socket is a useful fallback
            for firmware that is unreliable over VXI-11.
        socket_port: Raw-socket port (only used when ``socket`` is True).

    Returns:
        A VISA resource string.
    """
    if not host:
        raise ValueError("host must be a non-empty IP address or hostname")
    if socket:
        return f"TCPIP::{host}::{socket_port}::SOCKET"
    return f"TCPIP::{host}::INSTR"


def get_resource_manager(
    backend: str = DEFAULT_BACKEND,
) -> pyvisa.ResourceManager:
    """Return a pyVISA ResourceManager for the given backend."""
    return pyvisa.ResourceManager(backend)


def open_session(
    resource: str,
    *,
    resource_manager: pyvisa.ResourceManager | None = None,
    backend: str = DEFAULT_BACKEND,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    read_termination: str | None = "\n",
    write_termination: str | None = "\n",
    **open_kwargs: Any,
) -> pyvisa.resources.MessageBasedResource:
    """Open a pyVISA session for ``resource``.

    Args:
        resource: A VISA resource string (see :func:`build_resource_string`).
        resource_manager: An existing ResourceManager to reuse. If None, one
            is created for ``backend``.
        backend: VISA backend, used only when ``resource_manager`` is None.
        timeout_ms: I/O timeout in milliseconds.
        read_termination: Read terminator (``"\\n"`` suits Siglent SCPI).
        write_termination: Write terminator.
        **open_kwargs: Passed through to ``ResourceManager.open_resource``.

    Returns:
        An open message-based pyVISA resource.
    """
    rm = resource_manager or get_resource_manager(backend)
    logger.debug("Opening VISA resource %s", resource)
    session = rm.open_resource(resource, **open_kwargs)
    session.timeout = timeout_ms
    if read_termination is not None:
        session.read_termination = read_termination
    if write_termination is not None:
        session.write_termination = write_termination
    return session


def resolve_labgrid_session(
    target_or_driver: Any,
) -> pyvisa.resources.MessageBasedResource:
    """Extract an open pyVISA session from a labgrid target or driver.

    Accepts either:
      * a labgrid ``Target`` (its ``PyVISADriver`` is looked up), or
      * a labgrid ``PyVISADriver`` instance, or
      * an already-open pyVISA resource (returned unchanged).

    The labgrid driver owns the session lifecycle, so instruments built from
    it should not close it.
    """
    # Already a pyVISA resource: use as-is.
    if hasattr(target_or_driver, "write") and hasattr(
        target_or_driver, "query"
    ):
        return target_or_driver
    # A labgrid PyVISADriver exposes get_session().
    if hasattr(target_or_driver, "get_session"):
        return target_or_driver.get_session()
    # A labgrid Target: fetch its PyVISADriver, then the session.
    if hasattr(target_or_driver, "get_driver"):
        driver = target_or_driver.get_driver("PyVISADriver")
        return driver.get_session()
    raise TypeError(
        "Expected a labgrid Target, a PyVISADriver, or an open pyVISA "
        f"resource; got {type(target_or_driver)!r}"
    )
