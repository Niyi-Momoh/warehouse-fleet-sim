"""Check every motion step independently of whichever planner produced it."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fleet_sim.grid import Grid


@dataclass(frozen=True)
class Violation:
    kind: str
    robots: tuple[int, ...]
    cell: int


def check_step(grid: Grid, before: Sequence[int], after: Sequence[int]) -> list[Violation]:
    """Return every rule broken by moving all robots from ``before`` to ``after``."""
    if len(before) != len(after):
        return [Violation("count", (), -1)]
    problems: list[Violation] = []
    occupants: dict[int, list[int]] = {}
    for robot, (start, end) in enumerate(zip(before, after, strict=True)):
        if not 0 <= end < grid.size or not grid.free[end]:
            problems.append(Violation("blocked", (robot,), end))
            continue
        start_x, start_y = grid.xy(start)
        end_x, end_y = grid.xy(end)
        if abs(start_x - end_x) + abs(start_y - end_y) > 1:
            problems.append(Violation("jump", (robot,), end))
        occupants.setdefault(end, []).append(robot)
    for cell, robots in occupants.items():
        if len(robots) > 1:
            problems.append(Violation("vertex", tuple(robots), cell))
    start_owner = {cell: robot for robot, cell in enumerate(before)}
    for robot, (start, end) in enumerate(zip(before, after, strict=True)):
        other = start_owner.get(end)
        if other is not None and other > robot and start != end and after[other] == start:
            problems.append(Violation("swap", (robot, other), end))
    return problems
