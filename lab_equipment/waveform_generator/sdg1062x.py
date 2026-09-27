"""Driver for the Siglent SDG1062X arbitrary waveform / function generator.

Uses the Siglent ``C<n>:`` command syntax (BSWV = basic wave, OUTP = output),
the same family shown in labgrid's pyVISA example.
"""

from __future__ import annotations

import logging

from ..scpi_instrument import ScpiInstrument

logger = logging.getLogger(__name__)

#: Channels supported by the SDG1062X.
CHANNELS = (1, 2)

#: Valid ``WVTP`` (wave type) values.
WAVE_TYPES = ("SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC")


class SDG1062X(ScpiInstrument):
    """Siglent SDG1062X two-channel function/arbitrary waveform generator."""

    @staticmethod
    def _channel(channel: int) -> str:
        if channel not in CHANNELS:
            raise ValueError(
                f"channel must be one of {CHANNELS}, got {channel!r}"
            )
        return f"C{channel}"

    # -- basic waveform --------------------------------------------------

    def set_basic_wave(
        self,
        channel: int,
        *,
        wave_type: str | None = None,
        frequency: float | None = None,
        amplitude: float | None = None,
        offset: float | None = None,
        phase: float | None = None,
        duty: float | None = None,
        high_level: float | None = None,
        low_level: float | None = None,
    ) -> None:
        """Set basic-wave parameters for a channel (``C<n>:BSWV``).

        Only the parameters you pass are sent, so this can be used to change a
        single field without disturbing the others.
        """
        prefix = self._channel(channel)
        if wave_type is not None:
            wave_type = wave_type.upper()
            if wave_type not in WAVE_TYPES:
                raise ValueError(
                    f"wave_type must be one of {WAVE_TYPES}, got {wave_type!r}"
                )
        params: list[str] = []
        for key, value in (
            ("WVTP", wave_type),
            ("FRQ", frequency),
            ("AMP", amplitude),
            ("OFST", offset),
            ("PHSE", phase),
            ("DUTY", duty),
            ("HLEV", high_level),
            ("LLEV", low_level),
        ):
            if value is not None:
                params.append(f"{key},{value}")
        if not params:
            raise ValueError("set_basic_wave requires at least one parameter")
        self.write(f"{prefix}:BSWV {','.join(params)}")

    def get_basic_wave(self, channel: int) -> dict[str, str]:
        """Query basic-wave parameters, returned as a name->value dict."""
        prefix = self._channel(channel)
        raw = self.query(f"{prefix}:BSWV?")
        # Response form: "C1:BSWV WVTP,SINE,FRQ,1000,AMP,2,..."
        _, _, payload = raw.partition(" ")
        tokens = [t for t in payload.split(",") if t != ""]
        return dict(zip(tokens[0::2], tokens[1::2]))

    # -- convenience setters --------------------------------------------

    def set_frequency(self, channel: int, hz: float) -> None:
        """Set output frequency (hertz)."""
        self.set_basic_wave(channel, frequency=hz)

    def set_amplitude(self, channel: int, vpp: float) -> None:
        """Set output amplitude (volts peak-to-peak)."""
        self.set_basic_wave(channel, amplitude=vpp)

    def set_offset(self, channel: int, volts: float) -> None:
        """Set DC offset (volts)."""
        self.set_basic_wave(channel, offset=volts)

    def set_wave_type(self, channel: int, wave_type: str) -> None:
        """Set the wave type (see :data:`WAVE_TYPES`)."""
        self.set_basic_wave(channel, wave_type=wave_type)

    # -- output control --------------------------------------------------

    def set_output(
        self,
        channel: int,
        on: bool,
        *,
        load: str | float | None = None,
        polarity: str | None = None,
    ) -> None:
        """Enable/disable a channel output.

        Args:
            channel: 1 or 2.
            on: Output state.
            load: Output load, ``50`` (ohms) or ``"HZ"`` for high-Z.
            polarity: ``"NOR"`` or ``"INVT"``.
        """
        prefix = self._channel(channel)
        params = ["ON" if on else "OFF"]
        if load is not None:
            params.append(f"LOAD,{load}")
        if polarity is not None:
            params.append(f"PLRT,{polarity}")
        self.write(f"{prefix}:OUTP {','.join(params)}")

    def enable(self, channel: int, **kwargs) -> None:
        """Turn a channel output on."""
        self.set_output(channel, True, **kwargs)

    def disable(self, channel: int) -> None:
        """Turn a channel output off."""
        self.set_output(channel, False)

    def all_off(self) -> None:
        """Turn every channel output off (used on teardown)."""
        for channel in CHANNELS:
            self.disable(channel)

    def set_load(self, channel: int, load: str | float) -> None:
        """Set output load without changing the on/off state."""
        prefix = self._channel(channel)
        self.write(f"{prefix}:OUTP LOAD,{load}")

    def get_output(self, channel: int) -> dict[str, str]:
        """Query output state/parameters, returned as a name->value dict."""
        prefix = self._channel(channel)
        raw = self.query(f"{prefix}:OUTP?")
        _, _, payload = raw.partition(" ")
        tokens = [t for t in payload.split(",") if t != ""]
        # First token is the ON/OFF state; the rest are key,value pairs.
        state = {"STATE": tokens[0]} if tokens else {}
        rest = tokens[1:]
        state.update(dict(zip(rest[0::2], rest[1::2])))
        return state
