# Computational results: provenance and reproduction

Implementation source: `stochastic-firebreak-placement` commit
`1a00d6b725d4b29d4e5da2e158efabe723c40d3b` on `main`. From a
manuscript checkout beside the implementation checkout, run:

```bash
python3 analysis/reproduce_results.py --implementation ../implementation
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

The reproduction command writes both the 810-run solver comparison and a
**separate** 135-placement held-out decision study. It does not edit any
implementation results. Tables in the manuscript are generated LaTeX;
`tables/new20_statistics.csv` and `tables/new20_oos_stability.csv` retain
unrounded values. Reproduction stops if a selected worker JSON, solution,
budget, matching training split, test-ID list, or evaluation field fails a
consistency check.

## Solver comparison (Table 2 and Figure 1)

Source: `cpp_cplex_firebreak/results/batch/fpp_new20x20_scaling/`:
`batch_results_partial_resumen.csv` (SHA256
`aef99697e1ff050c7481a2d3b3b5c3c6672e8cea8208c176cf940c2f5bce2a02`),
`manifests/full_task_manifest.csv`, and `splits/`. The prefix of 108
unambiguously named columns records 810 complete reduced-graph runs (and
519 excluded Reburn rows), with 45 runs per objective and method. The
script verifies all task IDs, experimental controls, five cases in each
joint group, matched within-problem splits, and 9001–10000 test IDs.
Certification requires status `Optimal` and final relative MIP gap at
most 0.001; 424 of 810 reduced runs qualify. Table 2 reports
`100 * N_opt / 45`, mean and maximum final relative MIP gaps (percent),
and mean observed solver time across all 45 runs. Figure 1 uses all
45 runs in each method/objective denominator throughout. Observed solver
times can exceed the requested 1,800-second cutoff.

The consolidated CSV suffix starting at `selected_firebreaks` has ten
blank column headings and displaced/truncated values. It is not read as
a solution file. The original worker JSON/solution files under this
campaign's `results/batch/fpp_new20x20_scaling/workers/` were not
committed and are absent from accessible history. These omissions do
not affect Table 2 or Figure 1, which use the verified CSV prefix.

## Separate held-out and placement study (Table 3)

**Prespecified common policy:** LP Branch-and-Benders with exponential
projected path inequalities (`Path-exp`), separately optimized under
Expected, CVaR, and MeanCVaR objectives. This is not the top solver
configuration for Expected loss in Table 2; common methodology across
objectives and all 27 size/budget/objective groups motivated the
selection. No result from another method replaces a Path-exp solution.
The source is independently committed worker-level files in:

- `cpp_cplex_firebreak/Results_server/batch/fpp_new_instances_scaling/` for
  `n=100,200`, 90 selected Path-exp workers (five cases at each of three
  budgets and three objectives for each n).
- `cpp_cplex_firebreak/Results_server/batch/fpp_new_instances_scaling_new20x20/`
  for `n=400`, 45 selected Path-exp workers (cases 00–04 at each budget
  and objective). Other cases and `n=600` are excluded.

Each selected record is independently located using its worker CSV and
checked against its worker JSON and solution JSON/CSV. The worker CSV
provides status/gap and evaluation fields; the worker JSON provides
original selected cell IDs, expected and empirical CVaR test values,
and training/test IDs; the solution JSON and CSV independently verify
all selected original cell IDs. Every decision uses at most its budget
(4, 8, or 12), with no duplicate or out-of-range cell IDs. All selected
training and test split files are byte-identical to the original target
manifest split files, the JSON's test IDs are exactly 9001–10000, and
all 135 corresponding worker CSV and JSON evaluation values agree. The
burned-area evaluator (`src/eval/BurnedAreaEvaluator.cpp`) computes
expected burned cells over all test cases and empirical CVaR at 0.9;
with 1,000 equally weighted scenarios, the latter agrees with the mean
of the worst 100 losses. The MeanCVaR outcome is the arithmetic mean
of these two metrics, as specified by lambda 0.5. All 135 placements
have a feasible worker output. Table 3 uses 5 independent training
replications for every one of 27 groups, sample SD of their held-out
objectives, and ten **dependent** within-group pairwise Jaccard indices
summarized by mean and range. Its additional certification column uses
the *decision-study worker* statuses: 45/45 Expected, 27/45 CVaR, and
40/45 MeanCVaR (different from the 810-run timed panel's 39, 21, 30
for Path-exp). Their largest final gaps are respectively 0.0010, 0.0944,
and 0.0441. Risk comparisons with uncertified runs describe feasible
incumbents, not known SAA optimal solutions.

**Do not merge campaign IDs.** The later consolidated CSV for `n=400`
contains Combinatorial method rows whose `worker_id/task_id` values
point to different Path-exp/Root worker files in its `workers/` directory.
A row-by-row merge of that consolidated CSV with those worker files
would create false placements. The reproduction script instead uses
only matched *per-worker* CSV/JSON/solution triplets for Path-exp, and
crosschecks their split files against the original manifest. The
worker outcomes in this decision study do not always equal the
similarly identified runs in the original 810-run panel; the study
therefore reports its own certification and does not replace or
rewrite Table 2 or Figure 1. Neither a matching `case_id` across n
nor matching test IDs imply nested training samples: the training
splits are independently generated.

The original `new_instances/20x20/` and `20x20_reburn/` scenario graphs
and ignition records remain absent from accessible implementation
history. Thus the saved evaluation metrics can be checked against
worker CSV/JSON and the evaluator implementation, but scenario-level
losses cannot be recomputed from graphs here. Paired fixed-placement
transfer to Reburn requires the paired graph inputs, matching ignition
and weight conventions, and evaluation of the **same** selected cells
on both representations. The separately optimized Reburn result rows
cannot provide this estimate. No transfer value or claim is reported.
