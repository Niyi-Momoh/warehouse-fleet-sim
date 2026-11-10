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
    parser.add_argument(
        "--station-time", type=int, default=0, help="ticks a robot spends at a station"
    )
    args = parser.parse_args(argv)
    if not 0 <= args.warmup < args.ticks:
        parser.error("--warmup must be at least 0 and less than --ticks")
    if args.station_time < 0:
        parser.error("--station-time cannot be negative")
    config = SimConfig(
        args.robots, args.ticks, args.warmup, args.seed, args.arrival_rate, args.station_time
    )
    print(json.dumps(Simulation(make_warehouse(), args.planner, config).run().to_dict(), indent=2))


if __name__ == "__main__":
    main()
