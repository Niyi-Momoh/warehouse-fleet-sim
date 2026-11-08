"""Windowed Hierarchical Cooperative A* (Silver, 2005), replanned on every tick.

Each robot searches through space and time around the reservations of robots planned
before it. If a robot has no valid plan it moves to the front of the order and planning
restarts. If that keeps failing, PIBT chooses the moves for that tick, because a repeated
failure would otherwise leave the fleet frozen in the same state indefinitely.
"""

from __future__ import annotations

import heapq
import random
from collections.abc import Sequence

from fleet_sim.grid import Grid
from fleet_sim.planners.pibt import PibtPlanner


class WhcaPlanner:
    name = "whca"

    def __init__(self, window: int = 8, max_restarts: int = 4, node_limit: int = 4000):
        self.window = window
        self.max_restarts = max_restarts
        self.node_limit = node_limit

    def reset(self, grid: Grid, robots: int, rng: random.Random) -> None:
        self.grid = grid
        self.age = [0] * robots
        self.last_goal: list[int | None] = [None] * robots
        self.fallback_ticks = 0
        self.fallback = PibtPlanner()
        self.fallback.reset(grid, robots, rng)

    def plan(self, positions: Sequence[int], goals: Sequence[int]) -> list[int]:
        for robot, goal in enumerate(goals):
            self.age[robot] = 0 if goal != self.last_goal[robot] else self.age[robot] + 1
            self.last_goal[robot] = goal
        order = sorted(
            range(len(positions)),
            key=lambda r: (positions[r] == goals[r], -self.age[r], r),
        )
        for _ in range(self.max_restarts + 1):
            failed = self._plan_order(order, positions, goals)
            if isinstance(failed, int):
                order.remove(failed)
                order.insert(0, failed)
                continue
            return failed
        self.fallback_ticks += 1
        return self.fallback.plan(positions, goals)

    def _plan_order(
        self, order: list[int], positions: Sequence[int], goals: Sequence[int]
    ) -> int | list[int]:
        size = self.grid.size
        vertices: set[int] = set()
        edges: set[int] = set()
        result = list(positions)
        for robot in order:
            path = self._search(positions[robot], goals[robot], vertices, edges)
            if path is None:
                return robot
            for time in range(self.window):
                vertices.add((time + 1) * size + path[time + 1])
                edges.add(time * size * size + path[time] * size + path[time + 1])
            result[robot] = path[1]
        return result

    def _search(
        self, start: int, goal: int, vertices: set[int], edges: set[int]
    ) -> list[int] | None:
        size = self.grid.size
        distances = self.grid.distances_to(goal)
        best = {start: 0}
        parents: dict[int, int] = {}
        counter = 0
        frontier = [(distances[start], 0, counter, start)]
        expanded = 0
        while frontier and expanded < self.node_limit:
            _, gone, _, state = heapq.heappop(frontier)
            time, cell = divmod(state, size)
            if gone > best[state]:
                continue
            if time == self.window:
                path = [cell]
                while state in parents:
                    state = parents[state]
                    path.append(state % size)
                path.reverse()
                return path
            expanded += 1
            for following in (*self.grid.neighbors[cell], cell):
                next_state = (time + 1) * size + following
                if next_state in vertices:
                    continue
                if following != cell and time * size * size + following * size + cell in edges:
                    continue
                step = 0 if following == cell == goal else 1
                new_cost = gone + step
                if new_cost < best.get(next_state, 1 << 60):
                    best[next_state] = new_cost
                    parents[next_state] = state
                    counter += 1
                    estimate = new_cost + distances[following]
                    heapq.heappush(frontier, (estimate, new_cost, counter, next_state))
        return None
