"""Run the full benchmark and write results/benchmark.json.

Success criteria, fixed before the results were produced:
  * zero safety violations in every run;
  * coordinated planners take at most 50 ms per tick at the 99th percentile at 80 robots;
  * coordinated planners never go more than 100 ticks without completing a task.
"""

from __future__ import annotations

import json
from pathlib import Path

from fleet_sim.layout import make_warehouse
from fleet_sim.planners import PLANNERS
from fleet_sim.simulator import SimConfig, Simulation

FLEETS = (10, 20, 40, 60, 80, 120)
SEEDS = (1, 2, 3, 4, 5)
TICKS = 1200
WARMUP = 200


def main() -> None:
    warehouse = make_warehouse()
    runs = []
    for planner in sorted(PLANNERS):
        for robots in FLEETS:
            for seed in SEEDS:
                config = SimConfig(robots=robots, ticks=TICKS, warmup=WARMUP, seed=seed)
                runs.append(Simulation(warehouse, planner, config).run().to_dict())
            print(planner, robots, flush=True)
    Path("results").mkdir(exist_ok=True)
    grid = warehouse.grid
    output = {
        "warehouse": {
            "width": grid.width,
            "height": grid.height,
            "free_cells": len(grid.free_cells()),
            "stations": len(warehouse.stations),
        },
        "ticks": TICKS,
        "warmup": WARMUP,
        "seeds": list(SEEDS),
        "runs": runs,
    }
    Path("results/benchmark.json").write_text(json.dumps(output, indent=1))


if __name__ == "__main__":
    main()
