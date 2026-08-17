"""Text formatting helpers for ship and duel result tabs."""
from __future__ import annotations

from typing import List

from .models import DuelSummaryResult, SummaryResult


def seconds_to_mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {sec:02d}s"
    return f"{minutes:d}m {sec:02d}s"


def _format_table(headers: List[str], rows: List[List[str]]) -> str:
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


def format_summary_table(summaries: List[SummaryResult]) -> str:
    headers = [
        "Retreat @ holes", "Runs", "Survive %", "Flood death %",
        "HP death %", "Avg time", "Median time", "Avg HP left",
        "Avg end holes", "Avg flood %", "Avg max holes", "Avg shells",
        "Avg hits", "Avg holes made",
    ]
    rows = [
        [
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
        ]
        for summary in summaries
    ]
    return _format_table(headers, rows)


def format_duel_summary_table(summaries: List[DuelSummaryResult]) -> str:
    headers = [
        "Retreat @ holes", "Runs", "Forced retreat %", "Battery dead first %",
        "Ship destroyed %", "Tie %", "Timeout %", "Avg time in fight",
        "Median time", "Avg death time", "Avg guns destroyed",
        "Avg guns left", "Avg battery HP", "Ship flood %", "Ship shells",
        "Gun impacts", "Retargets",
    ]
    rows: List[List[str]] = []
    for summary in summaries:
        death_time = (
            seconds_to_mmss(summary.avg_battery_death_time_s)
            if summary.avg_battery_death_time_s is not None
            else "—"
        )
        rows.append([
            str(summary.retreat_threshold),
            str(summary.simulations),
            f"{summary.forced_retreat_pct:.1f}",
            f"{summary.battery_dead_first_pct:.1f}",
            f"{summary.ship_destroyed_pct:.1f}",
            f"{summary.simultaneous_pct:.1f}",
            f"{summary.timeout_pct:.1f}",
            seconds_to_mmss(summary.avg_battery_time_in_fight_s),
            seconds_to_mmss(summary.median_battery_time_in_fight_s),
            death_time,
            f"{summary.avg_guns_destroyed:.2f}",
            f"{summary.avg_guns_remaining:.2f}",
            f"{summary.avg_battery_hp_left:.0f}",
            f"{summary.avg_ship_flooding_pct:.1f}",
            f"{summary.avg_ship_shells_fired:.1f}",
            f"{summary.avg_ship_shell_impacts:.1f}",
            f"{summary.avg_retargets:.2f}",
        ])
    return _format_table(headers, rows)
