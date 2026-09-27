# lab_equipment

A small, pip-installable Python API for controlling the Siglent bench
instruments used in Precision Planting HIL testing, over pyVISA/SCPI. It is
designed to be imported by `pphil_common` and other HIL repos, used from
plain scripts, or driven through a labgrid target.

## Instruments

| Role | Model | Driver |
|---|---|---|
| Programmable DC power supply (3-ch) | SPD3303X-E | `lab_equipment.SPD3303X` |
| Arbitrary waveform generator (2-ch) | SDG1062X | `lab_equipment.SDG1062X` |
| 6.5-digit digital multimeter | SDM3065X | `lab_equipment.SDM3065X` |

All three are LAN/SCPI instruments addressed as `TCPIP::<host>::INSTR` over the
pure-Python PyVISA-py (`@py`) backend by default. A raw-socket fallback
(`TCPIP::<host>::5025::SOCKET`) is available for VXI-11 firmware quirks.

## Host configuration (never hardcoded)

Instrument addresses are internal information and are **only** read from
environment variables — see `.env.example`:

```
LAB_EQUIPMENT_PSU_HOST=...
LAB_EQUIPMENT_AWG_HOST=...
LAB_EQUIPMENT_DMM_HOST=...
LAB_EQUIPMENT_VISA_BACKEND=@py   # optional
LAB_EQUIPMENT_SOCKET=0           # optional (1 = raw socket)
LAB_EQUIPMENT_TIMEOUT_MS=5000    # optional
```

Copy `.env.example` to `.env` (git-ignored) for local use, or export the
variables in CI / your test runner.

## Install

```bash
pip install -e .                 # core
pip install -e ".[test]"         # + pytest and the pyvisa-sim backend
pip install -e ".[dotenv]"       # + python-dotenv for .env loading
```

As a dependency of another repo (e.g. `pphil_common`), add it to that repo's
`pyproject.toml` — for example:

```
"pp-lab-equipment @ git+ssh://git@<host>/<org>/lab-equipment.git@main"
```

## Usage

### Direct (scripts)

```python
import os
from lab_equipment import SPD3303X

psu = SPD3303X.from_ip(os.environ["LAB_EQUIPMENT_PSU_HOST"])
psu.apply(1, volts=12.0, amps=1.0)
psu.enable(1)
print(psu.measure_voltage(1))
psu.all_off()
psu.close()
```

### Via the DI container (reads env vars)

```python
from lab_equipment import build_container

container = build_container()  # reads LAB_EQUIPMENT_* from env/.env
dmm = container.dmm()
print(dmm.measure_dc_voltage())
```

### From a labgrid target

If your repo already acquires a labgrid `Target` with a `PyVISADriver`:

```python
from lab_equipment import SDG1062X

awg = SDG1062X.from_labgrid(target)  # or from_labgrid(pyvisa_driver)
awg.set_basic_wave(1, wave_type="SINE", frequency=1000, amplitude=2)
awg.enable(1, load=50)
```
(The labgrid driver owns the session, so `close()` is a no-op here.)

## Pytest fixtures

Register the plugin in a consuming repo's `conftest.py` (the same mechanism as
`pphil_common`'s other fixtures):

```python
pytest_plugins = ("lab_equipment.fixtures.instruments_fixture",)
```

Fixtures (all session-scoped): `bench_psu`, `bench_awg`, `bench_dmm`,
`visa_resource_manager`, `lab_equipment_container`. Each instrument fixture
`skip`s cleanly if its host env var is unset, and PSU/AWG outputs are forced
off on teardown.

```python
def test_rail_comes_up(bench_psu, bench_dmm):
    bench_psu.apply(1, 3.3, 0.5)
    bench_psu.enable(1)
    assert bench_dmm.measure_dc_voltage() == pytest.approx(3.3, abs=0.1)
```

## Development

```bash
python -m pytest            # runs against pyvisa-sim, no hardware needed
ruff check . && ruff format --check .
python examples/smoke_test.py   # on-bench: *IDN? for each configured host
```

The test suite uses the `pyvisa-sim` backend (`tests/sim_instruments.yaml`),
so it runs in CI with no instruments attached.

## Design notes

- **Driver classes are configuration-agnostic** — they take an explicit host
  or an open session. The `dependency_injector` container in
  `lab_equipment/containers.py` is the only place that reads host config, which
  keeps the classes reusable and easy to override in tests.
- **PSU safety clamps**: `SPD3303X` enforces configurable per-channel maximum
  voltage/current before sending a setpoint, so a test cannot over-drive the
  DUT (`SPD3303X.from_ip(host, voltage_limits={1: 14.0})`).
