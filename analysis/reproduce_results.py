#!/usr/bin/env python3
"""Reproduce the manuscript's solver table and certification profile.

Only columns preceding selected_firebreaks are read from the damaged new20 CSV.
Run from anywhere: python analysis/reproduce_results.py --implementation ../implementation
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from math import isfinite

OBJECTIVES = ("Expected", "CVaR", "MeanCVaR")
METHODS = ("SAA", "Root", "Standard", "Coverage-exp", "Path-exp", "Combinatorial")
LATEX = {"Expected": "Expected", "CVaR": "CVaR", "MeanCVaR": "Mean--CVaR"}
LABEL = {"SAA": "Extensive SAA", "Root": "LP B\\&B + Root", "Standard": "LP B\\&B + Standard",
         "Coverage-poly": "LP B\\&B + Coverage-poly", "Path-poly": "LP B\\&B + Path-poly",
         "Coverage-exp": "LP B\\&B + Coverage-exp", "Path-exp": "LP B\\&B + Path-exp",
         "Combinatorial": "Combinatorial B\\&B"}


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def classify(name: str) -> str:
    if "FPP-SAA" in name:
        return "SAA"
    if "Combinatorial" in name:
        return "Combinatorial"
    for family in ("Coverage", "Path"):
        for variant in ("poly", "exp"):
            if f"Projected{family}LLBI-{variant}" in name:
                return f"{family}-{variant}"
    if "-LLBI-" in name:
        return "Standard"
    assert "RootCuts" in name, name
    return "Root"


def key(r):
    return r["alpha"], r["train_count"], r["case_id"], r["objective_family"]


def test_run(r):
    gap = float(r["mip_gap"])
    assert r["solver_status"] in ("Optimal", "Feasible"), r
    assert (r["solver_status"] == "Optimal") == (gap <= .001), (r["task_id"], gap)
    assert isfinite(gap) and gap >= 0
    assert isfinite(float(r["runtime_seconds"])) and float(r["runtime_seconds"]) > 0
    return r["solver_status"] == "Optimal"


def split(implementation: Path, relative: str):
    path = implementation / "cpp_cplex_firebreak" / relative
    return tuple(int(line) for line in path.read_text().splitlines() if line.strip())


def verify_new20(base: Path, implementation: Path):
    campaign = base / "fpp_new20x20_scaling"
    headers, rows = read_csv(campaign / "batch_results_partial_resumen.csv")
    assert len(rows) == 1329 and len(headers) == 132
    assert headers[108] == "selected_firebreaks" and headers[122:] == [""] * 10
    assert len(set(headers[:108])) == 108  # the trailing malformed fields are never read
    rows = [{field: r[field] for field in headers[:108]} for r in rows]
    _, manifest = read_csv(campaign / "manifests/full_task_manifest.csv")
    assert len(manifest) == 2160 and len({r["method"] for r in manifest}) == 18
    tasks = {r["task_id"]: r for r in manifest}
    assert len(tasks) == len(manifest)
    assert len({r["task_id"] for r in rows}) == len(rows)
    assert Counter(r["instance_id"] for r in rows) == {"new20x20": 810, "new20x20_reburn": 519}
    assert Counter(r["solver_status"] for r in rows if r["instance_id"] == "new20x20_reburn") == {"Feasible": 519}
    _, preflight = read_csv(campaign / "preflight_new_instances_smoke.csv")
    diagnostics = {(r["folder"], r["graph_variant"]): r for r in preflight}
    reduced_preflight = diagnostics["20x20", "shortest_path"]
    assert int(reduced_preflight["analyzed_scenarios"]) == 10000
    assert tuple(float(reduced_preflight[field]) for field in
                 ("rooted_tree_ratio", "acyclic_dag_ratio", "empty_ratio")) == (.1241, .8683, .0076)
    reburn_preflight = diagnostics["20x20_reburn", "reburn_all_paths"]
    assert float(reburn_preflight["general_directed_graph_ratio"]) == .9426
    for r in rows:
        m = tasks[r["task_id"]]
        for field in ("instance_id", "alpha", "train_count", "test_count", "case_id", "objective_family", "method"):
            assert r[field] == m[field], (r["task_id"], field)
        assert m["threads"] == "1" and m["time_limit"] == r["time_limit"] == "1800"
        assert m["mip_gap"] == "0.001" and m["test_count"] == "1000"
        assert m["cvar_beta"] == "0.9"
        if r["objective_family"] == "MeanCVaR":
            assert m["cvar_lambda"] == "0.5"
        test_run(r)
    reduced = [r for r in rows if r["instance_id"] == "new20x20"]
    assert Counter(r["solver_status"] for r in reduced) == {"Optimal": 424, "Feasible": 386}
    groups = defaultdict(list)
    for r in reduced:
        assert r["train_count"] in ("100", "200", "400") and r["alpha"] in ("0.01", "0.02", "0.03")
        assert r["case_id"] in {f"case{i:02d}" for i in range(5)}
        assert r["objective_family"] in OBJECTIVES
        groups[key(r)].append(r)
    assert len(groups) == 135
    split_cache = {}
    for group, runs in groups.items():
        assert len(runs) == 6 and {classify(r["method"]) for r in runs} == set(METHODS)
        paths = {(tasks[r["task_id"]]["train_split_path"], tasks[r["task_id"]]["test_split_path"]) for r in runs}
        assert len({tuple(tasks[r["task_id"]][f] for f in ("instance_id", "alpha", "objective_family", "risk_measure", "cvar_beta", "cvar_lambda", "time_limit", "mip_gap", "threads")) for r in runs}) == 1
        assert len(paths) == 1
        training, testing = next(iter(paths))
        for name in (training, testing):
            if name not in split_cache:
                split_cache[name] = split(implementation, name)
        assert len(split_cache[training]) == int(group[1]) and len(split_cache[testing]) == 1000
        assert len(set(split_cache[training])) == int(group[1])
        assert set(split_cache[testing]) == set(range(9001, 10001))
        assert max(split_cache[training]) <= 9000
        # Objective discrepancies among runs certified to tolerance should be small.
        certified = [float(r["objective_in_sample"]) for r in runs if test_run(r)]
        if len(certified) > 1:
            assert max(certified) - min(certified) <= max(.5, .002 * min(certified)), group
    # Cross-graph training partitions differ even when alpha, count, case coincide.
    pairs = defaultdict(lambda: defaultdict(set))
    for r in manifest:
        pairs[r["alpha"], r["train_count"], r["case_id"]][r["instance_id"]].add((
            r["train_split_path"], r["test_split_path"]))
    assert len(pairs) == 60
    for variants in pairs.values():
        assert all(len(paths) == 1 for paths in variants.values())
        a, b = next(iter(variants["new20x20"])), next(iter(variants["new20x20_reburn"]))
        assert set(split(implementation, a[0])) != set(split(implementation, b[0]))
        assert split(implementation, a[1]) == split(implementation, b[1])
    assert sum(float(r["objective_in_sample"]) > 400 for r in reduced) == 14
    assert sum(float(r["objective_in_sample"]) > 400 for r in rows if r["instance_id"] == "new20x20_reburn") == 57
    return groups


def summarize(rr):
    """All recorded runs; gap in percent and sample standard deviation of time."""
    assert len(rr) > 1
    gaps = [100 * float(r["mip_gap"]) for r in rr]
    times = [float(r["runtime_seconds"]) for r in rr]
    return (sum(test_run(r) for r in rr), len(rr), mean(gaps), max(gaps), mean(times), stdev(times))


def write_tables(groups, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    by_objective = defaultdict(lambda: defaultdict(list))
    for k, runs in groups.items():
        for r in runs:
            by_objective[k[3]][classify(r["method"])].append(r)
    def table(header, spec):
        return [r"\begin{tabular}{" + spec + "}", r"\toprule", header + r" \\", r"\midrule"]
    def finish(lines, name):
        (output / name).write_text("\n".join(lines + [r"\bottomrule", r"\end{tabular}"]) + "\n")
    gaps = table(r"Objective & Method & Certified (\%) & Mean gap (\%) & Max gap (\%) & Mean time (s)", "llrrrr")
    records = []
    for oi, objective in enumerate(OBJECTIVES):
        if oi:
            gaps.append(r"\midrule")
        for method in METHODS:
            rr = by_objective[objective][method]
            assert len(rr) == 45
            by_n = [[r for r in rr if r["train_count"] == n] for n in ("100", "200", "400")]
            by_alpha = [[r for r in rr if r["alpha"] == a] for a in ("0.01", "0.02", "0.03")]
            assert all(len(x) == 15 for x in by_n + by_alpha)
            assert sum(summarize(x)[0] for x in by_n) == summarize(rr)[0] == sum(summarize(x)[0] for x in by_alpha)
            prefix = f"{LATEX[objective]} & {LABEL[method]} & "
            opt, total, avg_gap, max_gap, avg_time, _ = summarize(rr)
            assert total == 45
            gaps.append(prefix + f"{100 * opt / total:.1f} & {avg_gap:.2f} & {max_gap:.2f} & {avg_time:.1f}" + r" \\")
            # Machine-readable statistics also expose each five-replication alpha/n block.
            for alpha in ("all", "0.01", "0.02", "0.03"):
                for n in ("all", "100", "200", "400"):
                    subset = [r for r in rr if (alpha == "all" or r["alpha"] == alpha) and (n == "all" or r["train_count"] == n)]
                    assert len(subset) == (45 if alpha == n == "all" else 15 if "all" in (alpha, n) else 5)
                    records.append((objective, method, alpha, n, *summarize(subset)))
    finish(gaps, "new20_gaps_times.tex")
    with (output / "new20_statistics.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("objective", "method", "alpha", "train_count", "optimal", "total", "mean_gap_pct", "max_gap_pct", "mean_time_s", "sample_sd_time_s"))
        writer.writerows(records)
    return by_objective


def write_selection_audit(groups, output: Path):
    """Audit preferred-solver certification; do not treat alternatives as selected solutions."""
    preferred = {"Expected": "Combinatorial", "CVaR": "Path-exp", "MeanCVaR": "Path-exp"}
    records = []
    for (alpha, n, case, obj), runs in sorted(groups.items()):
        first = next(r for r in runs if classify(r["method"]) == preferred[obj])
        other_certified = sorted(classify(r["method"]) for r in runs if r is not first and test_run(r))
        records.append((obj, alpha, n, case, preferred[obj], first["task_id"],
                        test_run(first), float(first["mip_gap"]),
                        ";".join(other_certified), min(float(r["mip_gap"]) for r in runs)))
    with (output / "new20_selection_audit.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("objective", "alpha", "train_count", "case_id", "preferred_method",
                         "preferred_task_id", "preferred_certified", "preferred_final_gap",
                         "other_certified_methods", "best_available_final_gap"))
        writer.writerows(records)
    assert len(records) == 135
    assert Counter(row[0] for row in records if row[6]) == {
        "Expected": 43, "CVaR": 21, "MeanCVaR": 30}
    assert sum(bool(row[8]) for row in records if not row[6]) == 2


def write_figure(by_objective, path: Path):
    """Generate an editable vector PGFPlots figure without a binary asset."""
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = dict(zip(METHODS, ("gray!85!black,solid", "red!75!black,dashed", "orange!85!black,dotted",
                                "blue!75!black,dashdotted", "green!60!black,solid", "violet!75!black,dashed")))
    lines = [r"\begin{tikzpicture}",
             r"\begin{groupplot}[group style={group size=1 by 3,vertical sep=18pt},",
             r"  width=0.86\linewidth,height=0.22\textheight,xmin=0,xmax=1800,",
             r"  ymin=0,ymax=1,xtick={0,600,1200,1800},ytick={0,0.2,0.4,0.6,0.8,1},",
             r"  tick label style={font=\scriptsize},title style={font=\small},",
             r"  grid=major,grid style={black!15},enlarge x limits=false]" ]
    for j, obj in enumerate(OBJECTIVES):
        settings = ["title={" + LATEX[obj] + "}", r"ylabel={Fraction certified}",
                    r"ylabel style={font=\scriptsize}"]
        if j == 0:
            settings += ["legend to name=certlegend", "legend columns=3",
                         r"legend style={draw=none,font=\scriptsize}", "xticklabels={}"]
        elif j == 1:
            settings.append("xticklabels={}")
        else:
            settings += [r"xlabel={Solver time (s)}", r"xlabel style={font=\scriptsize}"]
        lines.append("\\nextgroupplot[" + ",".join(settings) + "]")
        for method in METHODS:
            rr = by_objective[obj][method]
            solved = sorted(float(r["runtime_seconds"]) for r in rr if test_run(r))
            assert len(rr) == 45 and all(t <= 1800 for t in solved)
            points = [(0, 0), *[(time, rank / 45) for rank, time in enumerate(solved, 1)],
                      (1800, len(solved) / 45)]
            coords = " ".join(f"({time:.4f},{fraction:.7f})" for time, fraction in points)
            lines.append(f"\\addplot+[const plot,mark=none,semithick,{styles[method]}] coordinates {{{coords}}};")
            if j == 0:
                lines.append("\\addlegendentry{" + method + "}")
    lines += [r"\end{groupplot}", r"\end{tikzpicture}", r"\par\smallskip",
              r"\pgfplotslegendfromname{certlegend}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", type=Path, required=True, help="Root of stochastic-firebreak-placement checkout")
    parser.add_argument("--manuscript", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    base = args.implementation / "cpp_cplex_firebreak/results/batch"
    groups = verify_new20(base, args.implementation)
    by_objective = write_tables(groups, args.manuscript / "tables")
    write_selection_audit(groups, args.manuscript / "tables")
    write_figure(by_objective, args.manuscript / "figs/new20_certified.tex")
    print("Checked: 810 complete reduced runs, 519 excluded Reburn rows; 60/60 Reburn training splits differ.")
    print("Wrote reduced-panel performance table, full statistics, preferred-method audit and enlarged certification profile; damaged suffix excluded.")


if __name__ == "__main__":
    main()
