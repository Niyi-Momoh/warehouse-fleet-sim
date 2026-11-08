"""Uncoordinated baseline: follow the shortest path and wait when something is in the way."""

from __future__ import annotations

import random
from collections.abc import Sequence

from fleet_sim.grid import Grid


class GreedyPlanner:
    name = "greedy"

    def reset(self, grid: Grid, robots: int, rng: random.Random) -> None:
        self.grid = grid
        self.rng = rng

    def _proposal(self, position: int, goal: int) -> int:
        distances = self.grid.distances_to(goal)
        here = distances[position]
        options = [n for n in self.grid.neighbors[position] if distances[n] < here]
        return self.rng.choice(options) if options else position

    def plan(self, positions: Sequence[int], goals: Sequence[int]) -> list[int]:
        proposed = [self._proposal(p, g) for p, g in zip(positions, goals, strict=True)]
        changed = True
        while changed:
            changed = False
            claims: dict[int, list[int]] = {}
            for robot, cell in enumerate(proposed):
                claims.setdefault(cell, []).append(robot)
            for robots in claims.values():
                if len(robots) > 1:
                    # A robot that is not moving keeps its cell. Otherwise the lowest id wins.
                    winner = min(robots, key=lambda r: (proposed[r] != positions[r], r))
                    for robot in robots:
                        if robot != winner and proposed[robot] != positions[robot]:
                            proposed[robot] = positions[robot]
                            changed = True
            owner = {cell: robot for robot, cell in enumerate(positions)}
            for robot, cell in enumerate(proposed):
                other = owner.get(cell)
                if (
                    other is not None
                    and other != robot
                    and proposed[other] == positions[robot]
                    and cell != positions[robot]
                ):
                    proposed[robot] = positions[robot]
                    proposed[other] = positions[other]
                    changed = True
        return proposed
