# Claim Registry

This registry separates documented evidence from claims that may be made
externally. It is deliberately conservative: NL4Opt or IndustryOR outcomes are
publishable only from complete runs with terminal deterministic Chinese
translation audits rendered by `nl2opt.eval.bench_report`.

| Claim | Scope | Provenance | Publication rule |
| --- | --- | --- | --- |
| Self-built 20-case result: 20/20 end-to-end | The repository's four supported Chinese problem families only | `outputs/deepseek_extractor_eval/all/summary.json`, `docs/deepseek_final_20_eval_report.md` | May be stated only as a self-built evaluation; it is not evidence for a public benchmark. |
| Audited public benchmark, checker retry off: 1,098/2,070 strict and loose passes (53.0%) | Manifest-pinned NL4Opt/IndustryOR English and Chinese tracks, three repetitions | `reports/bench_report.md`; sanitized inputs and hashes in `reports/artifacts/public-20260710-off/` and `reports/artifacts/manifest.json` | State with the denominator and audited scope. The 105 translation audits contain 93 approved and 12 rejected decisions. Do not generalize beyond this protocol. |
| Independent checker-retry-on rerun: 1,083/2,070 strict and loose passes (52.3%), with 412 checker retries | Same pinned datasets and matrix, separate completed run | `reports/bench_report.md`; sanitized inputs and hashes in `reports/artifacts/public-20260711-on-rerun/` and `reports/artifacts/manifest.json` | The result is 0.7 percentage points lower than retry-off. It is descriptive, not a paired causal estimate; do not claim checker retry improved accuracy. The 105 audits contain 95 approved and 10 rejected decisions. |
| Dataset provenance | Pinned NL4Opt and IndustryOR source inputs | `eval/datasets/manifest.json` records revision, URL, hash, license, and expected count | Cite the manifest URL/revision with the dataset name; do not imply a source paper's reported score is comparable without matching protocol. |

## Approved public-result wording

Use with the formal report and artifact package linked:

> On the manifest-pinned NL4Opt/IndustryOR benchmark, under the configuration
> recorded in the audited retry-off run manifest, NL2OPT achieved **53.0%**
> strict 1e-6 accuracy (**1,098/2,070**); the 1e-4 result was identical. An
> independent retry-on rerun achieved **52.3%** (**1,083/2,070**) and recorded
> 412 checker retries. This 0.7 percentage point difference is not a paired
> causal estimate and does not establish an accuracy improvement from retry.

Per-track results, Wilson intervals, failure distributions, audit decisions,
and limitations are in `reports/bench_report.md`; sanitized artifacts and
SHA-256 values are in `reports/artifacts/`. The existing self-built 20/20 result
remains a separately scoped claim.

## Portfolio release clarification (2026-09-16)

- Describe NL2OPT as a **controlled optimization-modeling workflow**. The Router is rule based; it is not a general autonomous tool loop.
- The first gate validates structured fields, types, implemented rules, and unresolved required fields. The second gate independently recomputes constraints and the objective against that structured model. Neither proves complete semantic fidelity to the original prompt, and a checker pass is not a separate proof of global optimality.
- Production checker evidence may claim integer/nonnegative/finite quantity checks, rejection of unknown product names, resource capacity, and objective consistency only with the source version and regression evidence in `docs/nl2opt_audit.md`.
- A missing product quantity defaults to zero. Do not claim the production checker enforces complete product coverage.
- The public benchmark denominator is **345 distinct source items × 2 language tracks × 3 repetitions = 2,070 attempts per run**, not 2,070 distinct optimization problems.
- The self-built live 20/20 result is dated **2026-06-30**. A current `case_quality` result of 20/20 is a static dataset check, not a repeat of that live evaluation. Unit/integration test counts are another separate measure.
- `reports/portfolio/evidence.json` contains fresh deterministic solver evidence and clearly labeled synthetic faults. Its Chinese prompt is a human paraphrase; that deterministic artifact does not imply a live model call. The separate 2026-09-16 single-case live smoke is linked from `docs/nl2opt_audit.md` and does not replace historical evaluations.
- `reports/portfolio/failure-index.json` derives from published CSV fields. It supports failure-stage screening, not access to every historical full failure archive.
- Local test results do not establish that the newly added GitHub Actions workflow has run remotely, nor that the optional live service has been deployed publicly.
