# Combinatorial scenario-order sensitivity

## Scope and provenance

Manuscript baseline: `3c946c8988ec0c8e83ed86bc726a7c3596b01ed7`.
Implementation snapshot: `1a00d6b725d4b29d4e5da2e158efabe723c40d3b`.

The comparison reads only `new20x20` Combinatorial B&B runs with 100 or
200 training scenarios from:

- ascending/legacy campaign:
  `cpp_cplex_firebreak/Results_server/batch/fpp_new_instances_scaling/`;
- descending campaign:
  `cpp_cplex_firebreak/Results_server/batch/fpp_new_instances_scaling_new20x20_100_200/`.

The source SHA256 values are:

- ascending CSV: `eb619b3bd3a6385b4c691d7ff15d6fe5f490e222e53ea28378689da347e2bfbf`;
- ascending manifest: `5b05c80e11ac13cf88166905c32867e6b3c8199ec0f1b085112eed7a3976ce16`;
- descending CSV: `7b5a20e6102a6259d8c8b2b3b055391baa278916e6d7c4da5b8981104e349da3`;
- descending manifest: `c2efde4c59c04fdd4be316b31f8d8977e49ca7e3a13f4cb2802a5ee13008fb4b`.

The legacy CSV, manifest, and JSON files do not record a scenario-order
field. Its ascending label is therefore inferred from the base method name,
the recoverable implementation default, the manifest generator, and the
README statement that `eta-asc` preserves previous behavior. The exact
execution commit cannot be reconstructed. The descending label is explicit
in its method names, CSV, manifest, and JSON files.

## Pairing and checks

`analysis/reproduce_combinatorial_order.py` constructs pairs by instance,
case, alpha, training count, and objective family. It verifies:

- 90 unique rows, 90 manifest entries, and 90 worker JSON files per order;
- three objectives, two training sizes, three alpha values, and five cases;
- 90 complete scientific-key pairs and no duplicate task IDs within a campaign;
- byte-identical training and test split files in every pair;
- exact agreement of the split IDs recorded in CSV, manifest, JSON, and files;
- common graph metadata, seeds, risk settings, 1,000 test scenarios, time limit,
  requested gap, thread count, lifting, sampling, initial cuts, and fractional
  separation;
- validation status `pass` in all 180 JSON files and agreement of status, gap,
  and runtime with the consolidated CSV;
- consistency of `Optimal` with final gap at most 0.001;
- exclusion of every 400- and 600-scenario row.

A resolved run has `solver_status == Optimal` and `mip_gap <= 0.001`.
Mean and maximum gaps use all runs and are converted to percent once. Mean
time and sample SD use all recorded runtimes, including time-limit overruns;
the SD denominator is N - 1.

## Generated outputs

- `tables/combinatorial_order_main.tex`: 30 runs per objective and order;
- `tables/combinatorial_order_by_n.tex`: 15 runs per objective, order, and n;
- `tables/combinatorial_order_by_alpha.tex`: 10 runs per objective, order,
  and alpha;
- `tables/combinatorial_order_paired.tex`: paired certification outcomes;
- `analysis/combinatorial_order_statistics.csv`: full-precision summaries;
- `analysis/combinatorial_order_pairing.csv`: pair keys, split hashes,
  provenance, statuses, gaps, times, and outcomes;
- `analysis/combinatorial_order_pair_summary.csv`: paired certification and
  conditional jointly-solved timing summaries.

The headline certification counts (ascending, descending) are Expected
(28/30, 29/30), CVaR (16/30, 15/30), and Mean-CVaR (21/30, 25/30).

## Limitations

The campaign timestamps differ: June 25--26, 2026, for ascending and July
3--4, 2026, for descending. Hardware and effective solver version are absent.
Consequently, runtime differences are descriptive and cannot be attributed
exclusively to scenario order. The ascending provenance is inferred rather
than recorded. Results_server runs at 400 and 600 scenarios are excluded until
their provenance discrepancy is resolved. The experiment measures solver
certification and final gaps, not out-of-sample placement quality.

## Reproduction

From the manuscript checkout, with the implementation checkout at the sibling
path shown below:

```sh
python analysis/reproduce_combinatorial_order.py --implementation ../implementation
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

## Final verification

An independent raw-CSV calculation using Python's sample standard deviation
agrees with every displayed aggregate, training-size, budget, and paired
outcome. It also confirms all 90 split-file pairs byte for byte and finds no
CSV/JSON mismatch. Two consecutive runs of the reproduction script produce
byte-identical versions of all seven generated outputs.

The complete manuscript compiles to a 22-page PDF. Pages 1, 6, 9, 14, 15, 21,
and 22 were rendered and visually inspected, including the abstract, algorithm
description, provenance text, both main order tables, both appendix tables,
and references. The tables are legible and remain inside the text block. There
are no unresolved citations or cross-references and no new box warning. The
CAS front matter retains the pre-existing 117.0831 pt overfull-box warning and
three empty-anchor warnings at `maketitle`; no visible clipping was found.
