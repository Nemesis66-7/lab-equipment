"""Session-scoped pytest fixtures exposing the bench instruments.

Hosts come from environment variables (see :mod:`lab_equipment.config`). A
fixture skips cleanly if its instrument's host is not configured, so a suite
that uses only one instrument need not set the others.

Register via::

    pytest_plugins = ("lab_equipment.fixtures.instruments_fixture",)
"""

from __future__ import annotations

import logging

import pytest

from ..config import (
    ENV_AWG_HOST,
    ENV_DMM_HOST,
    ENV_PSU_HOST,
)
from ..containers import build_container

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def lab_equipment_container():
    """The DI container, configured from the environment."""
    return build_container(require_hosts=False)


@pytest.fixture(scope="session")
def visa_resource_manager(lab_equipment_container):
    """The shared pyVISA ResourceManager."""
    rm = lab_equipment_container.resource_manager()
    yield rm
    try:
        rm.close()
    except Exception:  # pragma: no cover - best-effort teardown
        logger.debug("ResourceManager close failed", exc_info=True)


@pytest.fixture(scope="session")
def bench_psu(lab_equipment_container):
    """Siglent SPD3303X-E power supply. Outputs are forced off on teardown."""
    if not lab_equipment_container.config.psu.host():
        pytest.skip(f"{ENV_PSU_HOST} not set")
    psu = lab_equipment_container.psu()
    try:
        yield psu
    finally:
        try:
            psu.all_off()
        finally:
            psu.close()


@pytest.fixture(scope="session")
def bench_awg(lab_equipment_container):
    """Siglent SDG1062X waveform generator. Outputs off on teardown."""
    if not lab_equipment_container.config.awg.host():
        pytest.skip(f"{ENV_AWG_HOST} not set")
    awg = lab_equipment_container.awg()
    try:
        yield awg
    finally:
        try:
            awg.all_off()
        finally:
            awg.close()


@pytest.fixture(scope="session")
def bench_dmm(lab_equipment_container):
    """Siglent SDM3065X digital multimeter."""
    if not lab_equipment_container.config.dmm.host():
        pytest.skip(f"{ENV_DMM_HOST} not set")
    dmm = lab_equipment_container.dmm()
    try:
        yield dmm
    finally:
        dmm.close()
