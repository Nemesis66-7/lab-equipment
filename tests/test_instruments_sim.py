"""Driver + container tests against the pyvisa-sim backend."""

from __future__ import annotations

import pyvisa
import pytest

from lab_equipment import SDG1062X, SDM3065X, SPD3303X


# -- SPD3303X power supply ----------------------------------------------


def test_psu_idn(container):
    psu = container.psu()
    assert "SPD3303X-E" in psu.idn()


def test_psu_voltage_roundtrip(container):
    psu = container.psu()
    psu.set_voltage(1, 3.3)
    assert psu.get_set_voltage(1) == pytest.approx(3.3)


def test_psu_measurements(container):
    psu = container.psu()
    assert psu.measure_voltage(1) == pytest.approx(3.3)
    assert psu.measure_current(1) == pytest.approx(0.5)
    assert psu.measure_power(1) == pytest.approx(1.65)


def test_psu_output_and_status(container):
    psu = container.psu()
    psu.enable(1)
    assert psu.is_output_on(1) is True  # status register bit 4 set in sim


def test_psu_voltage_clamp_rejects_over_limit(container):
    psu = container.psu()
    with pytest.raises(ValueError, match="safety clamp"):
        psu.set_voltage(1, 99.0)


def test_psu_custom_clamp(sim_rm):
    psu = SPD3303X.from_ip(
        "psu", resource_manager=sim_rm, voltage_limits={1: 5.0}
    )
    psu.set_voltage(1, 5.0)  # at the clamp is allowed
    with pytest.raises(ValueError):
        psu.set_voltage(1, 5.1)


def test_psu_set_current_channel_guard(container):
    psu = container.psu()
    with pytest.raises(ValueError, match="channel must be"):
        psu.set_voltage(3, 3.3)  # CH3 is not programmable


# -- SDG1062X waveform generator ----------------------------------------


def test_awg_idn(container):
    assert "SDG1062X" in container.awg().idn()


def test_awg_set_basic_wave(container):
    awg = container.awg()
    # Exact command must match the sim dialogue.
    awg.set_basic_wave(
        1, wave_type="SINE", frequency=1000, amplitude=2, offset=0
    )


def test_awg_get_basic_wave_parses(container):
    params = container.awg().get_basic_wave(1)
    assert params["WVTP"] == "SINE"
    assert params["FRQ"] == "1000HZ"


def test_awg_bad_channel(container):
    with pytest.raises(ValueError):
        container.awg().set_frequency(3, 1000)


def test_awg_bad_wave_type(container):
    with pytest.raises(ValueError):
        container.awg().set_wave_type(1, "TRIANGLE")


def test_awg_get_output_parses(container):
    out = container.awg().get_output(1)
    assert out["STATE"] == "ON"
    assert out["LOAD"] == "50"


# -- SDM3065X multimeter ------------------------------------------------


def test_dmm_idn(container):
    assert "SDM3065X" in container.dmm().idn()


def test_dmm_measure(container):
    dmm = container.dmm()
    assert dmm.measure_dc_voltage() == pytest.approx(1.234)
    assert dmm.measure_dc_current() == pytest.approx(0.01)
    assert dmm.measure_resistance() == pytest.approx(100.5)


def test_dmm_average(container):
    # READ? returns "1.0,1.1,0.9" -> mean 1.0
    assert container.dmm().average("dc_voltage", 3) == pytest.approx(1.0)


def test_dmm_resolution_requires_range(container):
    with pytest.raises(ValueError, match="resolution requires"):
        container.dmm().measure_dc_voltage(resolution=0.001)


# -- transport / labgrid adapter ----------------------------------------


def test_from_labgrid_accepts_open_session(sim_rm):
    session = sim_rm.open_resource("TCPIP::dmm::INSTR")
    session.read_termination = "\n"
    session.write_termination = "\n"
    dmm = SDM3065X.from_labgrid(session)
    assert "SDM3065X" in dmm.idn()
    # from_labgrid must not own the session.
    dmm.close()
    assert session.session is not None  # still open (not closed by us)
    session.close()


class _FakeDriver:
    """Mimics labgrid PyVISADriver.get_session()."""

    def __init__(self, session):
        self._session = session

    def get_session(self):
        return self._session


class _FakeTarget:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, name):
        assert name == "PyVISADriver"
        return self._driver


def test_from_labgrid_target_and_driver(sim_rm):
    session = sim_rm.open_resource("TCPIP::awg::INSTR")
    session.read_termination = "\n"
    session.write_termination = "\n"
    driver = _FakeDriver(session)
    target = _FakeTarget(driver)

    awg_from_driver = SDG1062X.from_labgrid(driver)
    awg_from_target = SDG1062X.from_labgrid(target)
    assert "SDG1062X" in awg_from_driver.idn()
    assert "SDG1062X" in awg_from_target.idn()
    session.close()


def test_build_resource_string_socket():
    from lab_equipment.transport import build_resource_string

    assert (
        build_resource_string("10.0.0.1", socket=True)
        == "TCPIP::10.0.0.1::5025::SOCKET"
    )
    assert build_resource_string("10.0.0.1") == "TCPIP::10.0.0.1::INSTR"


def test_missing_host_raises_when_required():
    from lab_equipment.config import MissingConfigError, load_env_config

    with pytest.raises(MissingConfigError):
        load_env_config(require_hosts=True, environ={})


def test_unknown_query_uses_sim_error(container):
    # Sanity: the sim is actually answering (returns its device error string
    # for an unrecognized query), not silently passing.
    assert container.dmm().query("TOTALLY:UNKNOWN?") == "ERROR"
