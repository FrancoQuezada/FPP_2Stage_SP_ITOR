# Computational-study evidence and reproduction

Manuscript revision uses implementation `main` commit
`1a00d6b725d4b29d4e5da2e158efabe723c40d3b`. All quantitative
manuscript results concern the reduced `new20x20` campaign. From a
manuscript checkout alongside the implementation checkout:

```bash
python3 analysis/reproduce_results.py --implementation ../implementation
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

The source is `cpp_cplex_firebreak/results/batch/fpp_new20x20_scaling/`
under the implementation checkout. The solver results are in
`batch_results_partial_resumen.csv` (SHA256
`aef99697e1ff050c7481a2d3b3b5c3c6672e8cea8208c176cf940c2f5bce2a02`),
with configuration and partitions in `manifests/full_task_manifest.csv`
and `splits/`. The script verifies the 1,329 result rows (810 reduced,
519 excluded Reburn), the 2,160-row original manifest, all unique task
IDs, matching manifest fields, exactly 45 rows per objective/method,
15 per objective/method/size and budget, and five per
objective/method/size/budget. It checks training split sizes,
9001--10000 fixed test IDs, consistent matched-method splits, the
1,800-second limit, one thread, requested gap 0.001, beta 0.9 and
lambda 0.5. It checks status/gap consistency and the 424 certified and
386 feasible reduced rows. The 60 matching reduced/Reburn training
splits differ, though test IDs agree.

The six displayed configurations map to these exact manifest labels
for each objective:

| Displayed | Expected | CVaR | MeanCVaR |
| --- | --- | --- | --- |
| Extensive SAA | `FPP-SAA` | `FPP-SAA-CVaR` | `FPP-SAA-MeanCVaR` |
| LP B&B + Root | `FPP-Branch-Benders-RootCuts` | `FPP-Branch-Benders-CVaR-RootCuts` | `FPP-Branch-Benders-MeanCVaR-RootCuts` |
| LP B&B + Standard | `FPP-Branch-Benders-LLBI-RootCuts` | `FPP-Branch-Benders-CVaR-LLBI-RootCuts` | `FPP-Branch-Benders-MeanCVaR-LLBI-RootCuts` |
| LP B&B + Coverage-exp | `FPP-Branch-Benders-ProjectedCoverageLLBI-exp-RootCuts` | `FPP-Branch-Benders-CVaR-ProjectedCoverageLLBI-exp-RootCuts` | `FPP-Branch-Benders-MeanCVaR-ProjectedCoverageLLBI-exp-RootCuts` |
| LP B&B + Path-exp | `FPP-Branch-Benders-ProjectedPathLLBI-exp-RootCuts` | `FPP-Branch-Benders-CVaR-ProjectedPathLLBI-exp-RootCuts` | `FPP-Branch-Benders-MeanCVaR-ProjectedPathLLBI-exp-RootCuts` |
| Combinatorial B&B | `FPP-Branch-Benders-Combinatorial` | `FPP-Branch-Benders-Combinatorial-CVaR` | `FPP-Branch-Benders-Combinatorial-MeanCVaR` |

| Manuscript result | Direct source and inclusion | Definition |
| --- | --- | --- |
| Main 18-row performance table, size and budget certification tables, appendix budget tables, `tables/new20_statistics.csv` | 810 reduced rows, first 108 uniquely named CSV fields; manifest `instance_id=new20x20`, `n=100,200,400` | Certified iff `solver_status=Optimal` and final `mip_gap <= 0.001`; counts /45, /15 or /5; arithmetic mean and maximum of 100 times final relative MIP gap, observed solver-time mean and sample SD. Every run enters each summary. |
| `figs/new20_certified.tex` | Same 810 run-level records | Cumulative certified count by observed time /45 per objective and method, unresolved runs remain in denominator; not an uncensored performance profile. |
| `tables/new20_selection_coverage.tex`, `tables/new20_selection_audit.csv` | Same 810 rows, grouped into 135 six-method problems keyed by budget, size, case and objective | Preferred Expected = Combinatorial; preferred CVaR and MeanCVaR = Path-exp. If preferred is uncertified, choose a certified identical-sample method in published table order. If none is certified, mark unresolved. The CSV names the selected task ID and best available final gap; it does **not** assert recovery of its firebreak set. |

The 132-heading consolidated result file has ten blank headings and a
malformed, partly truncated suffix beginning at `selected_firebreaks`.
Even where the initial entries of this suffix look like cell IDs, their
completeness and evaluation-field correspondence cannot be verified
against the original worker artifacts. The script never uses the suffix.
The pre-suffix `test_cvar_burned_area` field is an aggregate, not a
scenario-level vector sufficient to reconstruct the requested OOS
risk functionals for exact selected placements. The original target
worker CSVs, JSONs and solution files referenced by the manifest are
not committed. Searches of the accessible history of this campaign
found no intact copy. The later `Results_server` campaign does commit
intact worker outputs, but it has 540 rows, different training sizes
(400 and 600) and nine methods per objective; it cannot substitute
for the target 810-run experimental design.

The original `new_instances/20x20/` and `20x20_reburn/` scenario inputs
and ignition records are absent from the implementation repository.
Neither cell-ID mapping, ignition matching, weight equality nor graph
arc inclusion can therefore be checked. No evaluation-only Reburn
campaign was executed: there are neither verified original placements
nor source graphs to evaluate. The 519 Reburn optimization rows are
excluded from all numerical conclusions. No independently optimized
Reburn solution is used. No OOS stability or paired-fidelity figure can
be generated honestly from the committed target data.

The optimization-quality prerequisite for OOS sampling conclusions
also fails unevenly. Out of 45 sampled problems per objective, the
preferred method is certified for 43 Expected, 21 CVaR and 30
MeanCVaR; Expected has two certified extensive-SAA substitutions.
For CVaR, 24 problems have no certified method (one at n=100,
alpha=0.02; three at n=200, alpha=0.02; all five at n=400,
alpha=0.02; all fifteen at alpha=0.03). For MeanCVaR, 15 have no
certified method (one at n=100, alpha=0.03; four at n=200,
alpha=0.03; all five at n=400 for each of alpha=0.02 and 0.03).
Restricting OOS summaries to certifiable cases would create a
condition-dependent sample. The individually generated training
samples at different n are not nested; case IDs cannot be assumed to
pair across n.

To complete the OOS stability and graph-fidelity analyses, restore intact target solution and
scenario graph artifacts; validate original IDs, ignitions, weights,
reduced/Reburn graph pairing and all 1,000 matched test IDs; resolve
uncertified risk-model problems to the requested tolerance or state a
predefined sensitivity design; then evaluate the exact selected
reduced-graph placements on both representations without optimizing
Reburn. Store scenario-level losses and no-treatment baselines so
Expected, empirical CVaR and MeanCVaR, Jaccard similarity, and raw and
normalized fixed-placement transfer can be reproduced.
