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
