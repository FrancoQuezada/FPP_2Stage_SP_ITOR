#!/usr/bin/env python3
"""Reproduce the manuscript's certified-solve tables from the committed batches.

Only columns preceding selected_firebreaks are read from the damaged new20 CSV.
Run from anywhere: python analysis/reproduce_results.py --implementation ../implementation
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

OBJECTIVES = ("Expected", "CVaR", "MeanCVaR")
METHODS = ("SAA", "Root", "Standard", "Coverage-exp", "Path-exp", "Combinatorial")
SUB_METHODS = ("Root", "Standard", "Coverage-poly", "Path-poly", "Coverage-exp", "Path-exp", "Combinatorial")
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
    assert (r["solver_status"] == "Optimal") == (gap <= .001000001), (r["task_id"], gap)
    assert float(r["runtime_seconds"]) > 0
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
        test_run(r)
    reduced = [r for r in rows if r["instance_id"] == "new20x20"]
    assert Counter(r["solver_status"] for r in reduced) == {"Optimal": 424, "Feasible": 386}
    groups = defaultdict(list)
    for r in reduced:
        assert r["train_count"] in ("100", "200", "400") and r["alpha"] in ("0.01", "0.02", "0.03")
        groups[key(r)].append(r)
    assert len(groups) == 135
    split_cache = {}
    for group, runs in groups.items():
        assert len(runs) == 6 and {classify(r["method"]) for r in runs} == set(METHODS)
        paths = {(tasks[r["task_id"]]["train_split_path"], tasks[r["task_id"]]["test_split_path"]) for r in runs}
        assert len(paths) == 1
        training, testing = next(iter(paths))
        for name in (training, testing):
            if name not in split_cache:
                split_cache[name] = split(implementation, name)
        assert len(split_cache[training]) == int(group[1]) and len(split_cache[testing]) == 1000
        assert len(set(split_cache[training])) == int(group[1])
        assert len(set(split_cache[testing])) == 1000
        assert max(split_cache[training]) <= 9000 and min(split_cache[testing]) >= 9001
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


def verify_sub20(base: Path):
    campaign = base / "fpp_projected_llbi_scaling"
    headers, rows = read_csv(campaign / "batch_results_all.csv")
    assert len(headers) == len(set(headers)) == 230 and len(rows) == 1440
    _, manifest = read_csv(campaign / "manifests/full_task_manifest.csv")
    assert len(manifest) == 1440
    tasks = {r["task_id"]: r for r in manifest}
    assert len(tasks) == len(manifest)
    groups = defaultdict(list)
    for r in rows:
        m = tasks[r["task_id"]]
        for field in ("alpha", "train_count", "test_count", "case_id", "objective_family", "method"):
            assert r[field] == m[field]
        assert r["landscape"] == m["landscape"] == "Sub20"
        assert m["threads"] == "1" and r["time_limit"] == m["time_limit"] == "1800"
        assert m["mip_gap"] == "0.001" and r["test_count"] == "200"
        assert r["validation_status"] in ("pass", "warn")
        test_run(r)
        groups[key(r)].append(r)
    assert len(groups) == 180
    for runs in groups.values():
        assert len(runs) == 8 and {classify(r["method"]) for r in runs} == set(SUB_METHODS) | {"SAA"}
        assert len({r["train_ids"] for r in runs}) == len({r["test_ids"] for r in runs}) == 1
    warnings = [r for r in rows if r["validation_status"] == "warn"]
    assert Counter(r["solver_status"] for r in rows) == {"Optimal": 605, "Feasible": 835}
    assert len(warnings) == 62 and {classify(r["method"]) for r in warnings} == {"SAA"}
    assert Counter(r["objective_family"] for r in warnings) == {"CVaR": 50, "MeanCVaR": 7, "Expected": 5}
    assert all(r["validation_status"] == "pass" for r in rows if classify(r["method"]) != "SAA")
    return groups


def write_tables(groups, subgroups, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    by_objective = defaultdict(lambda: defaultdict(list))
    for k, runs in groups.items():
        for r in runs:
            by_objective[k[3]][classify(r["method"])].append(r)
    solve = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Objective & Method & $n=100$ & $n=200$ & $n=400$ & Total \\", r"\midrule"]
    gaps = [r"\begin{tabular}{llrrrr}", r"\toprule",
            r"Objective & Method & Unsolved & Median gap (\%) & Paired & Time ratio \\", r"\midrule"]
    for oi, objective in enumerate(OBJECTIVES):
        if oi:
            solve.append(r"\midrule")
            gaps.append(r"\midrule")
        root = {key(r)[:3]: r for r in by_objective[objective]["Root"]}
        for method in METHODS:
            rr = by_objective[objective][method]
            assert len(rr) == 45
            counts = [sum(test_run(r) for r in rr if r["train_count"] == n) for n in ("100", "200", "400")]
            assert all(sum(r["train_count"] == n for r in rr) == 15 for n in ("100", "200", "400"))
            solve.append(f'{LATEX[objective]} & {LABEL[method]} & {counts[0]} & {counts[1]} & {counts[2]} & {sum(counts)} \\\\')
            unresolved = [100 * float(r["mip_gap"]) for r in rr if not test_run(r)]
            pairs = [(r, root[key(r)[:3]]) for r in rr if test_run(r) and test_run(root[key(r)[:3]])]
            ratio = median(float(r["runtime_seconds"]) / float(b["runtime_seconds"]) for r, b in pairs)
            gaps.append(f'{LATEX[objective]} & {LABEL[method]} & {len(unresolved)} & {median(unresolved):.2f} & {len(pairs)} & {ratio:.2f} \\\\')
    for lines, filename in [(solve, "new20_solved.tex"), (gaps, "new20_gaps_times.tex")]:
        lines += [r"\bottomrule", r"\end{tabular}"]
        (output / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    sub = [r"\begin{tabular}{lrrr}", r"\toprule",
           r"Method & Expected & CVaR & Mean--CVaR \\", r"\midrule"]
    for method in SUB_METHODS:
        counts = [sum(test_run(r) for group, runs in subgroups.items() if group[3] == obj
                      for r in runs if classify(r["method"]) == method) for obj in OBJECTIVES]
        sub.append(f'{LABEL[method]} & {counts[0]} & {counts[1]} & {counts[2]} \\\\')
    sub += [r"\bottomrule", r"\end{tabular}"]
    (output / "sub20_solved.tex").write_text("\n".join(sub) + "\n", encoding="utf-8")
    return by_objective


def write_figure(by_objective, path: Path):
    """Generate an editable vector PGFPlots figure without a binary asset."""
    path.parent.mkdir(parents=True, exist_ok=True)
    colors = dict(zip(METHODS, ("gray!80!black", "red!75!black", "orange!85!black",
                                "blue!75!black", "green!65!black", "violet!75!black")))
    lines = [r"\begin{tikzpicture}",
             r"\begin{groupplot}[group style={group size=3 by 1,horizontal sep=9pt},",
             r"  width=0.315\linewidth,height=0.275\linewidth,xmin=0,xmax=1800,",
             r"  ymin=0,ymax=1,xtick={0,600,1200,1800},ytick={0,0.2,0.4,0.6,0.8,1},",
             r"  xlabel={Solver time (s)},xlabel style={font=\scriptsize},",
             r"  tick label style={font=\tiny},title style={font=\small},",
             r"  grid=major,grid style={black!15},enlarge x limits=false]" ]
    for j, obj in enumerate(OBJECTIVES):
        settings = ["title={" + LATEX[obj] + "}"]
        if j == 0:
            settings += [r"ylabel={Fraction certified / 45}",
                         r"ylabel style={font=\scriptsize}",
                         "legend to name=certlegend", "legend columns=3",
                         r"legend style={draw=none,font=\scriptsize}"]
        else:
            settings.append("yticklabels={}")
        lines.append("\\nextgroupplot[" + ",".join(settings) + "]")
        for method in METHODS:
            rr = by_objective[obj][method]
            solved = sorted(float(r["runtime_seconds"]) for r in rr if test_run(r))
            assert len(rr) == 45 and all(t <= 1800 for t in solved)
            points = [(0, 0), *[(time, rank / 45) for rank, time in enumerate(solved, 1)],
                      (1800, len(solved) / 45)]
            coords = " ".join(f"({time:.4f},{fraction:.7f})" for time, fraction in points)
            lines.append(f"\\addplot+[const plot,mark=none,thin,color={colors[method]}] coordinates {{{coords}}};")
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
    sub = verify_sub20(base)
    by_objective = write_tables(groups, sub, args.manuscript / "tables")
    write_figure(by_objective, args.manuscript / "figs/new20_certified.tex")
    print("Checked: 810 complete reduced runs, 519 partial Reburn, 1440 Sub20; 60/60 Reburn training splits differ.")
    print("Wrote three tables and one certified-runtime plot; new20 fields after selected_firebreaks excluded.")


if __name__ == "__main__":
    main()
