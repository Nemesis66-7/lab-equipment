"""Dependency-injection container wiring instruments from configuration.

This is the composition root: the only place that reads host configuration and
assembles the shared VISA ResourceManager plus one provider per instrument.
The driver classes themselves stay configuration-agnostic, so they remain
usable directly (``SPD3303X.from_ip(...)``) and overridable in tests.
"""

from __future__ import annotations

from typing import Mapping

from dependency_injector import containers, providers

from .config import load_env_config, maybe_load_dotenv
from .multimeter.sdm3065x import SDM3065X
from .power_supply.spd3303x import SPD3303X
from .transport import get_resource_manager
from .waveform_generator.sdg1062x import SDG1062X


class LabEquipment(containers.DeclarativeContainer):
    """Container of bench instruments, wired from :attr:`config`."""

    config = providers.Configuration()

    resource_manager = providers.Singleton(
        get_resource_manager,
        backend=config.visa.backend,
    )

    psu = providers.Singleton(
        SPD3303X.from_ip,
        config.psu.host,
        resource_manager=resource_manager,
        socket=config.socket,
        timeout_ms=config.timeout_ms,
    )

    awg = providers.Singleton(
        SDG1062X.from_ip,
        config.awg.host,
        resource_manager=resource_manager,
        timeout_ms=config.timeout_ms,
    )

    dmm = providers.Singleton(
        SDM3065X.from_ip,
        config.dmm.host,
        resource_manager=resource_manager,
        timeout_ms=config.timeout_ms,
    )


def build_container(
    *,
    require_hosts: bool = False,
    environ: Mapping[str, str] | None = None,
    load_dotenv: bool = True,
) -> LabEquipment:
    """Create and configure a :class:`LabEquipment` container from the env.

    Args:
        require_hosts: Raise if a host env var is missing (default False, so a
            suite using one instrument need not set all three).
        environ: Mapping to read instead of ``os.environ`` (for tests).
        load_dotenv: Attempt to load a ``.env`` file first (no-op if
            python-dotenv is not installed or no file exists).
    """
    if load_dotenv and environ is None:
        maybe_load_dotenv()
    container = LabEquipment()
    container.config.from_dict(
        load_env_config(require_hosts=require_hosts, environ=environ)
    )
    return container
