"""A four-connected grid with cached shortest-path distances."""

from __future__ import annotations

from collections import deque

UNREACHABLE = 10**9


class Grid:
    """Cells are integers, ``y * width + x``, which keeps planning loops fast."""

    def __init__(self, width: int, height: int, blocked: set[tuple[int, int]] | None = None):
        if width <= 0 or height <= 0:
            raise ValueError("grid dimensions must be positive")
        self.width = width
        self.height = height
        self.size = width * height
        blocked = blocked or set()
        self.free = [(index % width, index // width) not in blocked for index in range(self.size)]
        self.neighbors: list[tuple[int, ...]] = [self._adjacent(i) for i in range(self.size)]
        self._distances: dict[int, list[int]] = {}

    @classmethod
    def from_ascii(cls, rows: list[str]) -> Grid:
        """Build a grid from strings in which ``#`` marks a blocked cell."""
        blocked = {
            (x, y) for y, row in enumerate(rows) for x, char in enumerate(row) if char == "#"
        }
        return cls(len(rows[0]), len(rows), blocked)

    def cell(self, x: int, y: int) -> int:
        return y * self.width + x

    def xy(self, cell: int) -> tuple[int, int]:
        return cell % self.width, cell // self.width

    def free_cells(self) -> list[int]:
        return [cell for cell in range(self.size) if self.free[cell]]

    def _adjacent(self, cell: int) -> tuple[int, ...]:
        if not self.free[cell]:
            return ()
        x, y = cell % self.width, cell // self.width
        options = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        return tuple(
            self.cell(nx, ny)
            for nx, ny in options
            if 0 <= nx < self.width and 0 <= ny < self.height and self.free[self.cell(nx, ny)]
        )

    def distances_to(self, goal: int) -> list[int]:
        """Return the shortest distance from every cell to ``goal``, cached per goal."""
        cached = self._distances.get(goal)
        if cached is not None:
            return cached
        distances = [UNREACHABLE] * self.size
        distances[goal] = 0
        queue = deque([goal])
        while queue:
            current = queue.popleft()
            for neighbor in self.neighbors[current]:
                if distances[neighbor] == UNREACHABLE:
                    distances[neighbor] = distances[current] + 1
                    queue.append(neighbor)
        self._distances[goal] = distances
        return distances
