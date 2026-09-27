"""Environment-driven configuration for the bench instruments.

Instrument hosts are treated as internal information: they are never hardcoded
in source, only read from environment variables (optionally via a git-ignored
``.env`` file). See ``.env.example`` for the variable names.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

#: Environment variable names.
ENV_PSU_HOST = "LAB_EQUIPMENT_PSU_HOST"
ENV_AWG_HOST = "LAB_EQUIPMENT_AWG_HOST"
ENV_DMM_HOST = "LAB_EQUIPMENT_DMM_HOST"
ENV_BACKEND = "LAB_EQUIPMENT_VISA_BACKEND"
ENV_SOCKET = "LAB_EQUIPMENT_SOCKET"
ENV_TIMEOUT_MS = "LAB_EQUIPMENT_TIMEOUT_MS"

_TRUE = {"1", "true", "yes", "on"}


class MissingConfigError(RuntimeError):
    """Raised when a required host environment variable is not set."""


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE


def maybe_load_dotenv(path: str | None = None) -> bool:
    """Load a ``.env`` file if python-dotenv is available.

    Returns True if a file was loaded. Missing python-dotenv is not an error;
    the function simply returns False so env vars set another way still work.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    return load_dotenv(path)


def load_env_config(
    *,
    require_hosts: bool = True,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a config dict from environment variables.

    Args:
        require_hosts: If True, raise :class:`MissingConfigError` when any host
            variable is unset. If False, unset hosts become ``None`` (useful so
            a suite that uses only one instrument does not require all three).
        environ: Mapping to read instead of ``os.environ`` (for tests).

    Returns:
        A dict shaped for ``dependency_injector`` ``Configuration.from_dict``.
    """
    env = os.environ if environ is None else environ

    def host(var: str) -> str | None:
        value = env.get(var) or None
        if require_hosts and not value:
            raise MissingConfigError(
                f"{var} is not set; export it or add it to a .env file"
            )
        return value

    return {
        "psu": {"host": host(ENV_PSU_HOST)},
        "awg": {"host": host(ENV_AWG_HOST)},
        "dmm": {"host": host(ENV_DMM_HOST)},
        "visa": {"backend": env.get(ENV_BACKEND) or "@py"},
        "socket": _as_bool(env.get(ENV_SOCKET), default=False),
        "timeout_ms": int(env.get(ENV_TIMEOUT_MS) or 5000),
    }
