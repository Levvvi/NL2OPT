# Claim Registry

This registry separates documented evidence from claims that may be made
externally. It is deliberately conservative: no NL4Opt or IndustryOR outcome
belongs in public-facing copy until a complete run and its deterministic
Chinese translation audit have been rendered by `nl2opt.eval.bench_report`.

| Claim | Scope | Provenance | Publication rule |
| --- | --- | --- | --- |
| Self-built 20-case result: 20/20 end-to-end | The repository's four supported Chinese problem families only | `outputs/deepseek_extractor_eval/all/summary.json`, `docs/deepseek_final_20_eval_report.md` | May be stated only as a self-built evaluation; it is not evidence for a public benchmark. |
| Public benchmark result (pending audited run) | NL4Opt/IndustryOR English and Chinese tracks | Result template: `reports/bench_report.md`, generated from `results.csv`, `run_manifest.json`, and `translation_audit.csv` | Do not replace this template with a rate, count, comparison, or improvement claim until every sampled audit row is terminal and the renderer has produced the report from the real run. |
| Dataset provenance | Pinned NL4Opt and IndustryOR source inputs | `eval/datasets/manifest.json` records revision, URL, hash, license, and expected count | Cite the manifest URL/revision with the dataset name; do not imply a source paper's reported score is comparable without matching protocol. |

## Public-result template

Use only after the publication gate succeeds:

> On the manifest-pinned NL4Opt/IndustryOR benchmark, under the configuration
> recorded in the audited run manifest, NL2OPT achieved **[strict 1e-6 rate]**
> (**[successes]/[attempts]**) on **[track]**. The corresponding 1e-4
> sensitivity, per-repetition Wilson intervals, failure distribution, and
> checker-retry rows are in `reports/bench_report.md`.

The placeholders above are intentionally not populated. The existing
self-built 20/20 result remains a separately scoped claim.
