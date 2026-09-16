# Portfolio evidence

Generate with `uv run python scripts/export_portfolio_evidence.py` after a locked environment install. This command does not call a language model.

- `evidence.json` contains one actual production solver run, two synthetic result mutations checked by the real checker, and one synthetic missing-field gate rejection. Each case distinguishes solver execution, checker execution, and deliberate fault injection. The Chinese prompt is a human paraphrase of the checked-in JSON specimen, not evidence of fresh model extraction.
- `failure-index.json` contains every failed row from the two published benchmark CSVs (972 retry-off and 987 retry-on), keeping a whitelisted set of existing fields. Records have stable composite identifiers. They do not link to unpublished full failure archives.
- Source metadata includes the base Git commit, modified-tree flag, source-file hashes, lock hash, interpreter and key package versions. A modified-tree hash is not represented as a committed release.

Production success: A=40, B=20; labor=100; material=80; objective=2200. Fault injection changes quantities to A=41, B=20 (labor=102, material=81), or A=0.5, B=0 (integer constraint violation). The missing-field example deliberately marks material.capacity unresolved; its existing value is a placeholder and must not be used.

The checker operates on the extracted model. It cannot independently establish faithful interpretation of all original natural-language requirements or certify global optimality. These demonstrations are separate from historical model benchmark scores.

The separate `live-smoke-request.json`, `live-smoke-first-attempt.json` and `live-smoke.json` preserve the 2026-09-16 real model request, initial metadata-gate rejection, and successful retry after the explicit v3/server-metadata fix. The successful response records the provider-returned model identifier, elapsed time and token counts. These files are not produced by the offline exporter, and they do not constitute a new 20-case evaluation.

`validation.json` records the four full successful test runs with log hashes and before/final file snapshots; Python 3.11 preceded the last test-budget and optional example-CLI adjustment, while Python 3.12 validates the final files twice. `environments.json` records both installed environments. Neither substitutes for remote CI or deployed-service checks.
