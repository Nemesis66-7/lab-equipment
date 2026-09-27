# Integrating `lab_equipment` into `pphil_common` (and other HIL repos)

`lab_equipment` is a standalone package. HIL repos consume it as a dependency;
nothing in this package imports `pphil_common`.

## 1. Add the dependency

In the consuming repo's `pyproject.toml`, add:

```
"pp-lab-equipment @ git+ssh://git@<host>/<org>/lab-equipment.git@main"
```

`pphil_common` already pins `PyVISA` and `PyVISA-py`, which satisfy this
package's runtime needs; `dependency-injector` is the only new transitive
dependency. Re-lock afterwards (per `pphil_common`'s CLAUDE.md):

```bash
uv pip compile pyproject.toml --universal --python-version 3.10 -o requirements.lock
```

## 2. Register the fixtures

In the product repo's `conftest.py`, add to `pytest_plugins` alongside the
existing entries:

```python
pytest_plugins = (
    "pphil_common.power.power_fixture",
    ...
    "lab_equipment.fixtures.instruments_fixture",
)
```

This exposes `bench_psu`, `bench_awg`, `bench_dmm`, `visa_resource_manager`,
and `lab_equipment_container`. Each instrument fixture `skip`s if its host env
var is unset, so repos that don't have a given instrument are unaffected.

## 3. Provide the host env vars

Set these in the test runner / CI environment (or a git-ignored `.env`):

```
LAB_EQUIPMENT_PSU_HOST, LAB_EQUIPMENT_AWG_HOST, LAB_EQUIPMENT_DMM_HOST
```

They are intentionally not committed anywhere in the HIL repos.

## 4. (Optional) thin pphil_common wrapper module

If `pphil_common` prefers its per-module `*_manager` / `*_fixture` convention,
add a small `pphil_common/instruments/` package that re-exports these fixtures
and adds any bench-specific defaults (e.g. per-channel PSU safety clamps for a
particular DUT):

```python
# pphil_common/instruments/instruments_fixture.py
import pytest
from lab_equipment.fixtures.instruments_fixture import (  # noqa: F401
    bench_awg,
    bench_dmm,
    lab_equipment_container,
    visa_resource_manager,
)
from lab_equipment import SPD3303X


@pytest.fixture(scope="session")
def dut_psu(lab_equipment_container):
    """PSU with DUT-specific voltage clamps."""
    if not lab_equipment_container.config.psu.host():
        pytest.skip("LAB_EQUIPMENT_PSU_HOST not set")
    host = lab_equipment_container.config.psu.host()
    rm = lab_equipment_container.resource_manager()
    psu = SPD3303X.from_ip(
        host, resource_manager=rm, voltage_limits={1: 14.0, 2: 5.0}
    )
    try:
        yield psu
    finally:
        psu.all_off()
        psu.close()
```

## 5. Using it alongside labgrid

If a repo already acquires a labgrid `Target` that has a `PyVISADevice` /
`PyVISADriver` for one of these instruments, build the driver from it instead
of by IP:

```python
from lab_equipment import SPD3303X

psu = SPD3303X.from_labgrid(target)  # reuses labgrid's managed session
```

This is the bridge to the existing `labgrid/driver/power/siglent.py` path:
`lab_equipment` gives the full SCPI surface (setpoints, measurements, waveform
config) on top of the same VXI-11/pyVISA session labgrid already manages.
