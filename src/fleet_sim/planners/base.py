"""The interface shared by all planners."""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Protocol

from fleet_sim.grid import Grid


class Planner(Protocol):
    name: str

    def reset(self, grid: Grid, robots: int, rng: random.Random) -> None:
        """Prepare for a new run."""

    def plan(self, positions: Sequence[int], goals: Sequence[int]) -> list[int]:
        """Return each robot's cell for the next tick."""
