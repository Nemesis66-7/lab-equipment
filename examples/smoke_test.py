#!/usr/bin/env python3
"""On-bench smoke test: connect to all three instruments and read *IDN?.

Hosts are read from the environment (see ``.env.example``); nothing is
hardcoded. Run against the real bench::

    export LAB_EQUIPMENT_PSU_HOST=...   # or put them in a .env file
    export LAB_EQUIPMENT_AWG_HOST=...
    export LAB_EQUIPMENT_DMM_HOST=...
    python examples/smoke_test.py

This performs only safe, read-only operations (identity query and a single
DMM DC-voltage measurement). It does NOT enable any PSU/AWG output.
"""

from __future__ import annotations

import logging
import sys

from lab_equipment.config import (
    ENV_AWG_HOST,
    ENV_DMM_HOST,
    ENV_PSU_HOST,
)
from lab_equipment.containers import build_container


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    container = build_container(require_hosts=False)
    cfg = container.config

    checks = [
        (ENV_PSU_HOST, cfg.psu.host(), container.psu),
        (ENV_AWG_HOST, cfg.awg.host(), container.awg),
        (ENV_DMM_HOST, cfg.dmm.host(), container.dmm),
    ]

    failures = 0
    for env_name, host, provider in checks:
        if not host:
            print(f"SKIP  {env_name} not set")
            continue
        # Acquire once, run all safe ops, then close. Container providers are
        # singletons (one control session per instrument), so do not re-acquire
        # after closing.
        try:
            instrument = provider()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL  {host:<15} {env_name}: {exc}")
            continue
        try:
            print(f"OK    {host:<15} {instrument.idn()}")
            if env_name == ENV_DMM_HOST:
                # One safe, read-only measurement.
                print(
                    f"      DC voltage = {instrument.measure_dc_voltage()} V"
                )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {host:<15} {env_name}: {exc}")
        finally:
            instrument.close()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
