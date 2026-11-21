# SPDX-License-Identifier: MIT
# Copyright (c) 2026 opopile (comprehensive-weight-space-programming-leaderboard contributors)
"""Generate four publication-grade English-annotated charts from the unified dataset.

Reads data/leaderboard_models.json and data/seaquest_ablation.json and produces:
  - charts/chart1_wwi_leaderboard.png
  - charts/chart2_wsb_median_leaderboard.png
  - charts/chart3_per_game_comparison.png
  - charts/chart4_seaquest_ablation.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


# Okabe-Ito inspired colorblind-safe palette
COLOR_NEON = "#D55E00"
COLOR_NEON_EDGE = "#7A2E00"
COLOR_NEON_BAND = "#FFF3E8"

COLOR_CLEAN = "#0072B2"
COLOR_CLEAN_EDGE = "#004B75"

COLOR_REPORTED = "#6C8EAD"
COLOR_REPORTED_EDGE = "#334155"

COLOR_BASELINE = "#4B5563"
COLOR_BASELINE_EDGE = "#111827"

COLOR_PROMPTED = "#D55E00"
COLOR_PROMPTED_EDGE = "#7A2E00"
COLOR_BASE_RUN = "#0072B2"
COLOR_BASE_RUN_EDGE = "#004B75"

COLOR_REF_PPO500 = "#DC2626"
COLOR_REF_PPO100 = "#7C3AED"

TEXT_DARK = "#0F172A"
TEXT_MUTED = "#475569"
TEXT_FOOTER = "#475569"
GRID_COLOR = "#CBD5E1"


def configure_matplotlib(dpi: int = 300) -> None:
    """Configure deterministic, cross-platform pure-ASCII sans-serif styling."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Segoe UI", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.dpi": dpi,
            "savefig.dpi": dpi,
            "axes.edgecolor": "#94A3B8",
            "axes.linewidth": 0.9,
            "xtick.color": TEXT_DARK,
            "ytick.color": TEXT_DARK,
        }
    )


def _save_figure(fig: plt.Figure, out_path: Path, title: str, dpi: int) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out_path,
        format="png",
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.3,
        facecolor="white",
        edgecolor="none",
        metadata={"Software": "matplotlib", "Title": title},
    )
    plt.close(fig)
    return out_path


def _wwi_value(rec: dict[str, Any]) -> float:
    if rec["per_game_scores_disclosed"] and rec["computed_wwi"] is not None:
        return float(rec["computed_wwi"])
    return float(rec["reported_wwi"])


def _wwi_sort_key(rec: dict[str, Any]) -> tuple[float, float, str]:
    wwi_val = _wwi_value(rec)
    wsb_tie = float(rec["computed_wsb_median"]) if rec["computed_wsb_median"] is not None else -1e9
    return (-round(wwi_val, 4), -wsb_tie, str(rec["model_name"]))


def _wsb_sort_key(rec: dict[str, Any]) -> tuple[float, str]:
    return (-round(float(rec["computed_wsb_median"]), 4), str(rec["model_name"]))


def _draw_two_line_ylabels(
    ax: plt.Axes,
    rows: list[dict[str, Any]],
    rank_labels: list[str],
    highlight_id: str,
    x_offset: float = -0.012,
    line1_size: float = 9.4,
    line2_size: float = 7.5,
) -> None:
    """Render two-line left-margin protocol labels using blended y-axis transform."""
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([])
    ax.tick_params(axis="y", length=0)

    trans = ax.get_yaxis_transform()
    for idx, (rec, rtag) in enumerate(zip(rows, rank_labels)):
        is_neon = rec["id"] == highlight_id
        is_base = rec["tier"] == "baseline"
        title_color = COLOR_NEON_EDGE if is_neon else (TEXT_MUTED if is_base else TEXT_DARK)

        line1 = f"{rtag}  {rec['model_name']}  |  {rec['source']}"
        line2 = f"Effort: {rec['thinking_effort']}  |  {rec['platform_api']}  |  {rec['attempts']}"

        ax.text(
            x_offset,
            idx - 0.14,
            line1,
            transform=trans,
            ha="right",
            va="center",
            fontsize=line1_size,
            fontweight="bold",
            color=title_color,
            clip_on=False,
        )
        ax.text(
            x_offset,
            idx + 0.19,
            line2,
            transform=trans,
            ha="right",
            va="center",
            fontsize=line2_size,
            fontweight="normal",
            color=TEXT_MUTED,
            clip_on=False,
        )


def _assign_ranks(rows: list[dict[str, Any]]) -> list[str]:
    ranks: list[str] = []
    counter = 0
    for rec in rows:
        if rec["tier"] == "baseline":
            ranks.append("Ref")
        else:
            counter += 1
            ranks.append(f"#{counter}")
    return ranks


