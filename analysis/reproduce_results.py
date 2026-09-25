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
    def cells(rr):
        opt, total, avg_gap, max_gap, avg_time, sd_time = summarize(rr)
        return f"{opt}/{total} & {avg_gap:.2f} & {max_gap:.2f} & {avg_time:.1f} & {sd_time:.1f}"
    solve = table(r"Objective & Method & $n=100$ & $n=200$ & $n=400$ & Total", "llrrrr")
    gaps = table(r"Objective & Method & $N_{\rm opt}/N$ & Mean gap & Max gap & Mean time & SD time", "llrrrrr")
    alpha_solved = table(r"Objective & Method & $\alpha=0.01$ & $\alpha=0.02$ & $\alpha=0.03$", "llrrr")
    records = []
    for oi, objective in enumerate(OBJECTIVES):
        if oi:
            for lines in (solve, gaps, alpha_solved): lines.append(r"\midrule")
        alpha_table = table(r"Method & $\alpha$ & $N_{\rm opt}/N$ & Mean gap & Max gap & Mean time & SD time", "lrrrrrr")
        for mi, method in enumerate(METHODS):
            rr = by_objective[objective][method]
            assert len(rr) == 45
            by_n = [[r for r in rr if r["train_count"] == n] for n in ("100", "200", "400")]
            by_alpha = [[r for r in rr if r["alpha"] == a] for a in ("0.01", "0.02", "0.03")]
            assert all(len(x) == 15 for x in by_n + by_alpha)
            assert sum(summarize(x)[0] for x in by_n) == summarize(rr)[0] == sum(summarize(x)[0] for x in by_alpha)
            prefix = f"{LATEX[objective]} & {LABEL[method]} & "
            solve.append(prefix + " & ".join(f"{summarize(x)[0]}/{len(x)}" for x in by_n + [rr]) + r" \\")
            gaps.append(prefix + cells(rr) + r" \\")
            alpha_solved.append(prefix + " & ".join(f"{summarize(x)[0]}/15" for x in by_alpha) + r" \\")
            if mi: alpha_table.append(r"\addlinespace")
            for alpha, subset in zip(("0.01", "0.02", "0.03"), by_alpha):
                alpha_table.append(f"{LABEL[method]} & {alpha} & " + cells(subset) + r" \\")
            # Machine-readable statistics also expose each five-replication alpha/n block.
            for alpha in ("all", "0.01", "0.02", "0.03"):
                for n in ("all", "100", "200", "400"):
                    subset = [r for r in rr if (alpha == "all" or r["alpha"] == alpha) and (n == "all" or r["train_count"] == n)]
                    assert len(subset) == (45 if alpha == n == "all" else 15 if "all" in (alpha, n) else 5)
                    records.append((objective, method, alpha, n, *summarize(subset)))
        finish(alpha_table, f"new20_alpha_{objective}.tex")
    finish(solve, "new20_solved.tex")
    finish(gaps, "new20_gaps_times.tex")
    finish(alpha_solved, "new20_alpha_solved.tex")
    with (output / "new20_statistics.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("objective", "method", "alpha", "train_count", "optimal", "total", "mean_gap_pct", "max_gap_pct", "mean_time_s", "sample_sd_time_s"))
        writer.writerows(records)
    return by_objective


def write_selection_audit(groups, output: Path):
    """Audit whether a certified placement could be selected, without using damaged suffix fields."""
    preferred = {"Expected": "Combinatorial", "CVaR": "Path-exp", "MeanCVaR": "Path-exp"}
    records = []
    for (alpha, n, case, obj), runs in sorted(groups.items()):
        first = next(r for r in runs if classify(r["method"]) == preferred[obj])
        certified = [r for r in runs if test_run(r)]
        if test_run(first):
            chosen, rule = first, "preferred"
        elif certified:
            # An exact same-sample, same-objective substitute: deterministic method order.
            chosen, rule = min(certified, key=lambda r: METHODS.index(classify(r["method"]))), "certified substitute"
        else:
            chosen, rule = None, "no certified method"
        records.append((obj, alpha, n, case, rule, preferred[obj],
                        "" if chosen is None else classify(chosen["method"]),
                        "" if chosen is None else chosen["task_id"],
                        min(float(r["mip_gap"]) for r in runs)))
    with (output / "new20_selection_audit.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("objective", "alpha", "train_count", "case_id", "selection_status",
                         "preferred_method", "selected_method", "selected_task_id", "best_available_final_gap"))
        writer.writerows(records)
    assert len(records) == 135
    assert Counter(row[4] for row in records) == {
        "preferred": 94, "certified substitute": 2, "no certified method": 39}
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Objective & $\alpha$ & $n=100$ & $n=200$ & $n=400$ & Total \\", r"\midrule"]
    for obj in OBJECTIVES:
        for alpha in ("0.01", "0.02", "0.03"):
            subsets = [[r for r in records if r[0] == obj and r[1] == alpha and r[2] == n]
                       for n in ("100", "200", "400")]
            assert all(len(x) == 5 for x in subsets)
            counts = [sum(r[4] != "no certified method" for r in x) for x in subsets]
            lines.append(f"{LATEX[obj]} & {alpha} & " + " & ".join(f"{x}/5" for x in counts)
                         + f" & {sum(counts)}/15" + r" \\")
        if obj != OBJECTIVES[-1]:
            lines.append(r"\midrule")
    (output / "new20_selection_coverage.tex").write_text(
        "\n".join(lines + [r"\bottomrule", r"\end{tabular}"]) + "\n")


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
    by_objective = write_tables(groups, args.manuscript / "tables")
    write_selection_audit(groups, args.manuscript / "tables")
    write_figure(by_objective, args.manuscript / "figs/new20_certified.tex")
    print("Checked: 810 complete reduced runs, 519 excluded Reburn rows; 60/60 Reburn training splits differ.")
    print("Wrote reduced-panel tables, selection audit and certification profile; damaged suffix excluded.")


if __name__ == "__main__":
    main()
