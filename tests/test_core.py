from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path

import pytest

from fleet_sim.grid import UNREACHABLE, Grid
from fleet_sim.layout import make_warehouse
from fleet_sim.planners import PLANNERS
from fleet_sim.simulator import Metrics, SafetyError, SimConfig, Simulation, percentile
from fleet_sim.validate import check_step

GRID = Grid.from_ascii(["...", ".#.", "..."])


def test_distances_route_around_obstacles():
    assert GRID.distances_to(GRID.cell(2, 2))[GRID.cell(0, 0)] == 4
    assert GRID.distances_to(GRID.cell(0, 0))[GRID.cell(1, 1)] == UNREACHABLE


def test_warehouse_is_fully_connected():
    warehouse = make_warehouse()
    distances = warehouse.grid.distances_to(warehouse.stations[0])
    assert all(distances[cell] < UNREACHABLE for cell in warehouse.grid.free_cells())
    assert set(warehouse.access_cells).isdisjoint(warehouse.stations)
    assert warehouse.access_cells and warehouse.stations


@pytest.mark.parametrize(
    ("before", "after", "kind"),
    [
        ([0], [GRID.cell(1, 1)], "blocked"),
        ([0], [GRID.cell(2, 0)], "jump"),
        ([0, 2], [1, 1], "vertex"),
        ([0, 1], [1, 0], "swap"),
    ],
)
def test_validator_catches_each_violation(before, after, kind):
    assert kind in {problem.kind for problem in check_step(GRID, before, after)}


def test_validator_allows_following_and_waiting():
    assert check_step(GRID, [0, 1], [1, 2]) == []
    assert check_step(GRID, [0, 1], [0, 1]) == []


def drive(name: str, grid: Grid, starts: list[int], goals: list[int], limit: int = 40):
    planner = PLANNERS[name]()
    planner.reset(grid, len(starts), random.Random(5))
    positions = list(starts)
    for tick in range(limit):
        if positions == goals:
            return tick
        following = planner.plan(positions, goals)
        assert check_step(grid, positions, following) == []
        positions = following
    return None


TWO_LANES = Grid.from_ascii([".....", "....."])
HEAD_ON = (
    [TWO_LANES.cell(0, 0), TWO_LANES.cell(4, 0)],
    [TWO_LANES.cell(4, 0), TWO_LANES.cell(0, 0)],
)


@pytest.mark.parametrize("name", ["pibt", "whca"])
def test_coordinated_planners_resolve_a_head_on_meeting(name):
    assert drive(name, TWO_LANES, *HEAD_ON) is not None


def test_greedy_baseline_deadlocks_head_on():
    assert drive("greedy", TWO_LANES, *HEAD_ON) is None


@pytest.mark.parametrize("name", sorted(PLANNERS))
@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("robots", [10, 60])
def test_no_planner_ever_breaks_safety_rules(name, seed, robots):
    config = SimConfig(robots=robots, ticks=120, warmup=0, seed=seed, strict=True)
    assert Simulation(make_warehouse(), name, config).run().collisions == 0


def test_strict_mode_stops_an_unsafe_planner(monkeypatch):
    class Bad:
        name = "bad"

        def reset(self, grid, robots, rng):
            self.count = robots

        def plan(self, positions, goals):
            return [positions[0]] * self.count

    monkeypatch.setitem(PLANNERS, "bad", Bad)
    with pytest.raises(SafetyError):
        Simulation(
            make_warehouse(), "bad", SimConfig(robots=3, ticks=2, warmup=0, strict=True)
        ).run()


@pytest.mark.parametrize("name", sorted(PLANNERS))
def test_same_seed_gives_same_result(name):
    def run() -> dict:
        config = SimConfig(robots=20, ticks=150, warmup=0, seed=9)
        result = Simulation(make_warehouse(), name, config).run().to_dict()
        result.pop("plan_ms_p50")
        result.pop("plan_ms_p99")
        return result

    assert run() == run()


def test_coordination_beats_the_baseline_under_load():
    def throughput(name: str) -> float:
        config = SimConfig(robots=40, ticks=500, warmup=100, seed=4)
        return Simulation(make_warehouse(), name, config).run().throughput_per_1000

    baseline = throughput("greedy")
    assert throughput("pibt") > baseline
    assert throughput("whca") > baseline


def test_poisson_arrivals_finish_light_demand():
    config = SimConfig(robots=20, ticks=800, warmup=100, seed=2, arrival_rate=0.05)
    metrics = Simulation(make_warehouse(), "pibt", config).run()
    assert metrics.completed > 0
    assert metrics.tasks_waiting_at_end < 10


def test_too_many_robots_is_rejected():
    with pytest.raises(ValueError):
        Simulation(make_warehouse(), "pibt", SimConfig(robots=100_000)).run()


def test_percentile_nearest_rank():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.99) == 4.0
    assert percentile([], 0.5) == 0.0


def test_metrics_serialise():
    assert Metrics("x", 1, 1, 10).to_dict()["planner"] == "x"


def test_readme_results_match_the_benchmark_file():
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("report", root / "benchmarks" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    study = json.loads((root / "results" / "benchmark.json").read_text())
    assert module.block(study) in (root / "README.md").read_text()