def generate_chart1(models_payload: dict[str, Any], out_dir: Path, dpi: int = 300) -> Path:
    """Chart 1: Writing Weights Index (WWI) Comprehensive Leaderboard."""
    models: list[dict[str, Any]] = models_payload["models"]
    by_id = {m["id"]: m for m in models}
    rows = sorted([m for m in models if m["include_in_main_wwi"]], key=_wwi_sort_key)
    rank_tags = _assign_ranks(rows)

    ppo500_wwi = _wwi_value(by_id["ppo_500m_mit"])
    ppo100_wwi = _wwi_value(by_id["ppo_100m_mit"])

    n = len(rows)
    n_base = sum(1 for r in rows if r["tier"] == "baseline")
    n_llm = n - n_base
    n_excl = sum(1 for m in models if not m["include_in_main_wwi"])
    y_pos = np.arange(n)
    values = [_wwi_value(r) for r in rows]

    fig_h = max(20.8, 0.63 * n)
    fig, ax = plt.subplots(figsize=(17.5, fig_h))
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.39, right=0.96, top=0.865, bottom=0.050)

    for idx, rec in enumerate(rows):
        if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
            ax.axhspan(idx - 0.45, idx + 0.45, color=COLOR_NEON_BAND, zorder=0)

    # Vertical reference lines
    ax.axvline(ppo500_wwi, color=COLOR_REF_PPO500, linestyle="--", linewidth=1.6, zorder=1)
    ax.axvline(ppo100_wwi, color=COLOR_REF_PPO100, linestyle="-.", linewidth=1.5, zorder=1)

    # Top-margin reference line tags (above bars, below legend)
    x_trans = ax.get_xaxis_transform()
    ax.text(
        ppo500_wwi,
        1.006,
        f"PPO-500M = {ppo500_wwi:.1f}",
        transform=x_trans,
        ha="center",
        va="bottom",
        fontsize=8.8,
        fontweight="bold",
        color=COLOR_REF_PPO500,
        zorder=5,
    )
    ax.text(
        ppo100_wwi,
        1.006,
        f"PPO-100M = {ppo100_wwi:.1f}",
        transform=x_trans,
        ha="center",
        va="bottom",
        fontsize=8.8,
        fontweight="bold",
        color=COLOR_REF_PPO100,
        zorder=5,
    )

    for idx, (rec, val) in enumerate(zip(rows, values)):
        if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
            fc, ec, lw, hatch = COLOR_NEON, COLOR_NEON_EDGE, 1.5, None
        elif rec["tier"] == "baseline":
            fc, ec, lw, hatch = COLOR_BASELINE, COLOR_BASELINE_EDGE, 0.9, ".."
        elif rec["tier"] == "reported_wwi_only":
            fc, ec, lw, hatch = COLOR_REPORTED, COLOR_REPORTED_EDGE, 0.9, "///"
        else:
            fc, ec, lw, hatch = COLOR_CLEAN, COLOR_CLEAN_EDGE, 0.8, None

        ax.barh(
            idx,
            val,
            height=0.66,
            color=fc,
            edgecolor=ec,
            linewidth=lw,
            hatch=hatch,
            zorder=3,
        )

        if rec["id"] == "gpt_6_astra_mit":
            rep = float(rec["reported_wwi"])
            val_label = f"{val:.2f} ({rep:.1f} reported in Dang)"
            t_color, t_weight = TEXT_DARK, "bold"
        elif rec["id"] == "claude_fable_5_2_high_shawnghu":
            val_label = f"{val:.2f}  [9/9 end_turn]"
            t_color, t_weight = TEXT_DARK, "bold"
        elif rec["id"] == "claude_fable_5_2_xhigh_shawnghu":
            val_label = f"{val:.2f}  [8/9 hit 128k cap; 1 Seaquest = 66.1]"
            t_color, t_weight = TEXT_MUTED, "normal"
        elif rec["id"] == "gemini_4_neon_xhigh_local_baseline":
            val_label = f"{val:.2f}  [Local Baseline]"
            t_color, t_weight = COLOR_NEON_EDGE, "bold"
        elif rec["tier"] == "reported_wwi_only":
            val_label = f"{val:.1f} [reported WWI]"
            t_color, t_weight = TEXT_DARK, "normal"
        elif rec["tier"] == "baseline":
            val_label = f"{val:.2f} [RL baseline]"
            t_color, t_weight = TEXT_MUTED, "bold"
        else:
            val_label = f"{val:.2f}"
            t_color, t_weight = TEXT_DARK, "normal"

        bbox_fc = COLOR_NEON_BAND if rec["id"] == "gemini_4_neon_xhigh_local_baseline" else "white"
        ax.text(
            val + 0.75,
            idx,
            val_label,
            va="center",
            ha="left",
            fontsize=8.6,
            fontweight=t_weight,
            color=t_color,
            zorder=5,
            bbox=dict(facecolor=bbox_fc, edgecolor="none", pad=0.8, alpha=1.0),
        )

    _draw_two_line_ylabels(ax, rows, rank_tags, highlight_id="gemini_4_neon_xhigh_local_baseline")

    ax.set_xlim(0, 88)
    ax.set_ylim(n - 0.35, -0.75)
    ax.set_xticks([0, 10, 20, 30, 40, 50, 60, 70, 80])
    ax.set_xlabel("Writing Weights Index (WWI, 0-100 scale)", fontsize=10.5, fontweight="bold", color=TEXT_DARK, labelpad=8)

    ax.xaxis.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.75, zorder=1)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_handles = [
        mpatches.Patch(facecolor=COLOR_NEON, edgecolor=COLOR_NEON_EDGE, linewidth=1.3, label="Gemini 4 Neon (XHigh) - Local Baseline"),
        mpatches.Patch(facecolor=COLOR_CLEAN, edgecolor=COLOR_CLEAN_EDGE, linewidth=0.9, label="Computed WWI (Full 3-Game Scores)"),
        mpatches.Patch(facecolor=COLOR_REPORTED, edgecolor=COLOR_REPORTED_EDGE, hatch="///", linewidth=0.9, label="Reported WWI (Per-Game Undisclosed)"),
        mpatches.Patch(facecolor=COLOR_BASELINE, edgecolor=COLOR_BASELINE_EDGE, hatch="..", linewidth=0.9, label="RL Reference Baseline"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.036),
        ncol=2,
        frameon=True,
        facecolor="#F8FAFC",
        edgecolor="#CBD5E1",
        fontsize=9.2,
        columnspacing=1.8,
        handletextpad=0.7,
    )

    fig.text(
        0.50,
        0.965,
        "Writing Weights Index (WWI) - Comprehensive MinAtar Experiment 5 Leaderboard",
        ha="center",
        va="top",
        fontsize=15.0,
        fontweight="bold",
        color=TEXT_DARK,
    )
    fig.text(
        0.50,
        0.943,
        f"{n_llm} Verbatim-Prompt LLM Entries + {n_base} RL Reference Baselines (n = {n}) | WWI = mean_3games [100 * q / (1 + q)], q = max(0, score - Random) / (PPO-500M - Random)",
        ha="center",
        va="top",
        fontsize=9.6,
        color=TEXT_MUTED,
    )

    baselines = models_payload["metadata"]["baselines"]
    p5 = baselines["ppo500"]
    rp = baselines["random_paper"]
    footer = (
        f"Paper Baselines: PPO-500M ({p5['breakout']} / {p5['seaquest']} / {p5['asterix']}) & "
        f"Random ({rp['breakout']} / {rp['seaquest']} / {rp['asterix']}). "
        f"Excluded from verbatim main rankings (n = {n_excl}): 4 cap-resumed runs, 1 medians-only run, 1 Seaquest prompt-intervention ablation."
    )
    fig.text(0.50, 0.015, footer, ha="center", va="bottom", fontsize=8.3, color=TEXT_FOOTER)

    return _save_figure(
        fig,
        out_dir / "chart1_wwi_leaderboard.png",
        "Writing Weights Index (WWI) Comprehensive MinAtar Experiment 5 Leaderboard",
        dpi=dpi,
    )


