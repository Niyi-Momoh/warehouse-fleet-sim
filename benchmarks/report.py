"""Turn results/benchmark.json into the README table, a chart and an animation."""

from __future__ import annotations

import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

START = "<!-- results:start -->"
END = "<!-- results:end -->"
NAMES = {"greedy": "Greedy baseline", "pibt": "PIBT", "whca": "WHCA* with PIBT fallback"}
COORDINATED = ("pibt", "whca")


def grouped(study: dict) -> dict[tuple[str, int], list[dict]]:
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for run in study["runs"]:
        groups[run["planner"], run["robots"]].append(run)
    return groups


def _mean(group: list[dict], key: str) -> float:
    return st.mean(run[key] for run in group)


def _task_time(group: list[dict]) -> str:
    return f"{_mean(group, 'mean_cycle'):.1f}" if _mean(group, "completed") else "None finished"


def render(study: dict) -> str:
    groups = grouped(study)
    fleets = sorted({key[1] for key in groups})
    runs = study["runs"]
    lines = [
        f"{len(runs)} runs on a {study['warehouse']['width']} by "
        f"{study['warehouse']['height']} warehouse with {study['warehouse']['free_cells']} "
        f"free cells and {study['warehouse']['stations']} stations. Each run lasts "
        f"{study['ticks']} ticks, and the first {study['warmup']} are excluded. Figures are "
        f"means over {len(study['seeds'])} seeds.",
        "",
        "| Robots | Planner | Tasks per 1,000 ticks | Mean task time (ticks) | Waiting "
        "| Plan time p99 (ms) | Longest stall (ticks) | Fallback ticks |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for robots in fleets:
        for planner, label in NAMES.items():
            group = groups[planner, robots]
            lines.append(
                f"| {robots} | {label} | {_mean(group, 'throughput_per_1000'):.0f} | "
                f"{_task_time(group)} | {_mean(group, 'wait_fraction') * 100:.0f}% | "
                f"{_mean(group, 'plan_ms_p99'):.2f} | {max(r['longest_stall'] for r in group)} | "
                f"{_mean(group, 'fallback_ticks'):.0f} |"
            )
    violations = sum(run["collisions"] for run in runs)
    at_80 = [run for run in runs if run["robots"] == 80 and run["planner"] in COORDINATED]
    worst_p99 = max(run["plan_ms_p99"] for run in at_80)
    coordinated = [run for run in runs if run["planner"] in COORDINATED]
    worst_stall = max(run["longest_stall"] for run in coordinated)
    verdict = lambda ok: "Pass" if ok else "Fail"  # noqa: E731
    lines += [
        "",
        "| Success criterion, set before the benchmark | Measured | Result |",
        "|---|---:|---|",
        f"| No safety violations in any run | {violations} | {verdict(violations == 0)} |",
        f"| Coordinated plan time p99 at most 50 ms at 80 robots | {worst_p99:.2f} ms | "
        f"{verdict(worst_p99 <= 50)} |",
        f"| Coordinated planners never stall over 100 ticks | {worst_stall} ticks | "
        f"{verdict(worst_stall <= 100)} |",
    ]
    gains = [
        _mean(groups["whca", robots], "throughput_per_1000")
        / _mean(groups["pibt", robots], "throughput_per_1000")
        - 1
        for robots in fleets
        if robots <= 60
    ]
    costs = [
        _mean(groups["whca", robots], "plan_ms_p99") / _mean(groups["pibt", robots], "plan_ms_p99")
        for robots in fleets
        if robots <= 60
    ]
    heavy = groups["whca", 80]
    lines += [
        "",
        f"- WHCA* completed {min(gains) * 100:.0f}% to {max(gains) * 100:.0f}% more tasks than "
        f"PIBT with 10 to 60 robots, with p99 planning time {min(costs):.0f} to "
        f"{max(costs):.0f} times higher.",
        f"- At 80 robots WHCA* used its PIBT fallback on "
        f"{_mean(heavy, 'fallback_ticks') / study['ticks'] * 100:.0f}% of ticks, so the two "
        "planners perform almost identically at that density and above.",
    ]
    return "\n".join(lines)


def block(study: dict) -> str:
    return f"{START}\n{render(study)}\n{END}"


def chart(study: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    groups = grouped(study)
    fleets = sorted({key[1] for key in groups})
    colours = {"greedy": "#9ca3af", "pibt": "#2563eb", "whca": "#ea580c"}
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    for planner, label in NAMES.items():
        values = [
            [run["throughput_per_1000"] for run in groups[planner, robots]] for robots in fleets
        ]
        ax.errorbar(
            fleets,
            [st.mean(v) for v in values],
            yerr=[st.stdev(v) for v in values],
            label=label,
            color=colours[planner],
            marker="o",
            capsize=3,
            lw=2,
        )
    ax.set_xlabel("Robots")
    ax.set_ylabel("Tasks completed per 1,000 ticks")
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig("results/throughput.png")
    plt.close(fig)


def animation(frames_count: int = 120, scale: int = 12) -> None:
    from PIL import Image, ImageDraw

    from fleet_sim.layout import make_warehouse
    from fleet_sim.simulator import SimConfig, Simulation

    warehouse = make_warehouse()
    grid = warehouse.grid
    panels = []
    for planner in ("greedy", "pibt"):
        config = SimConfig(robots=40, ticks=frames_count, warmup=0, seed=2)
        simulation = Simulation(warehouse, planner, config, record=True)
        simulation.run()
        panels.append((planner, simulation.frames))
    gap, header = 12, 18
    width = 2 * grid.width * scale + gap
    height = grid.height * scale + header
    images = []
    for index in range(frames_count):
        image = Image.new("P", (width, height), 0)
        image.putpalette(
            [255, 255, 255, 17, 24, 39, 203, 213, 225, 37, 99, 235, 234, 88, 12] + [255] * 3 * 250
        )
        draw = ImageDraw.Draw(image)
        for panel, (planner, frames) in enumerate(panels):
            left = panel * (grid.width * scale + gap)
            draw.text((left + 2, 3), NAMES[planner], fill=1)
            for cell in range(grid.size):
                if not grid.free[cell]:
                    x, y = grid.xy(cell)
                    draw.rectangle(
                        (
                            left + x * scale,
                            header + y * scale,
                            left + (x + 1) * scale - 2,
                            header + (y + 1) * scale - 2,
                        ),
                        fill=2,
                    )
            positions, carrying = frames[index]
            for cell, loaded in zip(positions, carrying, strict=True):
                x, y = grid.xy(cell)
                draw.ellipse(
                    (
                        left + x * scale + 1,
                        header + y * scale + 1,
                        left + (x + 1) * scale - 3,
                        header + (y + 1) * scale - 3,
                    ),
                    fill=4 if loaded else 3,
                )
        images.append(image)
    images[0].save(
        "results/fleet.gif",
        save_all=True,
        append_images=images[1:],
        duration=110,
        loop=0,
        optimize=False,
        disposal=1,
    )


STATION_START = "<!-- station:start -->"
STATION_END = "<!-- station:end -->"


def render_station(study: dict) -> str:
    groups: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for run in study["runs"]:
        groups[run["planner"], run["robots"], run["station_time"]].append(run)
    stations = study["stations"]
    lines = [
        f"Means over {len(study['seeds'])} seeds. Capacity is the most tasks per 1,000 ticks "
        f"that {stations} stations could handle if a new robot arrived the moment the last "
        "one left.",
        "",
        "| Planner | Robots | Station time (ticks) | Tasks per 1,000 ticks | Station capacity "
        "| Mean task time (ticks) | Robots pushed off a station mid-service |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for planner, robots, station_time in sorted(groups):
        group = groups[planner, robots, station_time]
        capacity = f"{stations * 1000 / (station_time + 1):.0f}" if station_time else "Not limiting"
        lines.append(
            f"| {NAMES[planner]} | {robots} | {station_time} | "
            f"{_mean(group, 'throughput_per_1000'):.0f} | {capacity} | "
            f"{_task_time(group)} | {_mean(group, 'service_interruptions'):.0f} |"
        )
    return "\n".join(lines)


def station_block(study: dict) -> str:
    return f"{STATION_START}\n{render_station(study)}\n{STATION_END}"


def _replace(text: str, start: str, end: str, content: str) -> str:
    return re.sub(re.escape(start) + ".*?" + re.escape(end), lambda _: content, text, flags=re.S)


def main() -> None:
    study = json.loads(Path("results/benchmark.json").read_text())
    readme = Path("README.md")
    text = _replace(readme.read_text(), START, END, block(study))
    station_file = Path("results/station_time.json")
    if station_file.exists():
        stations = json.loads(station_file.read_text())
        text = _replace(text, STATION_START, STATION_END, station_block(stations))
    readme.write_text(text)
    if "--text-only" not in sys.argv:
        chart(study)
        animation()


if __name__ == "__main__":
    main()
