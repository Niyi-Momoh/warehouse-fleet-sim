"""Priority Inheritance with Backtracking (Okumura et al., 2019).

Robots choose moves in priority order. A robot that wants an occupied cell lends its
priority to the occupant, which must move away. If the occupant has nowhere to go,
the failure backtracks and the requester tries its next best cell.
"""

from __future__ import annotations

import random
import sys
from collections.abc import Sequence

from fleet_sim.grid import Grid


class PibtPlanner:
    name = "pibt"

    def reset(self, grid: Grid, robots: int, rng: random.Random) -> None:
        self.grid = grid
        self.rng = rng
        self.tie_break = [rng.random() for _ in range(robots)]
        self.priority = list(self.tie_break)
        sys.setrecursionlimit(max(sys.getrecursionlimit(), robots + 1000))

    def plan(self, positions: Sequence[int], goals: Sequence[int]) -> list[int]:
        for robot, (position, goal) in enumerate(zip(positions, goals, strict=True)):
            if position == goal:
                self.priority[robot] = self.tie_break[robot]
            else:
                self.priority[robot] += 1
        self._positions = positions
        self._goals = goals
        self._now = {cell: robot for robot, cell in enumerate(positions)}
        self._next_owner: dict[int, int] = {}
        self._chosen: list[int | None] = [None] * len(positions)
        for robot in sorted(range(len(positions)), key=lambda r: -self.priority[r]):
            if self._chosen[robot] is None:
                self._assign(robot, None)
        return [cell for cell in self._chosen if cell is not None]

    def _candidates(self, robot: int) -> list[int]:
        position = self._positions[robot]
        distances = self.grid.distances_to(self._goals[robot])
        cells = [*self.grid.neighbors[position], position]
        random_keys = {cell: self.rng.random() for cell in cells}
        return sorted(
            cells,
            key=lambda cell: (
                distances[cell],
                cell in self._now and cell != position,
                random_keys[cell],
            ),
        )

    def _assign(self, robot: int, requester: int | None) -> bool:
        blocked_cell = None if requester is None else self._positions[requester]
        position = self._positions[robot]
        for cell in self._candidates(robot):
            if cell in self._next_owner or cell == blocked_cell:
                continue
            self._chosen[robot] = cell
            self._next_owner[cell] = robot
            occupant = self._now.get(cell)
            if (
                occupant is not None
                and occupant != robot
                and self._chosen[occupant] is None
                and not self._assign(occupant, robot)
            ):
                continue
            return True
        self._chosen[robot] = position
        self._next_owner[position] = robot
        return False
