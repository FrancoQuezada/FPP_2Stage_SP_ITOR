#!/usr/bin/env python3
"""Reproduce the held-out objective and placement-stability table.

The intact worker records come from two committed Results_server
campaigns. Their first five replicates use the same sampled training
splits and common test IDs as the 810-run comparison. This is a separate
decision study: solver outcomes need not equal the original panel.
Read worker CSVs rather than the later consolidated n=400 CSV, whose
task identifiers point to unrelated worker records.
"""

import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


POLICY = {
    "Expected": "FPP-Branch-Benders-ProjectedPathLLBI-exp-RootCuts",
    "CVaR": "FPP-Branch-Benders-CVaR-ProjectedPathLLBI-exp-RootCuts",
    "MeanCVaR": "FPP-Branch-Benders-MeanCVaR-ProjectedPathLLBI-exp-RootCuts",
}
CAMPAIGNS = {
    100: "fpp_new_instances_scaling",
    200: "fpp_new_instances_scaling",
    400: "fpp_new_instances_scaling_new20x20",
}
OBJECTIVES = {"Expected": "Expected", "CVaR": "CVaR", "MeanCVaR": "Mean--CVaR"}


def records(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def checked_equal(a, b):
    assert abs(float(a) - float(b)) < 0.0000001, (a, b)


def reproduce(implementation: Path, manuscript: Path):
    base = implementation / "cpp_cplex_firebreak"
    original = base / "results/batch/fpp_new20x20_scaling"
    manifest = records(original / "manifests/full_task_manifest.csv")
    original_tasks = {
        (r["case_id"], r["alpha"], int(r["train_count"]),
         r["objective_family"], r["method"]): r
        for r in manifest if r["instance_id"] == "new20x20"
    }
    groups = defaultdict(list)
    checked_splits = set()
    for n, campaign in CAMPAIGNS.items():
        source = base / "Results_server/batch" / campaign
        for worker_csv in sorted(source.glob("workers/*/batch_results_worker_*.csv")):
          for row in records(worker_csv):
            objective = row["objective_family"]
            if (int(row["train_count"]) != n or row["method"] != POLICY[objective]
                    or row["case_id"] not in {f"case{k:02}" for k in range(5)}):
                continue
            key = (row["case_id"], row["alpha"], n, objective, row["method"])
            assert key in original_tasks, key
            target = original_tasks[key]
            for field in ("seed_base", "split_seed", "budget", "test_count",
                          "cvar_beta", "cvar_lambda", "time_limit"):
                if field in target and field in row:
                    assert target[field] == row[field], (key, field)
            assert row["instance_id"] == "new20x20"
            assert row["test_pool_min"] == "9001" and row["test_pool_max"] == "10000"
            assert row["test_scenario_count"] == "1000"
            for field in ("train_split_path", "test_split_path"):
                p = (base / target[field], source / "splits" / Path(row[field]).name)
                if p not in checked_splits:
                    assert p[0].read_bytes() == p[1].read_bytes(), (key, field)
                    checked_splits.add(p)
            folder = worker_csv.parent
            assert folder.name == row["worker_id"]
            task = row["task_id"]
            worker = json.loads((folder / "json" / (task + ".json")).read_text())
            placement = json.loads((folder / "solutions" / (task + ".json")).read_text())
            csv_ids = (folder / "solutions" / (task + ".csv")).read_text().strip()
            cells = placement["selected_firebreak_original_nodes"]
            assert csv_ids == ",".join(map(str, cells)), key
            assert cells == worker["selected_firebreaks"], key
            assert len(cells) == len(set(cells)) and all(1 <= c <= 400 for c in cells), key
            assert len(cells) <= int(row["budget"]) == int(placement["budget"]) == int(worker["budget"]), key
            assert worker["method"] == row["method"]
            assert worker["test_ids"] == list(range(9001, 10001))
            assert worker["train_ids"] == [int(x) for x in (source / "splits" / Path(row["train_split_path"]).name).read_text().replace("\n", ",").split(",") if x.strip()]
            checked_equal(worker["test_expected_burned_area"], row["test_expected_burned_area"])
            checked_equal(worker["test_empirical_cvar_burned_area"], row["test_worst_10pct_burned_area"])
            checked_equal(worker["cvar_beta"], .9)
            checked_equal(worker["cvar_lambda"], .5 if objective == "MeanCVaR" else 1.)
            mu = float(worker["test_expected_burned_area"])
            cvar = float(worker["test_empirical_cvar_burned_area"])
            value = {"Expected": mu, "CVaR": cvar, "MeanCVaR": .5 * (mu + cvar)}[objective]
            certified = row["solver_status"] == "Optimal" and float(row["mip_gap"]) <= .001
            groups[(objective, row["alpha"], n)].append((row["case_id"], value, set(cells), certified, float(row["mip_gap"])))

    assert len(groups) == 27 and sum(map(len, groups.values())) == 135
    output = manuscript / "tables"
    results = []
    for objective in POLICY:
        for alpha in ("0.01", "0.02", "0.03"):
            for n in CAMPAIGNS:
                runs = sorted(groups[(objective, alpha, n)])
                assert [r[0] for r in runs] == [f"case{k:02}" for k in range(5)]
                values = [r[1] for r in runs]
                similarities = []
                for a, b in itertools.combinations(runs, 2):
                    union = a[2] | b[2]
                    similarities.append(len(a[2] & b[2]) / len(union) if union else 1.)
                assert len(similarities) == 10
                results.append(dict(objective=objective, alpha=alpha, n=n,
                                    valid_replications=5, oos_mean=mean(values),
                                    oos_sample_sd=stdev(values), jaccard_mean=mean(similarities),
                                    jaccard_min=min(similarities), jaccard_max=max(similarities),
                                    certified=sum(r[3] for r in runs),
                                    max_final_gap=max(r[4] for r in runs)))
    with (output / "new20_oos_stability.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=results[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Objective & $\alpha$ & $n$ & Test objective (mean $\pm$ SD) & Jaccard mean [range] & Certified \\",
             r"\midrule"]
    for index, r in enumerate(results):
        if index and index % 9 == 0:
            lines.append(r"\midrule")
        objective = OBJECTIVES[r["objective"]] if index % 9 == 0 else ""
        alpha = r["alpha"] if index % 3 == 0 else ""
        lines.append(f'{objective} & {alpha} & {r["n"]} & '
                     f'{r["oos_mean"]:.2f} $\\pm$ {r["oos_sample_sd"]:.2f} & '
                     f'{r["jaccard_mean"]:.2f} [{r["jaccard_min"]:.2f}, {r["jaccard_max"]:.2f}] & '
                     f'{r["certified"]}/5 '+r'\\')
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (output / "new20_oos_stability.tex").write_text("\n".join(lines) + "\n")
    print("Checked 135 worker JSON files, 135 original-cell solution JSON/CSV pairs, 27 matched five-replication groups and their split files; wrote OOS and Jaccard table.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", type=Path, required=True)
    parser.add_argument("--manuscript", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    reproduce(args.implementation.resolve(), args.manuscript.resolve())
