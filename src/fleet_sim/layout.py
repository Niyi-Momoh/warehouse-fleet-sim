"""Generate a warehouse with shelf blocks, single-width aisles and picking stations."""

from __future__ import annotations

from dataclasses import dataclass

from fleet_sim.grid import Grid


@dataclass(frozen=True)
class Warehouse:
    grid: Grid
    access_cells: tuple[int, ...]
    stations: tuple[int, ...]


def make_warehouse(
    block_columns: int = 4,
    block_rows: int = 6,
    block_width: int = 6,
    block_height: int = 2,
    margin: int = 3,
    station_spacing: int = 3,
) -> Warehouse:
    """Lay out shelf blocks to the right of an open area with stations on the left wall."""
    width = margin + block_columns * (block_width + 1)
    height = 1 + block_rows * (block_height + 1)
    shelves: set[tuple[int, int]] = set()
    for column in range(block_columns):
        left = margin + column * (block_width + 1)
        for row in range(block_rows):
            top = 1 + row * (block_height + 1)
            shelves.update(
                (x, y)
                for x in range(left, left + block_width)
                for y in range(top, top + block_height)
            )
    grid = Grid(width, height, shelves)
    stations = tuple(grid.cell(0, y) for y in range(1, height, station_spacing))
    station_set = set(stations)
    access = []
    for cell in grid.free_cells():
        x, y = grid.xy(cell)
        adjacent = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        if cell not in station_set and any(point in shelves for point in adjacent):
            access.append(cell)
    return Warehouse(grid, tuple(access), stations)
