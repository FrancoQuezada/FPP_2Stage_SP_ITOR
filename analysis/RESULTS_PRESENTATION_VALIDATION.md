# Presentation validation, reduced new20x20 study

The current manuscript uses only the 810-run reduced `new20x20` panel.
Run `python3 analysis/reproduce_results.py --implementation ../implementation`
from the manuscript checkout, then compile `main.tex` with `latexmk`.
Tables are generated with explicit denominators (45, 15 or 5) and
full-precision machine-readable summaries are in
`tables/new20_statistics.csv`. The cumulative certification profile is
editable PGFPlots in `figs/new20_certified.tex`. The preferred-method
certification-coverage audit is generated to
`tables/new20_selection_audit.csv` and its 27-cell display table.

All run-level numerical assertions, file hashes, scope limits and
unresolved OOS and Reburn prerequisites are documented in
`RESULTS_VALIDATION.md`. The formerly separate scenario-order and
Sub20 experiments no longer appear in the manuscript.