def generate_chart2(models_payload: dict[str, Any], out_dir: Path, dpi: int = 300) -> Path:
    """Chart 2: weight-space-bench (WSB) PPO-500M Median Normalized Leaderboard."""
    models: list[dict[str, Any]] = models_payload["models"]
    by_id = {m["id"]: m for m in models}
    rows = sorted([m for m in models if m["include_in_main_wsb"]], key=_wsb_sort_key)
    rank_tags = _assign_ranks(rows)

    ppo500_wsb = float(by_id["ppo_500m_mit"]["computed_wsb_median"])
    ppo100_wsb = float(by_id["ppo_100m_mit"]["computed_wsb_median"])

    n = len(rows)
    n_base = sum(1 for r in rows if r["tier"] == "baseline")
    n_llm = n - n_base
    n_excl = sum(1 for m in models if not m["include_in_main_wsb"])
    values = [float(r["computed_wsb_median"]) for r in rows]

    fig_h = max(14.8, 0.64 * n)
    fig, ax = plt.subplots(figsize=(17.5, fig_h))
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.39, right=0.96, top=0.870, bottom=0.070)

    for idx, rec in enumerate(rows):
        if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
            ax.axhspan(idx - 0.45, idx + 0.45, color=COLOR_NEON_BAND, zorder=0)

    ax.axvline(ppo500_wsb, color=COLOR_REF_PPO500, linestyle="--", linewidth=1.6, zorder=1)
    ax.axvline(ppo100_wsb, color=COLOR_REF_PPO100, linestyle="-.", linewidth=1.5, zorder=1)

    x_trans = ax.get_xaxis_transform()
    ax.text(
        ppo500_wsb,
        1.008,
        f"PPO-500M = {ppo500_wsb:.1f}",
        transform=x_trans,
        ha="center",
        va="bottom",
        fontsize=8.8,
        fontweight="bold",
        color=COLOR_REF_PPO500,
        zorder=5,
    )
    ax.text(
        ppo100_wsb,
        1.008,
        f"PPO-100M = {ppo100_wsb:.1f}",
        transform=x_trans,
        ha="center",
        va="bottom",
        fontsize=8.8,
        fontweight="bold",
        color=COLOR_REF_PPO100,
        zorder=5,
    )

    for idx, (rec, val) in enumerate(zip(rows, values)):
        if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
            fc, ec, lw, hatch = COLOR_NEON, COLOR_NEON_EDGE, 1.5, None
        elif rec["tier"] == "baseline":
            fc, ec, lw, hatch = COLOR_BASELINE, COLOR_BASELINE_EDGE, 0.9, ".."
        else:
            fc, ec, lw, hatch = COLOR_CLEAN, COLOR_CLEAN_EDGE, 0.8, None

        ax.barh(
            idx,
            val,
            height=0.66,
            color=fc,
            edgecolor=ec,
            linewidth=lw,
            hatch=hatch,
            zorder=3,
        )

        if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
            val_label = f"{val:.2f} ({val:.1f})  [Local Baseline]"
            t_color, t_weight = COLOR_NEON_EDGE, "bold"
        elif rec["id"] == "claude_fable_5_2_high_shawnghu":
            val_label = f"{val:.2f}  [9/9 end_turn]"
            t_color, t_weight = TEXT_DARK, "bold"
        elif rec["id"] == "claude_fable_5_2_xhigh_shawnghu":
            val_label = f"{val:.2f}  [8/9 hit 128k cap]"
            t_color, t_weight = TEXT_MUTED, "normal"
        elif rec["tier"] == "baseline":
            val_label = f"{val:.2f} [RL baseline]"
            t_color, t_weight = TEXT_MUTED, "bold"
        else:
            val_label = f"{val:.2f}"
            t_color, t_weight = TEXT_DARK, "normal"

        bbox_fc = COLOR_NEON_BAND if rec["id"] == "gemini_4_neon_xhigh_local_baseline" else "white"
        ax.text(
            val + 1.3,
            idx,
            val_label,
            va="center",
            ha="left",
            fontsize=8.7,
            fontweight=t_weight,
            color=t_color,
            zorder=5,
            bbox=dict(facecolor=bbox_fc, edgecolor="none", pad=0.8, alpha=1.0),
        )

    _draw_two_line_ylabels(ax, rows, rank_tags, highlight_id="gemini_4_neon_xhigh_local_baseline")

    ax.set_xlim(0, 162)
    ax.set_ylim(n - 0.35, -0.75)
    ax.set_xticks([0, 20, 40, 60, 80, 100, 120, 140, 160])
    ax.set_xlabel(
        "WSB Median Normalized Score (% of PPO-500M above Random)",
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_DARK,
        labelpad=8,
    )

    ax.xaxis.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.75, zorder=1)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_handles = [
        mpatches.Patch(facecolor=COLOR_NEON, edgecolor=COLOR_NEON_EDGE, linewidth=1.3, label="Gemini 4 Neon (XHigh) - Local Baseline"),
        mpatches.Patch(facecolor=COLOR_CLEAN, edgecolor=COLOR_CLEAN_EDGE, linewidth=0.9, label="Clean 3-Game Verbatim Run"),
        mpatches.Patch(facecolor=COLOR_BASELINE, edgecolor=COLOR_BASELINE_EDGE, hatch="..", linewidth=0.9, label="RL Reference Baseline"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.042),
        ncol=3,
        frameon=True,
        facecolor="#F8FAFC",
        edgecolor="#CBD5E1",
        fontsize=9.2,
        columnspacing=1.8,
        handletextpad=0.7,
    )

    fig.text(
        0.52,
        0.962,
        "weight-space-bench (WSB) PPO-500M Median Normalized Leaderboard",
        ha="center",
        va="top",
        fontsize=15.0,
        fontweight="bold",
        color=TEXT_DARK,
    )
    fig.text(
        0.52,
        0.935,
        f"{n_llm} Clean Verbatim 3-Game LLM Runs + {n_base} RL Reference Baselines (n = {n}) | WSB = 100 * median_3games [(score - Random) / (PPO-500M - Random)]",
        ha="center",
        va="top",
        fontsize=9.6,
        color=TEXT_MUTED,
    )

    footer = (
        f"Excluded from WSB Median (n = {n_excl}): 10 reported_wwi_only entries (N/A: per-game scores not publicly disclosed) "
        "+ 6 non-clean entries (4 cap-resumed runs, 1 medians-only run, 1 Seaquest prompt-intervention ablation)."
    )
    fig.text(0.52, 0.018, footer, ha="center", va="bottom", fontsize=8.3, color=TEXT_FOOTER)

    return _save_figure(
        fig,
        out_dir / "chart2_wsb_median_leaderboard.png",
        "weight-space-bench (WSB) PPO-500M Median Normalized Leaderboard",
        dpi=dpi,
    )


