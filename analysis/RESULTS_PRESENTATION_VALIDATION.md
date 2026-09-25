# Presentation validation, reduced new20x20 study

The current manuscript uses only the 810-run reduced `new20x20` panel.
Run `python3 analysis/reproduce_results.py --implementation ../implementation`
from the manuscript checkout, then compile `main.tex` with `latexmk`.
The main performance table reports certification percentages with
denominator 45 and omits time SD. Budget-conditioned details are
discussed in two results paragraphs; full-precision summaries,
including 15-run marginals and five-run joint blocks, are in
`tables/new20_statistics.csv`. The cumulative certification profile is
editable three-panel vertical PGFPlots in `figs/new20_certified.tex`.
The preferred-method certification audit is generated to
`tables/new20_selection_audit.csv` for provenance; it is not displayed
as an OOS result table.

All run-level numerical assertions, file hashes, scope limits and
unresolved OOS and Reburn prerequisites are documented in
`RESULTS_VALIDATION.md`. The formerly separate scenario-order and
Sub20 experiments no longer appear in the manuscript.

The revised manuscript compiles to 12 pages. Table 2 on page 9 and
the enlarged three-panel Figure 1 on page 10 were rendered and
visually inspected. The source audit and OOS limitation on pages
10--11 are legible, with no missing cross-references or new layout
warnings. The existing front-matter overfull-box warning at
`\maketitle` remains visible only in the LaTeX log and does not
clip the inspected front page. The PDF contains no Tables 3--5.
