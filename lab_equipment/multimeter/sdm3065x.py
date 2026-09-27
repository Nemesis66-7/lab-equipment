"""Driver for the Siglent SDM3065X 6.5-digit digital multimeter."""

from __future__ import annotations

import logging
from statistics import mean

from ..scpi_instrument import ScpiInstrument

logger = logging.getLogger(__name__)

#: SCPI function keywords keyed by a friendly name, for configure()/NPLC.
FUNCTIONS = {
    "dc_voltage": "VOLTage:DC",
    "ac_voltage": "VOLTage:AC",
    "dc_current": "CURRent:DC",
    "ac_current": "CURRent:AC",
    "resistance": "RESistance",
    "fresistance": "FRESistance",
    "frequency": "FREQuency",
    "capacitance": "CAPacitance",
    "temperature": "TEMPerature",
}


class SDM3065X(ScpiInstrument):
    """Siglent SDM3065X digital multimeter.

    ``measure_*`` helpers issue a one-shot ``MEASure?`` (auto-ranging unless a
    range is given). For repeated or averaged readings, use
    :meth:`configure` + :meth:`read`, or the ``average_*`` helpers.
    """

    default_timeout_ms = 10000  # slow functions (e.g. high-NPLC) need headroom

    # -- one-shot measurements ------------------------------------------

    def _measure(
        self,
        func: str,
        range_: float | str | None = None,
        resolution: float | str | None = None,
    ) -> float:
        if resolution is not None and range_ is None:
            raise ValueError("resolution requires an explicit range")
        cmd = f"MEASure:{func}?"
        args = [str(a) for a in (range_, resolution) if a is not None]
        if args:
            cmd += " " + ",".join(args)
        return self.query_float(cmd)

    def measure_dc_voltage(self, range_=None, resolution=None) -> float:
        """Measure DC voltage (volts)."""
        return self._measure("VOLTage:DC", range_, resolution)

    def measure_ac_voltage(self, range_=None, resolution=None) -> float:
        """Measure AC voltage (volts RMS)."""
        return self._measure("VOLTage:AC", range_, resolution)

    def measure_dc_current(self, range_=None, resolution=None) -> float:
        """Measure DC current (amps)."""
        return self._measure("CURRent:DC", range_, resolution)

    def measure_ac_current(self, range_=None, resolution=None) -> float:
        """Measure AC current (amps RMS)."""
        return self._measure("CURRent:AC", range_, resolution)

    def measure_resistance(
        self, four_wire: bool = False, range_=None, resolution=None
    ) -> float:
        """Measure resistance (ohms); ``four_wire`` selects 4-wire sense."""
        func = "FRESistance" if four_wire else "RESistance"
        return self._measure(func, range_, resolution)

    def measure_frequency(self, range_=None, resolution=None) -> float:
        """Measure frequency (hertz)."""
        return self._measure("FREQuency", range_, resolution)

    def measure_capacitance(self, range_=None, resolution=None) -> float:
        """Measure capacitance (farads)."""
        return self._measure("CAPacitance", range_, resolution)

    def measure_temperature(self) -> float:
        """Measure temperature (configured probe units)."""
        return self._measure("TEMPerature")

    # -- configured / averaged reads ------------------------------------

    def configure(self, function: str, range_=None) -> None:
        """Configure the active measurement function.

        Args:
            function: A key from :data:`FUNCTIONS`
                (e.g. ``"dc_voltage"``), or a raw SCPI function keyword.
            range_: Optional range value or ``"AUTO"``.
        """
        scpi = FUNCTIONS.get(function, function)
        cmd = f"CONFigure:{scpi}"
        if range_ is not None:
            cmd += f" {range_}"
        self.write(cmd)

    def set_sample_count(self, count: int) -> None:
        """Set the number of samples taken per trigger."""
        if count < 1:
            raise ValueError("sample count must be >= 1")
        self.write(f"SAMPle:COUNt {count}")

    def set_nplc(self, function: str, nplc: float) -> None:
        """Set integration time in power-line cycles for a function."""
        scpi = FUNCTIONS.get(function, function)
        self.write(f"SENSe:{scpi}:NPLC {nplc}")

    def read(self) -> list[float]:
        """Trigger and return all readings from the configured function."""
        raw = self.query("READ?")
        return [float(v) for v in raw.split(",") if v.strip()]

    def read_one(self) -> float:
        """Trigger and return a single reading from the configured function."""
        return self.read()[0]

    def average(self, function: str, count: int, range_=None) -> float:
        """Configure ``function`` and return the mean of ``count`` samples."""
        self.configure(function, range_)
        self.set_sample_count(count)
        return mean(self.read())
