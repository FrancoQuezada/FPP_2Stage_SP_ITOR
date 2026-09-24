# Results presentation revision

## Scope and sources

Manuscript baseline: `d5033af2b8ed5d2eb52b7d0c556daf4334a7f9cc`.
Implementation snapshot: `1a00d6b725d4b29d4e5da2e158efabe723c40d3b`.

The new20 calculations use exactly the 810 `instance_id=new20x20` rows in
`cpp_cplex_firebreak/results/batch/fpp_new20x20_scaling/batch_results_partial_resumen.csv`,
restricted to the first 108 uniquely named fields. Source SHA256:
`aef99697e1ff050c7481a2d3b3b5c3c6672e8cea8208c176cf940c2f5bce2a02`.
Configuration and partitions are verified against the campaign's
`manifests/full_task_manifest.csv` and split files. The preflight remains
an input to the existing graph-classification checks.

No new20 runs at 600 or 800 scenarios, Reburn rows, or Results_server campaigns
enter these summaries. The existing independent Sub20 table retains its
original data and has only its denominators made explicit as counts / 60.

## Outputs and definitions

- `tables/new20_solved.tex`: certified counts / 15 by training size and / 45 overall.
- `tables/new20_gaps_times.tex`: counts / 45, mean and maximum final gap (%),
  mean recorded time and sample standard deviation (seconds), all 45 runs.
- `tables/new20_alpha_solved.tex`: counts / 15 for each budget fraction.
- `tables/new20_alpha_{Expected,CVaR,MeanCVaR}.tex`: complete statistics by budget,
  in Appendix A; 15 runs in every row.
- `tables/new20_statistics.csv`: 288 full-precision summaries, including the
  five-run alpha/training-size blocks used to check aggregate trends.
- `figs/new20_certified.tex`: regenerated without changes to the data or the
  common-denominator certification curves.

A certified run requires both `Optimal` status and final gap <= 0.001.
All positive final gaps, including those of certified runs, are retained.
All recorded times, including nominal-limit overruns, are retained.
Standard deviations have denominator N - 1. Observed means under the stopping
rule are not estimates of unrestricted time to certification.

## Reproduction and checks

From the manuscript checkout, with the implementation checkout at the path below:

```sh
python analysis/reproduce_results.py --implementation ../implementation
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

Script assertions verify source/header shape, unique task IDs, manifest matching,
810 reduced rows, 45 rows per objective/method, 15 per objective/method/size
and objective/method/alpha, five rows per alpha/size block, common risk settings,
budgets, limits and partition contents, and exact status/gap consistency.

An independent calculation from the raw 108-field prefix, using explicit sums
and the sample-variance formula, agrees with all 288 output groups (relative
tolerance 1e-12, absolute tolerance 1e-10). Two consecutive regeneration runs
produce byte-identical new20 tables and statistics CSV. There are 424 certified
runs, including 298 with positive final gaps, and 386 recorded time overruns.
For example, Expected/Combinatorial over all 45 runs yields 43/45 certified,
mean gap 0.1751690667%, maximum gap 4.000649%, mean time 212.4496741 s and
sample SD 427.0617401 s, displayed as 0.18%, 4.00%, 212.4 s and 427.1 s.

Within-size checks support the declining certification counts for decomposition
methods as alpha increases, but do not support a universal time or gap trend.
The expected-loss SAA improvement comes from n=400; its n=100 times are
non-monotone. Mean-CVaR SAA gaps and combinatorial maximum gaps are also
non-monotone. The Results section reports these exceptions explicitly.

The 17-page PDF compiles successfully. Results tables (pages 10--13), appendix
tables (pages 15--17), and the front page were rendered and visually inspected.
No table overflow, missing citation, or unresolved cross-reference was found.
The CAS front matter retains one 117.0831 pt overfull-box warning and three
empty-anchor warnings at maketitle. An independent compilation of the baseline
commit produces exactly the same warnings; the inspected front page has no
visible clipping or overlap. No new layout warnings were introduced.

## Remaining limitations

The original new20 suffix remains malformed, and placement quality and paired
Reburn evaluation remain outside this revision. Final MIP gaps describe the
recorded optimization models, including extensive-model incumbent anomalies;
they are not evaluated losses of the placements. Time-limit censoring and
recorded overruns prevent interpreting mean observed times as unrestricted
solution times. The budget associations do not identify a causal mechanism.
