"""Planners choose every robot's next cell on each tick."""

from __future__ import annotations

from collections.abc import Callable

from fleet_sim.planners.base import Planner
from fleet_sim.planners.greedy import GreedyPlanner
from fleet_sim.planners.pibt import PibtPlanner
from fleet_sim.planners.whca import WhcaPlanner

PLANNERS: dict[str, Callable[[], Planner]] = {
    "greedy": GreedyPlanner,
    "pibt": PibtPlanner,
    "whca": WhcaPlanner,
}

__all__ = ["PLANNERS", "GreedyPlanner", "PibtPlanner", "Planner", "WhcaPlanner"]
