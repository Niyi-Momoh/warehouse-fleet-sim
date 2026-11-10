"""Measure how station processing time affects the fleet.

Fixed before the results were produced:
  * Station times of 0, 5, 10 and 20 ticks, with 40 and 80 robots, over five seeds.
  * Question: does throughput fall in line with the stations' capacity, and do planners
    disturb robots that are still being served?
"""

from __future__ import annotations

import json
from pathlib import Path

from fleet_sim.layout import make_warehouse
from fleet_sim.simulator import SimConfig, Simulation

PLANNERS = ("pibt", "whca")
FLEETS = (40, 80)
STATION_TIMES = (0, 5, 10, 20)
SEEDS = (1, 2, 3, 4, 5)
TICKS = 1200
WARMUP = 200


def main() -> None:
    warehouse = make_warehouse()
    runs = []
    for planner in PLANNERS:
        for robots in FLEETS:
            for station_time in STATION_TIMES:
                for seed in SEEDS:
                    config = SimConfig(robots, TICKS, WARMUP, seed, station_time=station_time)
                    result = Simulation(warehouse, planner, config).run().to_dict()
                    result["station_time"] = station_time
                    runs.append(result)
                print(planner, robots, station_time, flush=True)
    output = {
        "stations": len(warehouse.stations),
        "ticks": TICKS,
        "warmup": WARMUP,
        "seeds": list(SEEDS),
        "runs": runs,
    }
    Path("results/station_time.json").write_text(json.dumps(output, indent=1))


if __name__ == "__main__":
    main()
