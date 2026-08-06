"""Run AeroLink's offline Pilot 2 readiness checks from a source checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def run() -> int:
    from aerolink.preflight import main

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
