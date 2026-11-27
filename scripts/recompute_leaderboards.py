# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Xuyao Zhang (comprehensive-weight-space-programming-leaderboard contributors)
"""Recompute dual-formula Weight-Space Programming MinAtar Experiment 5 leaderboards.

Reads data/leaderboard_models.json, verifies all model entries against
scripts/wsp_eval.py (WWI & WSB median formulas), regenerates
data/leaderboard_wwi.csv (strictly main WWI rows) and
data/leaderboard_wsb_median.csv (strictly main WSB median rows), and prints
the main leaderboards plus the Random Baseline Sensitivity Table.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wsp_eval import (  # noqa: E402
    GAMES,
    PPO100,
    PPO500_BASELINES,
    RANDOM_PAPER_BASELINES,
    RANDOM_WIN_SEED0,
    RANDOM_WSB_IMPLIED,
    RANDOM_ZERO,
    compute_wsb_median,
    compute_wwi,
    wsb_game_norm,
    wwi_game_score,
)

NA_PER_GAME = "N/A (per-game scores not publicly disclosed)"

WWI_COLUMNS = [
    "rank",
    "id",
    "model_name",
    "source",
    "tier",
    "include_in_main_wwi",
    "per_game_scores_disclosed",
    "wwi_score",
    "wwi_score_type",
    "reported_wwi",
    "computed_wwi",
    "breakout_raw",
    "seaquest_raw",
    "asterix_raw",
    "breakout_wwi",
    "seaquest_wwi",
    "asterix_wwi",
    "thinking_effort",
    "platform_api",
    "attempts",
    "protocol_flag",
    "notes",
]

WSB_COLUMNS = [
    "rank",
    "id",
    "model_name",
    "source",
    "tier",
    "include_in_main_wsb",
    "per_game_scores_disclosed",
    "wsb_median",
    "wsb_published_median",
    "breakout_raw",
    "seaquest_raw",
    "asterix_raw",
    "breakout_pct_ppo500",
    "seaquest_pct_ppo500",
    "asterix_pct_ppo500",
    "thinking_effort",
    "platform_api",
    "attempts",
    "protocol_flag",
    "notes",
]


def _fmt_opt(val: float | int | None, decimals: int = 4) -> str:
    if val is None:
        return ""
    if isinstance(val, int):
        return str(val)
    return f"{float(val):.{decimals}f}"


def main() -> int:
    repo_root = SCRIPT_DIR.parent
    models_path = repo_root / "data" / "leaderboard_models.json"
    wwi_csv_path = repo_root / "data" / "leaderboard_wwi.csv"
    wsb_csv_path = repo_root / "data" / "leaderboard_wsb_median.csv"

    payload = json.loads(models_path.read_text(encoding="utf-8"))
    models: list[dict] = payload["models"]

    # Verify stored computed_wwi and computed_wsb_median for every disclosed per-game record.
    for rec in models:
        if rec["per_game_scores_disclosed"]:
            scores = rec["scores"]
            if scores is None:
                raise ValueError(f"{rec['id']}: per_game_scores_disclosed is true but scores is null")
            recomp_wwi = compute_wwi(scores, RANDOM_PAPER_BASELINES, PPO500_BASELINES)
            recomp_wsb = compute_wsb_median(scores, RANDOM_PAPER_BASELINES, PPO500_BASELINES)
            stored_wwi = rec["computed_wwi"]
            stored_wsb = rec["computed_wsb_median"]
            if stored_wwi is None or abs(recomp_wwi - stored_wwi) >= 1e-3:
                raise AssertionError(
                    f"{rec['id']}: WWI mismatch (recomputed={recomp_wwi:.6f}, stored={stored_wwi})"
                )
            if stored_wsb is None or abs(recomp_wsb - stored_wsb) >= 1e-3:
                raise AssertionError(
                    f"{rec['id']}: WSB mismatch (recomputed={recomp_wsb:.6f}, stored={stored_wsb})"
                )
            rec["_recomp_wwi"] = recomp_wwi
            rec["_recomp_wsb"] = recomp_wsb
            rec["_wwi_per_game"] = {
                g: wwi_game_score(scores[g]["mean"], RANDOM_PAPER_BASELINES[g], PPO500_BASELINES[g])
                for g in GAMES
            }
            rec["_wsb_per_game"] = {
                g: 100.0 * wsb_game_norm(scores[g]["mean"], RANDOM_PAPER_BASELINES[g], PPO500_BASELINES[g])
                for g in GAMES
            }
        else:
            rec["_recomp_wwi"] = None
            rec["_recomp_wsb"] = None

    # Build and sort main WWI table (strictly include_in_main_wwi == True).
    def wwi_sort_key(rec: dict) -> tuple:
        wwi_val = rec["_recomp_wwi"] if rec["_recomp_wwi"] is not None else float(rec["reported_wwi"])
        wsb_tie = rec["_recomp_wsb"] if rec["_recomp_wsb"] is not None else -1e9
        return (
            -round(wwi_val, 4),
            -wsb_tie,
            rec["model_name"],
        )

    wwi_models = [rec for rec in models if rec["include_in_main_wwi"]]
    wwi_sorted = sorted(wwi_models, key=wwi_sort_key)
    wwi_rows: list[dict[str, str]] = []
    main_wwi_rank = 0
    for rec in wwi_sorted:
        if rec["tier"] == "baseline":
            rank_str = "Baseline"
        else:
            main_wwi_rank += 1
            rank_str = str(main_wwi_rank)

        disclosed = bool(rec["per_game_scores_disclosed"])
        if disclosed and rec["_recomp_wwi"] is not None:
            wwi_score_str = f"{rec['_recomp_wwi']:.4f}"
            wwi_type = "computed_wwi"
            comp_wwi_str = f"{rec['_recomp_wwi']:.4f}"
            raw_vals = {g: f"{rec['scores'][g]['mean']:.4f}" for g in GAMES}
            wwi_vals = {g: f"{rec['_wwi_per_game'][g]:.4f}" for g in GAMES}
        else:
            wwi_score_str = f"{float(rec['reported_wwi']):.4f}"
            wwi_type = "reported WWI"
            comp_wwi_str = ""
            raw_vals = {g: NA_PER_GAME for g in GAMES}
            wwi_vals = {g: NA_PER_GAME for g in GAMES}

        wwi_rows.append(
            {
                "rank": rank_str,
                "id": rec["id"],
                "model_name": rec["model_name"],
                "source": rec["source"],
                "tier": rec["tier"],
                "include_in_main_wwi": str(bool(rec["include_in_main_wwi"])),
                "per_game_scores_disclosed": str(disclosed),
                "wwi_score": wwi_score_str,
                "wwi_score_type": wwi_type,
                "reported_wwi": _fmt_opt(rec["reported_wwi"], 1) if rec["reported_wwi"] is not None else "",
                "computed_wwi": comp_wwi_str,
                "breakout_raw": raw_vals["breakout"],
                "seaquest_raw": raw_vals["seaquest"],
                "asterix_raw": raw_vals["asterix"],
                "breakout_wwi": wwi_vals["breakout"],
                "seaquest_wwi": wwi_vals["seaquest"],
                "asterix_wwi": wwi_vals["asterix"],
                "thinking_effort": rec["thinking_effort"],
                "platform_api": rec["platform_api"],
                "attempts": str(rec["attempts"]),
                "protocol_flag": rec.get("protocol_flag", rec["tier"]),
                "notes": rec["notes"],
            }
        )

    with wwi_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=WWI_COLUMNS)
        writer.writeheader()
        writer.writerows(wwi_rows)

    # Build and sort main WSB median table (strictly include_in_main_wsb == True).
    def wsb_sort_key(rec: dict) -> tuple:
        return (-round(rec["_recomp_wsb"], 4), rec["model_name"])

    wsb_models = [rec for rec in models if rec["include_in_main_wsb"]]
    wsb_sorted = sorted(wsb_models, key=wsb_sort_key)
    wsb_rows: list[dict[str, str]] = []
    main_wsb_rank = 0
    for rec in wsb_sorted:
        if rec["tier"] == "baseline":
            rank_str = "Baseline"
        else:
            main_wsb_rank += 1
            rank_str = str(main_wsb_rank)

        disclosed = bool(rec["per_game_scores_disclosed"])
        if disclosed and rec["_recomp_wsb"] is not None:
            wsb_str = f"{rec['_recomp_wsb']:.4f}"
            raw_vals = {g: f"{rec['scores'][g]['mean']:.4f}" for g in GAMES}
            pct_vals = {g: f"{rec['_wsb_per_game'][g]:.4f}" for g in GAMES}
        else:
            wsb_str = NA_PER_GAME
            raw_vals = {g: NA_PER_GAME for g in GAMES}
            pct_vals = {g: NA_PER_GAME for g in GAMES}

        wsb_rows.append(
            {
                "rank": rank_str,
                "id": rec["id"],
                "model_name": rec["model_name"],
                "source": rec["source"],
                "tier": rec["tier"],
                "include_in_main_wsb": str(bool(rec["include_in_main_wsb"])),
                "per_game_scores_disclosed": str(disclosed),
                "wsb_median": wsb_str,
                "wsb_published_median": (
                    f"{rec['wsb_published_median']:.2f}" if rec["wsb_published_median"] is not None else ""
                ),
                "breakout_raw": raw_vals["breakout"],
                "seaquest_raw": raw_vals["seaquest"],
                "asterix_raw": raw_vals["asterix"],
                "breakout_pct_ppo500": pct_vals["breakout"],
                "seaquest_pct_ppo500": pct_vals["seaquest"],
                "asterix_pct_ppo500": pct_vals["asterix"],
                "thinking_effort": rec["thinking_effort"],
                "platform_api": rec["platform_api"],
                "attempts": str(rec["attempts"]),
                "protocol_flag": rec.get("protocol_flag", rec["tier"]),
                "notes": rec["notes"],
            }
        )

    with wsb_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=WSB_COLUMNS)
        writer.writeheader()
        writer.writerows(wsb_rows)

    # Print summary tables.
    print("=== Main Writing Weights Index (WWI) Leaderboard ===")
    print(f"{'Rank':<9} {'Model':<32} {'Source':<22} {'WWI':>8} {'Type':<14} {'Effort':<24}")
    for row in wwi_rows:
        if row["include_in_main_wwi"] == "True":
            print(
                f"{row['rank']:<9} {row['model_name']:<32} {row['source']:<22} "
                f"{row['wwi_score']:>8} {row['wwi_score_type']:<14} {row['thinking_effort']:<24}"
            )

    print("\n=== Main weight-space-bench (WSB) Median Leaderboard ===")
    print(f"{'Rank':<9} {'Model':<32} {'Source':<22} {'WSB Med':>9} {'Pub':>7} {'B / S / A':<28}")
    for row in wsb_rows:
        if row["include_in_main_wsb"] == "True":
            bsa = f"{float(row['breakout_raw']):.1f} / {float(row['seaquest_raw']):.1f} / {float(row['asterix_raw']):.1f}"
            print(
                f"{row['rank']:<9} {row['model_name']:<32} {row['source']:<22} "
                f"{row['wsb_median']:>9} {row['wsb_published_median']:>7} {bsa:<28}"
            )

    # Random Baseline Sensitivity Table.
    by_id = {rec["id"]: rec for rec in models}
    astra_scores = by_id["gpt_6_astra_mit"]["scores"]
    astra_paper = compute_wwi(astra_scores, RANDOM_PAPER_BASELINES, PPO500_BASELINES)
    astra_zero = compute_wwi(astra_scores, RANDOM_ZERO, PPO500_BASELINES)
    astra_win = compute_wwi(astra_scores, RANDOM_WIN_SEED0, PPO500_BASELINES)
    ppo100_paper = compute_wwi(PPO100, RANDOM_PAPER_BASELINES, PPO500_BASELINES)
    ppo100_zero = compute_wwi(PPO100, RANDOM_ZERO, PPO500_BASELINES)

    print("\n=== Random Baseline Sensitivity Table ===")
    print(
        f"GPT-6 Astra (MIT) WWI | random_paper (0.55/0.09/0.49): {astra_paper:.4f} | "
        f"random_zero (0/0/0): {astra_zero:.4f} | "
        f"random_win_local_seed0 (0.539/0.086/0.487): {astra_win:.4f} | "
        f"Xingyu Dang chart: 60.7"
    )
    print(
        f"PPO-100M (MIT) WWI    | random_paper: {ppo100_paper:.4f} ({ppo100_paper:.1f}) | "
        f"random_zero: {ppo100_zero:.4f} ({ppo100_zero:.1f})"
    )

    wsb_ids = [
        "gpt_6_1_sol_wsb",
        "claude_opus_5_5_wsb",
        "claude_sonnet_5_5_wsb",
        "kimi_k3_1_pro_wsb",
        "muse_wonder_wsb",
        "deepseek_v4_1_flash_wsb",
    ]
    print("\nWSB 6 Models: random_wsb_implied (0.545/0.093/0.492) vs random_paper (0.55/0.09/0.49) vs CSV:")
    for mid in wsb_ids:
        rec = by_id[mid]
        m_implied = compute_wsb_median(rec["scores"], RANDOM_WSB_IMPLIED, PPO500_BASELINES)
        m_paper = compute_wsb_median(rec["scores"], RANDOM_PAPER_BASELINES, PPO500_BASELINES)
        pub = rec["wsb_published_median"]
        assert round(m_implied, 2) == pub, f"{mid}: {m_implied:.4f} != {pub}"
        print(
            f"  {rec['model_name']:<22} | implied={m_implied:6.2f} | "
            f"paper={m_paper:6.2f} | csv={pub:6.2f}"
        )

    print(
        f"\nRegenerated {wwi_csv_path.relative_to(repo_root).as_posix()} ({len(wwi_rows)} main rows) and "
        f"{wsb_csv_path.relative_to(repo_root).as_posix()} ({len(wsb_rows)} main rows) from "
        f"{len(models)} verified JSON records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
