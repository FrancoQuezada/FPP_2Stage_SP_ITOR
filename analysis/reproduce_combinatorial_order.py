#!/usr/bin/env python3
"""Reproduce the paired eta-order sensitivity analysis for Combinatorial B&B.

The eta-ascending campaign predates the explicit scenario-order output field.
Its order is therefore an inference from the base method name and the documented
default that preserves the previous behavior. The eta-descending order is
recorded explicitly in its manifest, consolidated CSV, and worker JSON files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, stdev


OBJECTIVES = ("Expected", "CVaR", "MeanCVaR")
ORDERS = ("eta-asc", "eta-desc")
TRAIN_COUNTS = ("100", "200")
ALPHAS = ("0.01", "0.02", "0.03")
LATEX_OBJECTIVE = {
    "Expected": "Expected",
    "CVaR": "CVaR",
    "MeanCVaR": "Mean--CVaR",
}
LATEX_ORDER = {
    "eta-asc": r"$\eta$-asc",
    "eta-desc": r"$\eta$-desc",
}
CAMPAIGNS = {
    "eta-asc": "fpp_new_instances_scaling",
    "eta-desc": "fpp_new_instances_scaling_new20x20_100_200",
}
ORDER_PROVENANCE = {
    "eta-asc": "inferred: legacy base method and documented eta-asc default",
    "eta-desc": "recorded explicitly in manifest, CSV, and JSON",
}


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def is_resolved(row: dict[str, str]) -> bool:
    return row["solver_status"] == "Optimal" and float(row["mip_gap"]) <= 0.001


def scientific_key(row: dict[str, str]):
    return (
        row["instance_id"],
        row["case_id"],
        row["alpha"],
        row["train_count"],
        row["objective_family"],
    )


def canonical_ids(value) -> tuple[int, ...]:
    if isinstance(value, list):
        return tuple(int(item) for item in value)
    normalized = str(value).replace("\r", "\n").replace("\n", ",")
    return tuple(int(item) for item in normalized.split(",") if item.strip())


def ids_hash(ids: tuple[int, ...]) -> str:
    return hashlib.sha256(",".join(map(str, ids)).encode("utf-8")).hexdigest()


def values_match(csv_value: str, json_value) -> bool:
    if isinstance(json_value, bool):
        return csv_value.lower() == str(json_value).lower()
    if isinstance(json_value, (int, float)):
        return math.isclose(float(csv_value), float(json_value), rel_tol=1e-10, abs_tol=1e-8)
    if isinstance(json_value, list):
        return canonical_ids(csv_value) == canonical_ids(json_value)
    return csv_value == str(json_value)


def resolve_split(campaign: Path, recorded_path: str) -> Path:
    path = campaign / "splits" / Path(recorded_path).name
    assert path.is_file(), path
    return path


def validate_order_documentation(implementation: Path):
    header = (implementation / "cpp_cplex_firebreak/include/benders/FppCombinatorialBenders.hpp").read_text()
    generator = (implementation / "cpp_cplex_firebreak/scripts/generate_fpp_new_instances_scaling_manifests.py").read_text()
    readme = (implementation / "cpp_cplex_firebreak/README.md").read_text()
    assert "FppCombinatorialBendersScenarioOrder::EtaAscending" in header
    assert 'scenario_order = "eta-desc" if method.endswith("-EtaDesc") else "eta-asc"' in generator
    assert "`eta-asc` is the default and preserves the previous behavior" in readme


def load_campaign(batch_root: Path, order: str):
    campaign = batch_root / CAMPAIGNS[order]
    headers, all_rows = read_csv(campaign / "batch_results_all.csv")
    assert len(headers) == len(set(headers))
    rows = [
        row
        for row in all_rows
        if row["instance_id"] == "new20x20" and "Combinatorial" in row["method"]
    ]
    manifest_headers, manifest_rows = read_csv(campaign / "manifests/full_task_manifest.csv")
    manifests = {
        row["task_id"]: row
        for row in manifest_rows
        if row["instance_id"] == "new20x20" and "Combinatorial" in row["method"]
    }
    assert len(rows) == len(manifests) == 90
    assert len({row["task_id"] for row in rows}) == 90
    assert len({scientific_key(row) for row in rows}) == 90
    assert Counter(row["objective_family"] for row in rows) == Counter({objective: 30 for objective in OBJECTIVES})
    assert Counter(row["train_count"] for row in rows) == Counter({count: 45 for count in TRAIN_COUNTS})
    assert Counter(row["alpha"] for row in rows) == Counter({alpha: 30 for alpha in ALPHAS})
    assert {row["case_id"] for row in rows} == {f"case{i:02d}" for i in range(5)}
    assert {row["solver_status"] for row in rows} <= {"Optimal", "Feasible"}
    assert {row["instance_type"] for row in rows} == {"shortest_path"}
    assert {row["test_count"] for row in rows} == {"1000"}
    assert {row["time_limit"] for row in rows} == {"1800"}
    assert {row["threads"] for row in rows} == {"1"}
    expected_risk = {
        "Expected": ("expected", "0.9", "1.0"),
        "CVaR": ("cvar", "0.9", "1.0"),
        "MeanCVaR": ("mean-cvar", "0.9", "0.5"),
    }
    for row in rows:
        assert (
            row["risk_measure"], row["cvar_beta"], row["cvar_lambda"]
        ) == expected_risk[row["objective_family"]]

    if order == "eta-asc":
        assert "combinatorial_benders_scenario_order" not in headers
        assert "combinatorial_benders_scenario_order" not in manifest_headers
        assert all(not row["method"].endswith("-EtaDesc") for row in rows)
    else:
        assert "combinatorial_benders_scenario_order" in headers
        assert "combinatorial_benders_scenario_order" in manifest_headers
        assert {row["combinatorial_benders_scenario_order"] for row in rows} == {"eta-desc"}
        assert {row["combinatorial_benders_scenario_order"] for row in manifests.values()} == {"eta-desc"}
        assert all(row["method"].endswith("-EtaDesc") for row in rows)

    json_payloads = {}
    for path in campaign.glob("workers/*/json/*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("instance_id") == "new20x20" and "Combinatorial" in payload.get("method", ""):
            json_payloads[path.stem] = payload
    assert len(json_payloads) == 90

    manifest_match_fields = (
        "instance_id", "case_id", "case_index", "seed", "split_seed", "alpha",
        "train_count", "test_count", "objective_family", "method", "risk_measure",
        "cvar_beta", "cvar_lambda", "time_limit", "threads",
    )
    json_match_fields = (
        "method", "solver_status", "objective_in_sample", "best_bound",
        "runtime_seconds", "mip_gap", "train_ids", "test_ids",
    )
    for row in rows:
        manifest = manifests[row["task_id"]]
        payload = json_payloads[row["task_id"]]
        for field in manifest_match_fields:
            assert row[field] == manifest[field], (row["task_id"], field)
        assert manifest["mip_gap"] == "0.001"
        assert manifest["combinatorial_benders_lift"] == "heuristic"
        assert manifest["combinatorial_benders_cut_sampling_ratio"] == "0.10"
        assert manifest["combinatorial_benders_separate_fractional"] == "true"
        assert manifest["combinatorial_benders_initial_cuts"] == "true"
        assert payload["validation_status"] == "pass"
        for field in json_match_fields:
            assert values_match(row[field], payload[field]), (row["task_id"], field)
        assert (row["solver_status"] == "Optimal") == (float(row["mip_gap"]) <= 0.001)
        assert math.isfinite(float(row["mip_gap"])) and float(row["mip_gap"]) >= 0
        assert math.isfinite(float(row["runtime_seconds"])) and float(row["runtime_seconds"]) > 0
        if order == "eta-asc":
            assert "combinatorial_benders_scenario_order" not in payload
        else:
            assert payload["combinatorial_benders_scenario_order"] == "eta-desc"
    return campaign, rows, manifests, json_payloads


def summarize(rows: list[dict[str, str]]):
    assert len(rows) > 1
    gaps = [100 * float(row["mip_gap"]) for row in rows]
    times = [float(row["runtime_seconds"]) for row in rows]
    return {
        "optimal": sum(is_resolved(row) for row in rows),
        "total": len(rows),
        "mean_gap_pct": mean(gaps),
        "max_gap_pct": max(gaps),
        "mean_time_s": mean(times),
        "sample_sd_time_s": stdev(times),
    }


def table_start(spec: str, header: str):
    return [
        rf"\begin{{tabular}}{{{spec}}}",
        r"\toprule",
        header + r" \\",
        r"\midrule",
    ]


def table_finish(path: Path, lines: list[str]):
    path.write_text("\n".join(lines + [r"\bottomrule", r"\end{tabular}"]) + "\n", encoding="utf-8")


def metric_cells(summary):
    return (
        f'{summary["optimal"]}/{summary["total"]} & '
        f'{summary["mean_gap_pct"]:.2f} & {summary["max_gap_pct"]:.2f} & '
        f'{summary["mean_time_s"]:.1f} & {summary["sample_sd_time_s"]:.1f}'
    )


def write_outputs(manuscript: Path, indexed, pair_metadata):
    tables = manuscript / "tables"
    analysis = manuscript / "analysis"
    tables.mkdir(parents=True, exist_ok=True)
    analysis.mkdir(parents=True, exist_ok=True)

    main = table_start(
        "llrrrrr",
        r"Objective & Order & $N_{\rm opt}/N$ & Mean gap & Max gap & Mean time & SD time",
    )
    by_n = table_start(
        "llrrrrrr",
        r"Objective & Order & $n$ & $N_{\rm opt}/N$ & Mean gap & Max gap & Mean time & SD time",
    )
    by_alpha = table_start(
        "llrrrrrr",
        r"Objective & Order & $\alpha$ & $N_{\rm opt}/N$ & Mean gap & Max gap & Mean time & SD time",
    )
    paired = table_start(
        "lrrrrr",
        r"Objective & Pairs & Both & Asc only & Desc only & Neither",
    )
    statistic_rows = []
    pair_summary_rows = []
    for objective_index, objective in enumerate(OBJECTIVES):
        if objective_index:
            main.append(r"\midrule")
            by_n.append(r"\midrule")
            by_alpha.append(r"\midrule")
        for order in ORDERS:
            rows = [row for key, row in indexed[order].items() if key[-1] == objective]
            summary = summarize(rows)
            main.append(f"{LATEX_OBJECTIVE[objective]} & {LATEX_ORDER[order]} & {metric_cells(summary)} " + r"\\")
            statistic_rows.append((objective, order, "all", "all", *summary.values()))
            for train_count in TRAIN_COUNTS:
                subset = [row for row in rows if row["train_count"] == train_count]
                summary = summarize(subset)
                assert summary["total"] == 15
                by_n.append(f"{LATEX_OBJECTIVE[objective]} & {LATEX_ORDER[order]} & {train_count} & {metric_cells(summary)} " + r"\\")
                statistic_rows.append((objective, order, "train_count", train_count, *summary.values()))
            for alpha in ALPHAS:
                subset = [row for row in rows if row["alpha"] == alpha]
                summary = summarize(subset)
                assert summary["total"] == 10
                by_alpha.append(f"{LATEX_OBJECTIVE[objective]} & {LATEX_ORDER[order]} & {alpha} & {metric_cells(summary)} " + r"\\")
                statistic_rows.append((objective, order, "alpha", alpha, *summary.values()))

        objective_pairs = [metadata for metadata in pair_metadata if metadata["objective_family"] == objective]
        outcomes = Counter(metadata["certification_outcome"] for metadata in objective_pairs)
        assert sum(outcomes.values()) == 30
        paired.append(
            f'{LATEX_OBJECTIVE[objective]} & 30 & {outcomes["both"]} & '
            f'{outcomes["asc-only"]} & {outcomes["desc-only"]} & {outcomes["neither"]} ' + r"\\"
        )
        both = [metadata for metadata in objective_pairs if metadata["certification_outcome"] == "both"]
        asc_times = [float(metadata["asc_runtime_seconds"]) for metadata in both]
        desc_times = [float(metadata["desc_runtime_seconds"]) for metadata in both]
        pair_summary_rows.append({
            "objective": objective,
            "pairs": len(objective_pairs),
            "both_resolved": outcomes["both"],
            "asc_only": outcomes["asc-only"],
            "desc_only": outcomes["desc-only"],
            "neither": outcomes["neither"],
            "both_resolved_asc_faster": sum(a < d for a, d in zip(asc_times, desc_times)),
            "both_resolved_desc_faster": sum(d < a for a, d in zip(asc_times, desc_times)),
            "both_resolved_equal_time": sum(math.isclose(a, d) for a, d in zip(asc_times, desc_times)),
            "both_resolved_mean_asc_time_s": mean(asc_times),
            "both_resolved_mean_desc_time_s": mean(desc_times),
        })

    table_finish(tables / "combinatorial_order_main.tex", main)
    table_finish(tables / "combinatorial_order_by_n.tex", by_n)
    table_finish(tables / "combinatorial_order_by_alpha.tex", by_alpha)
    table_finish(tables / "combinatorial_order_paired.tex", paired)

    with (analysis / "combinatorial_order_statistics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow((
            "objective", "order", "aggregation", "level", "optimal", "total",
            "mean_gap_pct", "max_gap_pct", "mean_time_s", "sample_sd_time_s",
        ))
        writer.writerows(statistic_rows)
    with (analysis / "combinatorial_order_pairing.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = list(pair_metadata[0])
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(pair_metadata)
    with (analysis / "combinatorial_order_pair_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = list(pair_summary_rows[0])
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(pair_summary_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", type=Path, required=True)
    parser.add_argument("--manuscript", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    implementation = args.implementation.resolve()
    validate_order_documentation(implementation)
    batch_root = implementation / "cpp_cplex_firebreak/Results_server/batch"
    loaded = {order: load_campaign(batch_root, order) for order in ORDERS}
    indexed = {order: {scientific_key(row): row for row in loaded[order][1]} for order in ORDERS}
    assert indexed["eta-asc"].keys() == indexed["eta-desc"].keys()

    config_fields = (
        "seed_base", "seed", "split_seed", "instance_id", "folder_name", "instance_type",
        "declared_cells", "inferred_cells", "metadata_status", "metadata_consistent",
        "graph_variant", "landscape", "forest_path", "results_path", "alpha", "train_count",
        "test_count", "training_pool_min", "training_pool_max", "test_pool_min", "test_pool_max",
        "fixed_oos_test_set", "objective_family", "risk_measure", "cvar_beta", "cvar_lambda",
        "use_combinatorial_benders", "combinatorial_benders_lift",
        "combinatorial_benders_cut_sampling_ratio", "combinatorial_benders_separate_fractional",
        "combinatorial_benders_initial_cuts", "projected_llbi_root_rounds",
        "projected_llbi_max_cuts_per_round", "projected_llbi_violation_tolerance",
        "time_limit", "mip_gap", "threads",
    )
    pair_metadata = []
    for key in sorted(indexed["eta-asc"]):
        asc = indexed["eta-asc"][key]
        desc = indexed["eta-desc"][key]
        asc_campaign, _, asc_manifests, asc_json = loaded["eta-asc"]
        desc_campaign, _, desc_manifests, desc_json = loaded["eta-desc"]
        asc_manifest, desc_manifest = asc_manifests[asc["task_id"]], desc_manifests[desc["task_id"]]
        assert all(asc_manifest.get(field) == desc_manifest.get(field) for field in config_fields)
        assert canonical_ids(asc["train_ids"]) == canonical_ids(desc["train_ids"])
        assert canonical_ids(asc["test_ids"]) == canonical_ids(desc["test_ids"])
        for kind in ("train", "test"):
            asc_split = resolve_split(asc_campaign, asc_manifest[f"{kind}_split_path"])
            desc_split = resolve_split(desc_campaign, desc_manifest[f"{kind}_split_path"])
            assert asc_split.read_bytes() == desc_split.read_bytes()
            assert canonical_ids(asc_split.read_text()) == canonical_ids(asc[f"{kind}_ids"])

        asc_resolved, desc_resolved = is_resolved(asc), is_resolved(desc)
        outcome = (
            "both" if asc_resolved and desc_resolved
            else "asc-only" if asc_resolved
            else "desc-only" if desc_resolved
            else "neither"
        )
        train_ids = canonical_ids(asc["train_ids"])
        test_ids = canonical_ids(asc["test_ids"])
        pair_metadata.append({
            "instance_id": key[0],
            "case_id": key[1],
            "alpha": key[2],
            "train_count": key[3],
            "objective_family": key[4],
            "train_id_count": len(train_ids),
            "test_id_count": len(test_ids),
            "train_ids_sha256": ids_hash(train_ids),
            "test_ids_sha256": ids_hash(test_ids),
            "asc_task_id": asc["task_id"],
            "desc_task_id": desc["task_id"],
            "asc_order_provenance": ORDER_PROVENANCE["eta-asc"],
            "desc_order_provenance": ORDER_PROVENANCE["eta-desc"],
            "asc_validation_status": asc_json[asc["task_id"]]["validation_status"],
            "desc_validation_status": desc_json[desc["task_id"]]["validation_status"],
            "asc_solver_status": asc["solver_status"],
            "desc_solver_status": desc["solver_status"],
            "asc_mip_gap": asc["mip_gap"],
            "desc_mip_gap": desc["mip_gap"],
            "asc_runtime_seconds": asc["runtime_seconds"],
            "desc_runtime_seconds": desc["runtime_seconds"],
            "certification_outcome": outcome,
        })

    assert len(pair_metadata) == 90
    write_outputs(args.manuscript.resolve(), indexed, pair_metadata)
    expected = {
        "Expected": (28, 29),
        "CVaR": (16, 15),
        "MeanCVaR": (21, 25),
    }
    for objective, counts in expected.items():
        observed = tuple(
            sum(is_resolved(row) for key, row in indexed[order].items() if key[-1] == objective)
            for order in ORDERS
        )
        assert observed == counts, (objective, observed)

    version_fields = ("solver_version", "cplex_version", "hardware", "hostname", "cpu_model", "processor")
    assert not any(
        any(field in payload for field in version_fields)
        for order in ORDERS
        for payload in loaded[order][3].values()
    )
    print("Verified 90 paired new20x20 configurations and 180 validation-pass JSON records.")
    print("Wrote four LaTeX tables, full-precision statistics, pair records, and pair summaries.")
    print("eta-asc is inferred from the legacy base method and documented default; eta-desc is explicit.")
    print("No hardware or effective solver-version fields are recorded; no 400/600 rows were read.")


if __name__ == "__main__":
    main()