def generate_chart3(models_payload: dict[str, Any], out_dir: Path, dpi: int = 300) -> Path:
    """Chart 3: 1x3 per-game MinAtar comparison across 13 core models."""
    models: list[dict[str, Any]] = models_payload["models"]
    by_id = {m["id"]: m for m in models}
    ppo500 = models_payload["metadata"]["baselines"]["ppo500"]
    ppo100_wsb = float(by_id["ppo_100m_mit"]["computed_wsb_median"])

    # Exact 13 core models: 11 clean 3-game LLMs exceeding PPO-100M on WSB Median + PPO-500M + PPO-100M
    core_rows = sorted(
        [
            m
            for m in models
            if m["include_in_main_wsb"] and float(m["computed_wsb_median"]) >= ppo100_wsb - 1e-6
        ],
        key=_wsb_sort_key,
    )
    rank_tags = _assign_ranks(core_rows)

    n = len(core_rows)
    n_base = sum(1 for r in core_rows if r["tier"] == "baseline")
    n_llm = n - n_base
    fig_h = max(9.6, 0.74 * n)
    fig, axes = plt.subplots(
        1,
        3,
        sharey=True,
        figsize=(19.2, fig_h),
        gridspec_kw={"wspace": 0.12, "left": 0.27, "right": 0.975, "top": 0.805, "bottom": 0.125},
    )
    fig.patch.set_facecolor("white")

    panels = [
        ("breakout", "MinAtar Breakout\n(Mean Episode Return)", float(ppo500["breakout"]), (0, 770), [0, 150, 300, 450, 600, 750], "left"),
        ("seaquest", "MinAtar Seaquest\n(Mean Episode Return)", float(ppo500["seaquest"]), (0, 108), [0, 20, 40, 60, 80, 100], "right"),
        ("asterix", "MinAtar Asterix\n(Mean Episode Return)", float(ppo500["asterix"]), (0, 96), [0, 20, 40, 60, 80], "right"),
    ]

    for ax, (game, title, ppo_val, xlim, xticks, tag_ha) in zip(axes, panels):
        for idx, rec in enumerate(core_rows):
            if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
                ax.axhspan(idx - 0.45, idx + 0.45, color=COLOR_NEON_BAND, zorder=0)

        ax.axvline(ppo_val, color=COLOR_REF_PPO500, linestyle="--", linewidth=1.6, zorder=1)

        tag_x = ppo_val + 10.0 if tag_ha == "left" else (ppo_val - 1.5 if tag_ha == "right" else ppo_val)
        ax.text(
            tag_x,
            -0.84,
            f"PPO-500M = {ppo_val:.1f}",
            ha=tag_ha,
            va="center",
            fontsize=8.3,
            fontweight="bold",
            color=COLOR_REF_PPO500,
            zorder=5,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=1.0),
        )

        for idx, rec in enumerate(core_rows):
            g_score = rec["scores"][game]
            mean_val = float(g_score["mean"])
            se_val = float(g_score["se"]) if g_score.get("se") is not None else None

            if rec["id"] == "gemini_4_neon_xhigh_local_baseline":
                fc, ec, lw, hatch = COLOR_NEON, COLOR_NEON_EDGE, 1.4, None
            elif rec["tier"] == "baseline":
                fc, ec, lw, hatch = COLOR_BASELINE, COLOR_BASELINE_EDGE, 0.9, ".."
            else:
                fc, ec, lw, hatch = COLOR_CLEAN, COLOR_CLEAN_EDGE, 0.8, None

            ax.barh(
                idx,
                mean_val,
                height=0.62,
                color=fc,
                edgecolor=ec,
                linewidth=lw,
                hatch=hatch,
                zorder=3,
            )

            if se_val is not None and se_val > 0:
                ax.errorbar(
                    mean_val,
                    idx,
                    xerr=se_val,
                    fmt="none",
                    ecolor="#1E293B",
                    elinewidth=1.1,
                    capsize=2.5,
                    zorder=4,
                )

            if se_val is not None and se_val > 0:
                if mean_val < 10:
                    val_str = f"{mean_val:.2f} +/- {se_val:.2f}"
                else:
                    val_str = f"{mean_val:.1f} +/- {se_val:.1f}"
            else:
                if mean_val < 10:
                    val_str = f"{mean_val:.2f}"
                else:
                    val_str = f"{mean_val:.1f}"

            x_text = mean_val + (se_val if se_val is not None and se_val > 0 else 0.0) + 0.016 * xlim[1]
            t_color = COLOR_NEON_EDGE if rec["id"] == "gemini_4_neon_xhigh_local_baseline" else TEXT_DARK
            t_weight = "bold" if rec["id"] == "gemini_4_neon_xhigh_local_baseline" else "normal"

            bbox_fc = COLOR_NEON_BAND if rec["id"] == "gemini_4_neon_xhigh_local_baseline" else "white"
            ax.text(
                x_text,
                idx,
                val_str,
                va="center",
                ha="left",
                fontsize=8.0,
                fontweight=t_weight,
                color=t_color,
                zorder=5,
                bbox=dict(facecolor=bbox_fc, edgecolor="none", pad=0.7, alpha=1.0),
            )

        ax.set_title(title, fontsize=11.0, fontweight="bold", color=TEXT_DARK, pad=10)
        ax.set_xlim(xlim)
        ax.set_xticks(xticks)
        ax.set_ylim(n - 0.35, -1.25)
        ax.xaxis.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.75, zorder=1)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    _draw_two_line_ylabels(
        axes[0],
        core_rows,
        rank_tags,
        highlight_id="gemini_4_neon_xhigh_local_baseline",
        x_offset=-0.025,
        line1_size=9.1,
        line2_size=7.4,
    )

    legend_handles = [
        mpatches.Patch(facecolor=COLOR_NEON, edgecolor=COLOR_NEON_EDGE, linewidth=1.3, label="Gemini 4 Neon (XHigh) - Local Baseline"),
        mpatches.Patch(facecolor=COLOR_CLEAN, edgecolor=COLOR_CLEAN_EDGE, linewidth=0.9, label="Clean 3-Game Verbatim LLM"),
        mpatches.Patch(facecolor=COLOR_BASELINE, edgecolor=COLOR_BASELINE_EDGE, hatch="..", linewidth=0.9, label="RL Baseline (PPO)"),
        Line2D([0], [0], color=COLOR_REF_PPO500, linestyle="--", linewidth=1.6, label="PPO-500M Reference"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.61, 0.908),
        ncol=4,
        frameon=True,
        facecolor="#F8FAFC",
        edgecolor="#CBD5E1",
        fontsize=9.2,
        columnspacing=1.5,
        handletextpad=0.6,
    )

    fig.text(
        0.55,
        0.968,
        "Per-Game MinAtar Experiment 5 Comparison (Independent Scales)",
        ha="center",
        va="top",
        fontsize=15.0,
        fontweight="bold",
        color=TEXT_DARK,
    )
    fig.text(
        0.55,
        0.935,
        f"{n_llm} Clean 3-Game LLM Runs Exceeding PPO-100M on WSB Median + PPO-500M & PPO-100M Baselines (ordered by WSB Median; n = {n})",
        ha="center",
        va="top",
        fontsize=9.8,
        color=TEXT_MUTED,
    )

    footer = (
        "Evaluated on 600-32-32-6 tanh policy networks over 1,000 MinAtar episodes. "
        "Error bars show +/-1 SE where disclosed (1,000-episode SE for n=1 runs; run-to-run SE across n=3 networks for yzw-22 & shawnghu; omitted if SE undisclosed)."
    )
    fig.text(0.55, 0.025, footer, ha="center", va="bottom", fontsize=8.4, color=TEXT_FOOTER)

    return _save_figure(
        fig,
        out_dir / "chart3_per_game_comparison.png",
        "Per-Game MinAtar Experiment 5 Comparison (Breakout, Seaquest, Asterix)",
        dpi=dpi,
    )


