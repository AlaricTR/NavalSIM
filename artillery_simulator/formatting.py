"""Text formatting helpers for simulation output."""
from __future__ import annotations

from typing import List

from .models import SummaryResult


def seconds_to_mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {sec:02d}s"
    return f"{minutes:d}m {sec:02d}s"


def format_summary_table(
    summaries: List[SummaryResult],
) -> str:
    headers = [
        "Retreat @ holes",
        "Runs",
        "Survive %",
        "Flood death %",
        "HP death %",
        "Avg time",
        "Median time",
        "Avg HP left",
        "Avg end holes",
        "Avg flood %",
        "Avg max holes",
        "Avg shells",
        "Avg hits",
        "Avg holes made",
    ]

    rows: List[List[str]] = []
    for summary in summaries:
        rows.append([
            str(summary.retreat_threshold),
            str(summary.simulations),
            f"{summary.survival_pct:.1f}",
            f"{summary.flooding_death_pct:.1f}",
            f"{summary.hp_death_pct:.1f}",
            seconds_to_mmss(summary.avg_time_s),
            seconds_to_mmss(summary.median_time_s),
            f"{summary.avg_hp_left:.0f}",
            f"{summary.avg_active_holes_end:.1f}",
            f"{summary.avg_flooding_pct_end:.1f}",
            f"{summary.avg_max_holes:.1f}",
            f"{summary.avg_shells_fired:.1f}",
            f"{summary.avg_damaging_hits:.1f}",
            f"{summary.avg_holes_created:.1f}",
        ])

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(values: List[str]) -> str:
        return " | ".join(
            str(value).rjust(widths[index])
            for index, value in enumerate(values)
        )

    divider = "-+-".join("-" * width for width in widths)
    output = [format_row(headers), divider]
    output.extend(format_row(row) for row in rows)
    return "\n".join(output)
