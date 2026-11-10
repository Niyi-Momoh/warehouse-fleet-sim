"""Run a fleet through a continuous stream of pick-and-deliver tasks."""

from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, dataclass, field

from fleet_sim.layout import Warehouse
from fleet_sim.planners import PLANNERS
from fleet_sim.validate import check_step


class SafetyError(RuntimeError):
    """Raised in strict mode when a planner produces an unsafe move."""


@dataclass
class Task:
    pickup: int
    dropoff: int
    created: int
    assigned: int = -1


@dataclass
class Robot:
    position: int
    task: Task | None = None
    carrying: bool = False
    service_done: int = 0

    @property
    def goal(self) -> int:
        if self.task is None:
            return self.position
        return self.task.dropoff if self.carrying else self.task.pickup


@dataclass(frozen=True)
class SimConfig:
    robots: int = 40
    ticks: int = 1200
    warmup: int = 200
    seed: int = 1
    arrival_rate: float | None = None
    station_time: int = 0
    strict: bool = False

    def __post_init__(self) -> None:
        if self.station_time < 0:
            raise ValueError("station_time cannot be negative")


@dataclass
class Metrics:
    planner: str
    robots: int
    seed: int
    measured_ticks: int
    completed: int = 0
    throughput_per_1000: float = 0.0
    mean_cycle: float = 0.0
    p95_cycle: float = 0.0
    plan_ms_p50: float = 0.0
    plan_ms_p99: float = 0.0
    wait_fraction: float = 0.0
    moves_per_task: float = 0.0
    collisions: int = 0
    longest_stall: int = 0
    tasks_waiting_at_end: int = 0
    fallback_ticks: int = 0
    service_interruptions: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))]


def _poisson(rng: random.Random, rate: float) -> int:
    limit, count, product = math.exp(-rate), 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count


@dataclass
class Simulation:
    warehouse: Warehouse
    planner_name: str
    config: SimConfig = field(default_factory=SimConfig)
    frames: list[tuple[list[int], list[bool]]] = field(default_factory=list)
    record: bool = False

    def run(self) -> Metrics:
        config = self.config
        grid = self.warehouse.grid
        task_rng = random.Random(config.seed)
        plan_rng = random.Random(config.seed + 1_000_003)
        start_cells = [c for c in grid.free_cells() if c not in set(self.warehouse.stations)]
        if config.robots > len(start_cells):
            raise ValueError("more robots than free cells")
        robots = [Robot(cell) for cell in task_rng.sample(start_cells, config.robots)]
        planner = PLANNERS[self.planner_name]()
        planner.reset(grid, config.robots, plan_rng)
        queue: list[Task] = []
        metrics = Metrics(
            self.planner_name, config.robots, config.seed, config.ticks - config.warmup
        )
        cycles: list[float] = []
        plan_ms: list[float] = []
        moves = waits = active = 0
        last_completion = 0

        def new_task(tick: int) -> None:
            queue.append(
                Task(
                    task_rng.choice(self.warehouse.access_cells),
                    task_rng.choice(self.warehouse.stations),
                    tick,
                )
            )

        for tick in range(config.ticks):
            if config.arrival_rate is None:
                while len(queue) < 2 * config.robots:
                    new_task(tick)
            else:
                for _ in range(_poisson(task_rng, config.arrival_rate)):
                    new_task(tick)
            self._assign(robots, queue, tick)
            positions = [robot.position for robot in robots]
            goals = [robot.goal for robot in robots]
            started = time.perf_counter()
            following = planner.plan(positions, goals)
            elapsed = (time.perf_counter() - started) * 1000
            problems = check_step(grid, positions, following)
            if problems and config.strict:
                raise SafetyError(f"tick {tick}: {problems[:3]}")
            measured = tick >= config.warmup
            if measured:
                plan_ms.append(elapsed)
                metrics.collisions += len(problems)
            for robot, cell in zip(robots, following, strict=True):
                in_service = robot.service_done > 0 and robot.position == robot.goal
                if in_service and cell != robot.position and measured:
                    # The planner moved a robot that was still being served at its station.
                    metrics.service_interruptions += 1
                if measured and robot.task is not None and not in_service:
                    active += 1
                    if cell == robot.position:
                        waits += 1
                    else:
                        moves += 1
                robot.position = cell
                if robot.task is None or robot.position != robot.goal:
                    continue
                if not robot.carrying:
                    robot.carrying = True
                    continue
                if robot.service_done < config.station_time:
                    # Service time only counts while the robot is on its station cell.
                    robot.service_done += 1
                    continue
                if measured:
                    metrics.completed += 1
                    cycles.append(tick + 1 - robot.task.assigned)
                robot.task = None
                robot.carrying = False
                robot.service_done = 0
                last_completion = tick
            if measured:
                metrics.longest_stall = max(metrics.longest_stall, tick - last_completion)
            if self.record:
                self.frames.append(
                    ([robot.position for robot in robots], [robot.carrying for robot in robots])
                )
        metrics.throughput_per_1000 = 1000 * metrics.completed / metrics.measured_ticks
        metrics.mean_cycle = sum(cycles) / len(cycles) if cycles else 0.0
        metrics.p95_cycle = percentile(cycles, 0.95)
        metrics.plan_ms_p50 = percentile(plan_ms, 0.50)
        metrics.plan_ms_p99 = percentile(plan_ms, 0.99)
        metrics.wait_fraction = waits / active if active else 0.0
        metrics.moves_per_task = moves / metrics.completed if metrics.completed else 0.0
        metrics.tasks_waiting_at_end = len(queue)
        metrics.fallback_ticks = getattr(planner, "fallback_ticks", 0)
        return metrics

    def _assign(self, robots: list[Robot], queue: list[Task], tick: int) -> None:
        grid = self.warehouse.grid
        for robot in robots:
            if robot.task is not None or not queue:
                continue
            window = queue[: 2 * len(robots)]
            best = min(
                range(len(window)),
                key=lambda i: (grid.distances_to(window[i].pickup)[robot.position], i),
            )
            robot.task = queue.pop(best)
            robot.task.assigned = tick
            robot.carrying = False
