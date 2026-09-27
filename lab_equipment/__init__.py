"""lab_equipment: pyVISA/SCPI API for Siglent bench instruments.

Public API::

    from lab_equipment import SPD3303X, SDG1062X, SDM3065X

    # direct (host from your own config / env):
    psu = SPD3303X.from_ip(os.environ["LAB_EQUIPMENT_PSU_HOST"])

    # or via the DI container (reads env vars for you):
    from lab_equipment import build_container
    container = build_container()
    dmm = container.dmm()

    # or from an existing labgrid target/driver:
    awg = SDG1062X.from_labgrid(target)
"""

from .containers import LabEquipment, build_container
from .multimeter import SDM3065X
from .power_supply import SPD3303X
from .scpi_instrument import InstrumentError, ScpiInstrument
from .waveform_generator import SDG1062X

__all__ = [
    "ScpiInstrument",
    "InstrumentError",
    "SPD3303X",
    "SDG1062X",
    "SDM3065X",
    "LabEquipment",
    "build_container",
]

__version__ = "0.1.0"
