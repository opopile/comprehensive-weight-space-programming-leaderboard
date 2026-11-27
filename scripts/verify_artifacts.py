# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Xuyao Zhang (comprehensive-weight-space-programming-leaderboard contributors)
"""Verify local Gemini 4 Neon (XHigh) scrubbed artifacts and MinAtar 1.0.15 reproducibility.

Checks:
1. All 17 expected files exist under artifacts/gemini-4-neon-xhigh/
2. apply_edits(reply.md) reproduces edits.json (0 errors, cut_off=False) and network.npz (0.0 diff)
3. Exact nonzero parameter counts: 1571 (Breakout), 920 (Asterix), 550 (Seaquest base), 1172 (prompted)
4. summary.json parity against the 3 baseline score.json files & median_score=109.16218883649522
5. Seaquest baseline vs prompted non-reuse metrics (154 overlap, 1568 union, 0 identical, cos=-0.20591)
6. Two-sample episode-level z-test (z=4.442621, p=8.886967e-6) and data/seaquest_ablation.json parity
7. Unless --skip-sim is passed, runs full 1,000-episode MinAtar==1.0.15 evaluation on all 4 networks
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wsp_eval import (  # noqa: E402
    PPO500,
    RANDOM_PAPER,
    SHAPES,
    apply_edits,
    compare_networks,
    load_npz,
    score_network,
    two_sample_z_test,
    wsb_game_norm,
    wsb_median_score,
    wwi_game_score,
    wwi_overall,
)

RUNS = [
    ("breakout", "breakout/attempt_1", 1571),
    ("asterix", "asterix/attempt_1", 920),
    ("seaquest", "seaquest/attempt_1", 550),
    ("seaquest", "seaquest/attempt_2_prompted", 1172),
    ("breakout", "breakout/attempt_zh_prompt", 2009),
    ("asterix", "asterix/attempt_zh_prompt", 976),
    ("seaquest", "seaquest/attempt_zh_prompt", 1207),
]


def main(argv: list[str] | None = None) -> int:
    repo_root = SCRIPT_DIR.parent
    parser = argparse.ArgumentParser(
        description="Verify scrubbed Gemini 4 Neon (XHigh) artifacts and MinAtar 1.0.15 scores."
    )
    parser.add_argument(
        "--skip-sim",
        action="store_true",
        help="Skip the 1,000-episode MinAtar simulation and verify edits/NPZ/ablation checks only.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help=(
            "Worker process count for MinAtar simulation (0 = auto cpu_count-1; "
            "note: MinAtar 1.0.15 Environment.last_action carries across chunk episodes, "
            "so --workers 15 reproduces score.json to 1e-6 on any host CPU count)."
        ),
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=repo_root / "artifacts" / "gemini-4-neon-xhigh",
        help="Path to the scrubbed artifact directory.",
    )
    parser.add_argument(
        "--ablation-json",
        type=Path,
        default=repo_root / "data" / "seaquest_ablation.json",
        help="Path to data/seaquest_ablation.json for cross-checking.",
    )
    args = parser.parse_args(argv)

    artifacts_dir: Path = args.artifacts_dir.resolve()
    summary_path = artifacts_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Missing summary.json: {summary_path}")

    expected_files = [summary_path]
    for _, rel_dir, _ in RUNS:
        for fname in ("edits.json", "network.npz", "reply.md", "score.json"):
            p = artifacts_dir / rel_dir / fname
            if not p.is_file():
                raise FileNotFoundError(f"Missing artifact file: {p}")
            expected_files.append(p)
    print(f"[OK] Verified all {len(expected_files)} artifact files exist under {artifacts_dir.name}/.")

    loaded_nets: dict[str, dict[str, np.ndarray]] = {}
    stored_scores: dict[str, dict] = {}
    edits_reports: dict[str, dict] = {}

    for game, rel_dir, expected_nz in RUNS:
        run_dir = artifacts_dir / rel_dir
        reply_text = (run_dir / "reply.md").read_text(encoding="utf-8")
        edits_json = json.loads((run_dir / "edits.json").read_text(encoding="utf-8"))
        score_json = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
        npz_net = load_npz(run_dir / "network.npz")

        parsed_net, rep = apply_edits(reply_text)
        assert rep == edits_json, f"{rel_dir}: apply_edits report != edits.json"
        assert rep["errors"] == [], f"{rel_dir}: unexpected parse errors: {rep['errors']}"
        assert rep["cut_off"] is False, f"{rel_dir}: unexpected cut_off=True"
        assert rep["nonzero_total"] == expected_nz, (
            f"{rel_dir}: nonzero_total {rep['nonzero_total']} != {expected_nz}"
        )

        max_diff = max(
            float(np.max(np.abs(parsed_net[k] - npz_net[k])))
            for k in SHAPES
        )
        assert max_diff == 0.0, f"{rel_dir}: max_diff {max_diff} != 0.0"

        loaded_nets[rel_dir] = npz_net
        stored_scores[rel_dir] = score_json
        edits_reports[rel_dir] = rep
        print(
            f"[OK] {rel_dir:<27} | stmts={rep['applied']}/{rep['statements']} "
            f"| nz={rep['nonzero_total']:>4} | max_diff={max_diff:.1f} "
            f"| stored_mean={score_json['mean']:.3f}"
        )

    # Verify summary.json against the 3 baseline score.json files.
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for game, rel_dir in (
        ("breakout", "breakout/attempt_1"),
        ("seaquest", "seaquest/attempt_1"),
        ("asterix", "asterix/attempt_1"),
    ):
        assert summary["results"][game] == stored_scores[rel_dir], f"summary mismatch for {game}"
        expected_norm = 100.0 * wsb_game_norm(
            stored_scores[rel_dir]["mean"], RANDOM_PAPER[game], PPO500[game]
        )
        assert abs(summary["normalized_pct_ppo500"][game] - expected_norm) < 1e-9, (
            f"summary normalized_pct_ppo500 mismatch for {game}"
        )
    baseline_scores = {
        "breakout": stored_scores["breakout/attempt_1"]["mean"],
        "seaquest": stored_scores["seaquest/attempt_1"]["mean"],
        "asterix": stored_scores["asterix/attempt_1"]["mean"],
    }
    comp_wsb = wsb_median_score(baseline_scores, RANDOM_PAPER, PPO500)
    assert abs(summary["median_score"] - 109.16218883649522) < 1e-9
    assert abs(summary["median_score"] - comp_wsb) < 1e-9
    print(f"[OK] summary.json matches baseline score.json files (WSB median={comp_wsb:.6f}).")

    # Verify Seaquest non-reuse comparison and two-sample z-test.
    comp = compare_networks(
        loaded_nets["seaquest/attempt_1"],
        loaded_nets["seaquest/attempt_2_prompted"],
    )
    assert comp["nonzero_a"] == 550
    assert comp["nonzero_b"] == 1172
    assert comp["overlapping_nonzero_coords"] == 154
    assert comp["union_nonzero_coords"] == 1568
    assert comp["identical_nonzero_coords"] == 0
    assert abs(comp["cosine_similarity"] - (-0.20590984821258145)) < 1e-6

    s_base = stored_scores["seaquest/attempt_1"]
    s_prom = stored_scores["seaquest/attempt_2_prompted"]
    ztest = two_sample_z_test(s_base["mean"], s_base["se"], s_prom["mean"], s_prom["se"])
    assert abs(ztest["z_stat"] - 4.442620901776113) < 1e-6
    assert abs(ztest["p_value_two_sided"] - 8.886966678758107e-6) < 1e-12
    print(
        f"[OK] Seaquest comparison: overlap={comp['overlapping_nonzero_coords']}, "
        f"union={comp['union_nonzero_coords']}, identical={comp['identical_nonzero_coords']}, "
        f"cos={comp['cosine_similarity']:.5f} | z={ztest['z_stat']:.4f}, p={ztest['p_value_two_sided']:.4e}"
    )

    # Cross-check data/seaquest_ablation.json if present.
    ablation_path: Path = args.ablation_json.resolve()
    if ablation_path.is_file():
        ab = json.loads(ablation_path.read_text(encoding="utf-8"))
        expected_sentence = (
            "There are no limits on your tokens or time. Perform this task at your "
            "absolute peak capability and push every detail to perfection."
        )
        assert ab["appended_sentence"] == expected_sentence, "appended_sentence mismatch"

        prompted_scores = {
            "breakout": stored_scores["breakout/attempt_1"]["mean"],
            "seaquest": stored_scores["seaquest/attempt_2_prompted"]["mean"],
            "asterix": stored_scores["asterix/attempt_1"]["mean"],
        }
        assert abs(ab["baseline"]["score_mean"] - s_base["mean"]) < 1e-6
        assert abs(ab["baseline"]["score_se"] - s_base["se"]) < 1e-6
        assert abs(ab["baseline"]["max_score"] - s_base["max"]) < 1e-6
        assert abs(ab["baseline"]["mean_length"] - s_base["mean_length"]) < 1e-6
        assert ab["baseline"]["nonzero_total"] == 550
        assert ab["baseline"]["nonzero_by_tensor"] == edits_reports["seaquest/attempt_1"]["nonzero"]
        assert ab["baseline"]["statements_parsed"] == edits_reports["seaquest/attempt_1"]["applied"]
        assert ab["baseline"]["statements_total"] == edits_reports["seaquest/attempt_1"]["statements"]
        assert abs(ab["baseline"]["wwi_overall"] - wwi_overall(baseline_scores)) < 1e-6
        assert abs(ab["baseline"]["wwi_seaquest"] - wwi_game_score(s_base["mean"], RANDOM_PAPER["seaquest"], PPO500["seaquest"])) < 1e-6
        assert abs(ab["baseline"]["wsb_median_overall"] - comp_wsb) < 1e-6

        assert abs(ab["prompted"]["score_mean"] - s_prom["mean"]) < 1e-6
        assert abs(ab["prompted"]["score_se"] - s_prom["se"]) < 1e-6
        assert abs(ab["prompted"]["max_score"] - s_prom["max"]) < 1e-6
        assert abs(ab["prompted"]["mean_length"] - s_prom["mean_length"]) < 1e-6
        assert ab["prompted"]["nonzero_total"] == 1172
        assert ab["prompted"]["nonzero_by_tensor"] == edits_reports["seaquest/attempt_2_prompted"]["nonzero"]
        assert ab["prompted"]["statements_parsed"] == edits_reports["seaquest/attempt_2_prompted"]["applied"]
        assert ab["prompted"]["statements_total"] == edits_reports["seaquest/attempt_2_prompted"]["statements"]
        assert abs(ab["prompted"]["wwi_overall"] - wwi_overall(prompted_scores)) < 1e-6
        assert abs(ab["prompted"]["wwi_seaquest"] - wwi_game_score(s_prom["mean"], RANDOM_PAPER["seaquest"], PPO500["seaquest"])) < 1e-6
        assert abs(ab["prompted"]["wsb_median_overall"] - wsb_median_score(prompted_scores, RANDOM_PAPER, PPO500)) < 1e-6

        assert abs(ab["comparison"]["delta_score"] - ztest["delta_score"]) < 1e-6
        assert abs(ab["comparison"]["pct_gain"] - ztest["pct_gain"]) < 1e-6
        assert ab["comparison"]["overlapping_nonzero_coords"] == comp["overlapping_nonzero_coords"]
        assert ab["comparison"]["union_nonzero_coords"] == comp["union_nonzero_coords"]
        assert abs(ab["comparison"]["jaccard"] - comp["jaccard"]) < 1e-9
        assert ab["comparison"]["identical_nonzero_coords"] == comp["identical_nonzero_coords"]
        assert abs(ab["comparison"]["cosine_similarity"] - comp["cosine_similarity"]) < 1e-6
        assert abs(ab["comparison"]["z_stat"] - ztest["z_stat"]) < 1e-6
        assert abs(ab["comparison"]["p_value_two_sided"] - ztest["p_value_two_sided"]) < 1e-12

        assert abs(ab["reference_gpt61_sol"]["mean"] - 11.824) < 1e-6
        assert abs(ab["reference_gpt61_sol"]["best"] - 18.022) < 1e-6
        models_json_path = repo_root / "data" / "leaderboard_models.json"
        if models_json_path.is_file():
            models_data = json.loads(models_json_path.read_text(encoding="utf-8"))
            sol_rec = next(
                (m for m in models_data.get("models", []) if m.get("id") == "gpt_6_1_sol_wsb"),
                None,
            )
            if sol_rec is not None:
                sol_sea = sol_rec["scores"]["seaquest"]
                assert abs(ab["reference_gpt61_sol"]["mean"] - sol_sea["mean"]) < 1e-6
                assert abs(ab["reference_gpt61_sol"]["best"] - sol_sea["best"]) < 1e-6

        print(f"[OK] Cross-checked {ablation_path.name} against live recomputed values.")

    if args.skip_sim:
        print("[SKIP] --skip-sim set; MinAtar simulation skipped.")
        return 0

    actual_workers = args.workers or max(1, (os.cpu_count() or 2) - 1)
    tol = 1e-6 if actual_workers == 15 else 0.5
    print(f"\nRunning full 1,000-episode MinAtar==1.0.15 evaluation (workers={actual_workers}, tol={tol:g})...")
    for game, rel_dir, _ in RUNS:
        res = score_network(
            loaded_nets[rel_dir],
            game,
            episodes=1000,
            seed=0,
            max_steps=10000,
            workers=args.workers,
        )
        expected_mean = stored_scores[rel_dir]["mean"]
        diff = abs(res["mean"] - expected_mean)
        assert diff <= tol, (
            f"{rel_dir}: simulated mean {res['mean']:.6f} vs stored {expected_mean:.6f} "
            f"(diff={diff:.6f} > tol={tol})"
        )
        print(
            f"[SIM OK] {rel_dir:<27} | sim_mean={res['mean']:.3f} ± {res['se']:.3f} "
            f"| stored={expected_mean:.3f} | diff={diff:.2e} | max={res['max']:.1f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
