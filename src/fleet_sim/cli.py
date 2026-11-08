"""Command line entry point: ``fleet-sim --help``."""

from __future__ import annotations

import argparse
import json

from fleet_sim.layout import make_warehouse
from fleet_sim.planners import PLANNERS
from fleet_sim.simulator import SimConfig, Simulation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fleet-sim", description=__doc__)
    parser.add_argument("--planner", choices=sorted(PLANNERS), default="pibt")
    parser.add_argument("--robots", type=int, default=40)
    parser.add_argument("--ticks", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--arrival-rate", type=float, help="tasks per tick; omit for an unlimited backlog"
    )
    args = parser.parse_args(argv)
    if not 0 <= args.warmup < args.ticks:
        parser.error("--warmup must be at least 0 and less than --ticks")
    config = SimConfig(args.robots, args.ticks, args.warmup, args.seed, args.arrival_rate)
    print(json.dumps(Simulation(make_warehouse(), args.planner, config).run().to_dict(), indent=2))


if __name__ == "__main__":
    main()
