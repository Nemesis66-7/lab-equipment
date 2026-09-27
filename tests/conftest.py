"""Test fixtures backed by the pyvisa-sim backend (no hardware required)."""

from __future__ import annotations

import os

import pyvisa
import pytest
from dependency_injector import providers

from lab_equipment.containers import build_container

SIM_YAML = os.path.join(os.path.dirname(__file__), "sim_instruments.yaml")
SIM_BACKEND = f"{SIM_YAML}@sim"

# Hosts here are the sim resource names (see sim_instruments.yaml), not real
# addresses. They stand in for the LAB_EQUIPMENT_*_HOST env vars.
SIM_ENV = {
    "LAB_EQUIPMENT_PSU_HOST": "psu",
    "LAB_EQUIPMENT_AWG_HOST": "awg",
    "LAB_EQUIPMENT_DMM_HOST": "dmm",
}


@pytest.fixture
def sim_rm():
    rm = pyvisa.ResourceManager(SIM_BACKEND)
    yield rm
    rm.close()


@pytest.fixture
def container(sim_rm):
    """A LabEquipment container wired to the sim backend."""
    c = build_container(environ=SIM_ENV, load_dotenv=False)
    c.resource_manager.override(providers.Object(sim_rm))
    yield c
    c.reset_override()
