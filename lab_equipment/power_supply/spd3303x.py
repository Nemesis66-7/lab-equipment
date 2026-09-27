"""Driver for the Siglent SPD3303X-E programmable DC power supply.

Channels 1 and 2 are fully programmable (0-32 V, 0-3.2 A). Channel 3 is a
fixed-preset output; it can be measured and switched but not set via SCPI.
"""

from __future__ import annotations

import logging
from typing import Mapping

import pyvisa

from ..scpi_instrument import ScpiInstrument

logger = logging.getLogger(__name__)

#: Hardware maxima for the SPD3303X-E programmable channels.
CHANNEL_MAX_VOLTAGE = 32.0
CHANNEL_MAX_CURRENT = 3.2

#: Channels that accept programmable voltage/current setpoints.
PROGRAMMABLE_CHANNELS = (1, 2)

#: All channels that can be measured / output-switched.
ALL_CHANNELS = (1, 2, 3)


class TrackMode:
    """``OUTPut:TRACK`` mode codes."""

    INDEPENDENT = 0
    SERIES = 1
    PARALLEL = 2


class SPD3303X(ScpiInstrument):
    """Siglent SPD3303X-E programmable DC power supply.

    Args:
        session: Open pyVISA session (usually built via the factory methods).
        owns_session: Whether closing this object closes the session.
        voltage_limits: Optional per-channel max voltage clamp,
            e.g. ``{1: 14.0, 2: 5.0}``. Requests above the clamp raise before
            anything is sent - use this to protect the DUT. Defaults to the
            hardware maximum for each programmable channel.
        current_limits: Optional per-channel max current clamp, same shape.
    """

    def __init__(
        self,
        session: pyvisa.resources.MessageBasedResource,
        *,
        owns_session: bool = True,
        voltage_limits: Mapping[int, float] | None = None,
        current_limits: Mapping[int, float] | None = None,
    ) -> None:
        super().__init__(session, owns_session=owns_session)
        self._voltage_limits = {
            ch: CHANNEL_MAX_VOLTAGE for ch in PROGRAMMABLE_CHANNELS
        }
        self._current_limits = {
            ch: CHANNEL_MAX_CURRENT for ch in PROGRAMMABLE_CHANNELS
        }
        if voltage_limits:
            self._voltage_limits.update(voltage_limits)
        if current_limits:
            self._current_limits.update(current_limits)

    # -- validation ------------------------------------------------------

    @staticmethod
    def _check_channel(channel: int, allowed=ALL_CHANNELS) -> int:
        if channel not in allowed:
            raise ValueError(
                f"channel must be one of {allowed}, got {channel!r}"
            )
        return channel

    def _check_voltage(self, channel: int, volts: float) -> None:
        limit = self._voltage_limits[channel]
        if not 0.0 <= volts <= limit:
            raise ValueError(
                f"CH{channel} voltage {volts} V out of range "
                f"[0, {limit}] V (safety clamp)"
            )

    def _check_current(self, channel: int, amps: float) -> None:
        limit = self._current_limits[channel]
        if not 0.0 <= amps <= limit:
            raise ValueError(
                f"CH{channel} current {amps} A out of range "
                f"[0, {limit}] A (safety clamp)"
            )

    # -- setpoints -------------------------------------------------------

    def set_voltage(self, channel: int, volts: float) -> None:
        """Set the output voltage setpoint for a programmable channel."""
        self._check_channel(channel, PROGRAMMABLE_CHANNELS)
        self._check_voltage(channel, volts)
        self.write(f"CH{channel}:VOLTage {volts:.3f}")

    def set_current(self, channel: int, amps: float) -> None:
        """Set the current limit for a programmable channel."""
        self._check_channel(channel, PROGRAMMABLE_CHANNELS)
        self._check_current(channel, amps)
        self.write(f"CH{channel}:CURRent {amps:.3f}")

    def apply(self, channel: int, volts: float, amps: float) -> None:
        """Set both voltage and current limit for a channel."""
        self.set_voltage(channel, volts)
        self.set_current(channel, amps)

    def get_set_voltage(self, channel: int) -> float:
        """Return the configured voltage setpoint (not the measured value)."""
        self._check_channel(channel, PROGRAMMABLE_CHANNELS)
        return self.query_float(f"CH{channel}:VOLTage?")

    def get_set_current(self, channel: int) -> float:
        """Return the configured current limit (not the measured value)."""
        self._check_channel(channel, PROGRAMMABLE_CHANNELS)
        return self.query_float(f"CH{channel}:CURRent?")

    # -- measurements ----------------------------------------------------

    def measure_voltage(self, channel: int) -> float:
        """Measure the actual output voltage of a channel."""
        self._check_channel(channel)
        return self.query_float(f"MEASure:VOLTage? CH{channel}")

    def measure_current(self, channel: int) -> float:
        """Measure the actual output current of a channel."""
        self._check_channel(channel)
        return self.query_float(f"MEASure:CURRent? CH{channel}")

    def measure_power(self, channel: int) -> float:
        """Measure the actual output power of a channel."""
        self._check_channel(channel)
        return self.query_float(f"MEASure:POWEr? CH{channel}")

    # -- output control --------------------------------------------------

    def enable(self, channel: int) -> None:
        """Turn a channel's output on."""
        self._check_channel(channel)
        self.write(f"OUTPut CH{channel},ON")

    def disable(self, channel: int) -> None:
        """Turn a channel's output off."""
        self._check_channel(channel)
        self.write(f"OUTPut CH{channel},OFF")

    def set_output(self, channel: int, on: bool) -> None:
        """Set a channel's output state from a boolean."""
        self.enable(channel) if on else self.disable(channel)

    def all_off(self) -> None:
        """Turn every channel output off (used on teardown)."""
        for channel in PROGRAMMABLE_CHANNELS:
            self.disable(channel)

    def set_track_mode(self, mode: int) -> None:
        """Set independent/series/parallel tracking (:class:`TrackMode`)."""
        if mode not in (
            TrackMode.INDEPENDENT,
            TrackMode.SERIES,
            TrackMode.PARALLEL,
        ):
            raise ValueError(f"invalid track mode {mode!r}")
        self.write(f"OUTPut:TRACK {mode}")

    def select_channel(self, channel: int) -> None:
        """Select the active channel on the front panel."""
        self._check_channel(channel)
        self.write(f"INSTrument CH{channel}")

    def get_status(self) -> int:
        """Return the ``SYSTem:STATus?`` register as an int."""
        return int(self.query("SYSTem:STATus?"), 16)

    def is_output_on(self, channel: int) -> bool:
        """Return True if the given channel's output is enabled.

        Derived from the status register bitmask (CH1 = bit 4, CH2 = bit 5).
        """
        self._check_channel(channel, PROGRAMMABLE_CHANNELS)
        bitmask = 1 << (channel + 3)
        return bool(self.get_status() & bitmask)