def generate_chart4(
    models_payload: dict[str, Any],
    ablation_payload: dict[str, Any],
    out_dir: Path,
    dpi: int = 300,
) -> Path:
    """Chart 4: Seaquest Prompt-Intervention Ablation Comparison (1x2 figure)."""
    by_id = {m["id"]: m for m in models_payload["models"]}
    astra_sea = by_id["gpt_6_astra_mit"]["scores"]["seaquest"]
    ppo500_sea = by_id["ppo_500m_mit"]["scores"]["seaquest"]
    ppo100_sea = by_id["ppo_100m_mit"]["scores"]["seaquest"]

    base = ablation_payload["baseline"]
    prmt = ablation_payload["prompted"]
    comp = ablation_payload["comparison"]
    sol_ref = ablation_payload["reference_gpt61_sol"]
    appended_sentence = ablation_payload["appended_sentence"]

    fig, (ax1, ax2) = plt.subplots(
        1,
        2,
        figsize=(16.0, 7.3),
        gridspec_kw={"width_ratios": [1.05, 1.15], "wspace": 0.24, "left": 0.065, "right": 0.975, "top": 0.77, "bottom": 0.19},
    )
    fig.patch.set_facecolor("white")

    # --- Panel A: Seaquest Episode Return ---
    bar_labels = [
        f"Gemini 4 Neon\nBaseline\n({base['nonzero_total']} nz, n=1)",
        f"Gemini 4 Neon\n1-Sent. Prompted\n({prmt['nonzero_total']:,} nz, n=1)",
        "GPT-6.1 Sol\nWSB Mean\n(high, n=3)",
        "GPT-6.1 Sol\nBest Single Run\n(1 of 3)",
    ]
    bar_means = [
        float(base["score_mean"]),
        float(prmt["score_mean"]),
        float(sol_ref["mean"]),
        float(sol_ref["best"]),
    ]
    bar_ses = [float(base["score_se"]), float(prmt["score_se"]), 0.0, 0.0]
    bar_colors = [COLOR_BASE_RUN, COLOR_PROMPTED, "#94A3B8", "#64748B"]
    bar_edges = [COLOR_BASE_RUN_EDGE, COLOR_PROMPTED_EDGE, "#475569", "#334155"]

    x1 = np.arange(4)
    for i in range(4):
        lw = 1.4 if i == 1 else 0.9
        ax1.bar(
            x1[i],
            bar_means[i],
            width=0.56,
            color=bar_colors[i],
            edgecolor=bar_edges[i],
            linewidth=lw,
            zorder=3,
        )
        if bar_ses[i] > 0:
            ax1.errorbar(
                x1[i],
                bar_means[i],
                yerr=bar_ses[i],
                fmt="none",
                ecolor="#1E293B",
                elinewidth=1.3,
                capsize=4.0,
                zorder=4,
            )
            lbl = f"{bar_means[i]:.2f} +/- {bar_ses[i]:.2f}"
            y_lbl = bar_means[i] + bar_ses[i] + 0.45
        else:
            lbl = f"{bar_means[i]:.2f}"
            y_lbl = bar_means[i] + 0.45

        ax1.text(
            x1[i],
            y_lbl,
            lbl,
            ha="center",
            va="bottom",
            fontsize=8.8,
            fontweight="bold" if i in (0, 1) else "normal",
            color=COLOR_PROMPTED_EDGE if i == 1 else TEXT_DARK,
            zorder=5,
        )

    ppo100_val = float(ppo100_sea["mean"])
    ax1.axhline(ppo100_val, color="#334155", linestyle="--", linewidth=1.4, zorder=2)
    ax1.text(
        4.12,
        ppo100_val + 0.35,
        f"PPO-100M\n= {ppo100_val:.2f}",
        ha="right",
        va="bottom",
        fontsize=8.2,
        fontweight="bold",
        color="#334155",
        bbox=dict(facecolor="white", edgecolor="#CBD5E1", boxstyle="round,pad=0.22", alpha=1.0),
        zorder=5,
    )

    # Significance bracket between Baseline and Prompted
    bracket_y = 20.6
    bracket_h = 0.65
    ax1.plot(
        [0, 0, 1, 1],
        [bracket_y, bracket_y + bracket_h, bracket_y + bracket_h, bracket_y],
        color=COLOR_PROMPTED_EDGE,
        linewidth=1.4,
        zorder=5,
    )
    stat_text = (
        f"+{comp['pct_gain']:.2f}% (+{comp['delta_score']:.2f})\n"
        f"z = {comp['z_stat']:.2f}, p = {comp['p_value_two_sided']:.2e}"
    )
    ax1.text(
        0.5,
        bracket_y + bracket_h + 0.35,
        stat_text,
        ha="center",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
        color=COLOR_PROMPTED_EDGE,
        bbox=dict(facecolor="#FFFBEB", edgecolor="#FCD34D", boxstyle="round,pad=0.28"),
        zorder=6,
    )

    # Off-scale upper reference callout box
    offscale_text = (
        "Upper Refs (off-scale):\n"
        f"GPT-6 Astra (MIT): {astra_sea['mean']:.2f} +/- {astra_sea['se']:.2f}\n"
        f"PPO-500M (best seed): {ppo500_sea['mean']:.2f} +/- {ppo500_sea['se']:.2f}"
    )
    ax1.text(
        0.97,
        0.96,
        offscale_text,
        transform=ax1.transAxes,
        ha="right",
        va="top",
        fontsize=8.2,
        color=TEXT_DARK,
        bbox=dict(facecolor="#F8FAFC", edgecolor="#CBD5E1", boxstyle="round,pad=0.4"),
        zorder=6,
    )

    ax1.set_xticks(x1)
    ax1.set_xticklabels(bar_labels, fontsize=8.5, color=TEXT_DARK)
    ax1.set_xlim(-0.55, 4.20)
    ax1.set_ylim(0, 28.5)
    ax1.set_yticks([0, 5, 10, 15, 20, 25])
    ax1.set_ylabel("Seaquest Mean Episode Return (+/-1 SE)", fontsize=10.0, fontweight="bold", color=TEXT_DARK)
    ax1.set_title("A. Seaquest Episode Return vs Reference", fontsize=11.0, fontweight="bold", color=TEXT_DARK, pad=10)
    ax1.yaxis.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.75, zorder=1)
    ax1.set_axisbelow(True)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # --- Panel B: Nonzero Weight Circuit Growth ---
    base_nz = base["nonzero_by_tensor"]
    prmt_nz = prmt["nonzero_by_tensor"]
    base_biases = int(base_nz["b1"]) + int(base_nz["b2"]) + int(base_nz["b3"])
    prmt_biases = int(prmt_nz["b1"]) + int(prmt_nz["b2"]) + int(prmt_nz["b3"])

    cats = ["Total\n(All Tensors)", "W1\n(600->32)", "W2\n(32->32)", "W3\n(32->6)", "Biases\n(b1+b2+b3)"]
    vals_base = [int(base["nonzero_total"]), int(base_nz["W1"]), int(base_nz["W2"]), int(base_nz["W3"]), base_biases]
    vals_prmt = [int(prmt["nonzero_total"]), int(prmt_nz["W1"]), int(prmt_nz["W2"]), int(prmt_nz["W3"]), prmt_biases]

    x2 = np.arange(len(cats))
    width = 0.36
    ax2.bar(
        x2 - width / 2,
        vals_base,
        width=width,
        color=COLOR_BASE_RUN,
        edgecolor=COLOR_BASE_RUN_EDGE,
        linewidth=0.9,
        label=f"Baseline ({base['nonzero_total']} nz)",
        zorder=3,
    )
    ax2.bar(
        x2 + width / 2,
        vals_prmt,
        width=width,
        color=COLOR_PROMPTED,
        edgecolor=COLOR_PROMPTED_EDGE,
        linewidth=1.1,
        label=f"1-Sentence Prompted ({prmt['nonzero_total']:,} nz)",
        zorder=3,
    )

    for i in range(len(cats)):
        ax2.text(
            x2[i] - width / 2,
            vals_base[i] + 22,
            f"{vals_base[i]:,}",
            ha="center",
            va="bottom",
            fontsize=8.3,
            color=COLOR_BASE_RUN_EDGE,
            fontweight="bold" if i < 2 else "normal",
            zorder=5,
        )
        ax2.text(
            x2[i] + width / 2,
            vals_prmt[i] + 22,
            f"{vals_prmt[i]:,}",
            ha="center",
            va="bottom",
            fontsize=8.3,
            color=COLOR_PROMPTED_EDGE,
            fontweight="bold",
            zorder=5,
        )

    # Verification callout in open upper-right space above W2/W3/Biases
    verify_box = (
        "From-Scratch Verification (0 Weight Reuse)\n"
        f"- Identical nonzero coords: {comp['identical_nonzero_coords']} / {comp['overlapping_nonzero_coords']} overlap\n"
        f"- Union: {comp['union_nonzero_coords']:,}  |  Jaccard: {comp['jaccard']:.4f}\n"
        f"- Cosine similarity: {comp['cosine_similarity']:.4f}\n"
        f"- Parsed edits: {base['statements_parsed']}/{base['statements_total']} -> {prmt['statements_parsed']}/{prmt['statements_total']}\n"
        f"- Overall WWI: {base['wwi_overall']:.2f} -> {prmt['wwi_overall']:.2f}"
    )
    ax2.text(
        0.41,
        0.81,
        verify_box,
        transform=ax2.transAxes,
        ha="left",
        va="top",
        fontsize=8.2,
        color=TEXT_DARK,
        linespacing=1.45,
        bbox=dict(facecolor="#F8FAFC", edgecolor="#CBD5E1", boxstyle="round,pad=0.45"),
        zorder=6,
    )

    ax2.legend(
        loc="upper right",
        frameon=True,
        facecolor="white",
        edgecolor="#CBD5E1",
        fontsize=8.6,
    )
    ax2.set_xticks(x2)
    ax2.set_xticklabels(cats, fontsize=8.8, color=TEXT_DARK)
    ax2.set_ylim(0, 1420)
    ax2.set_yticks([0, 200, 400, 600, 800, 1000, 1200, 1400])
    ax2.set_ylabel("Nonzero Parameters (Count)", fontsize=10.0, fontweight="bold", color=TEXT_DARK)
    ax2.set_title("B. Nonzero Weight Circuit Growth & Divergence", fontsize=11.0, fontweight="bold", color=TEXT_DARK, pad=10)
    ax2.yaxis.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.75, zorder=1)
    ax2.set_axisbelow(True)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.text(
        0.52,
        0.96,
        "Seaquest Prompt-Intervention Ablation: Gemini 4 Neon (XHigh) Baseline vs 1-Sentence Prompted",
        ha="center",
        va="top",
        fontsize=14.2,
        fontweight="bold",
        color=TEXT_DARK,
    )
    fig.text(
        0.52,
        0.905,
        (
            f'Appended sentence: "{appended_sentence}"\n'
            f"Separated from verbatim-prompt main rankings | Local runs: xhigh, Antigravity (default ctx), tool_calls={base['tool_calls']}, {comp['episodes']:,} eval episodes"
        ),
        ha="center",
        va="top",
        fontsize=8.9,
        color=TEXT_MUTED,
        linespacing=1.35,
    )

    footer = (
        f"Caveat (n=1 generated network sample): Two-sample z-test (z={comp['z_stat']:.2f}, p={comp['p_value_two_sided']:.2e}) "
        f"tests {comp['episodes']:,} MinAtar evaluation episodes per network; n >= 3 independent network generations are required for network-level reproducibility."
    )
    fig.text(0.52, 0.025, footer, ha="center", va="bottom", fontsize=8.2, color=TEXT_FOOTER)

    return _save_figure(
        fig,
        out_dir / "chart4_seaquest_ablation.png",
        "Seaquest Prompt-Intervention Ablation: Gemini 4 Neon (XHigh)",
        dpi=dpi,
    )


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Generate four publication-grade Weight-Space Programming charts.")
    parser.add_argument(
        "--models-json",
        type=Path,
        default=repo_root / "data" / "leaderboard_models.json",
        help="Path to leaderboard_models.json",
    )
    parser.add_argument(
        "--ablation-json",
        type=Path,
        default=repo_root / "data" / "seaquest_ablation.json",
        help="Path to seaquest_ablation.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=repo_root / "charts",
        help="Output directory for PNG charts",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Output PNG DPI (default: 300)")
    args = parser.parse_args(argv)

    configure_matplotlib(dpi=args.dpi)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    models_payload = json.loads(args.models_json.read_text(encoding="utf-8"))
    ablation_payload = json.loads(args.ablation_json.read_text(encoding="utf-8"))

    outputs = [
        generate_chart1(models_payload, args.out_dir, dpi=args.dpi),
        generate_chart2(models_payload, args.out_dir, dpi=args.dpi),
        generate_chart3(models_payload, args.out_dir, dpi=args.dpi),
        generate_chart4(models_payload, ablation_payload, args.out_dir, dpi=args.dpi),
    ]
    for path in outputs:
        print(f"Generated {path.name} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
