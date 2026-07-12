# Audited public benchmark artifacts

This package is derived from the completed, manifest-pinned NL4Opt/IndustryOR
retry-off and independent retry-on benchmark runs. The formal tables,
limitations, and protocol interpretation remain in [`../bench_report.md`](../bench_report.md).

## Reproduction

Regenerate this directory from the local completed runs with:

```bash
python -m nl2opt.eval.publication_export \
  --retry-off eval/results/public-20260710-off \
  --retry-on eval/results/public-20260711-on-rerun \
  --output-dir reports/artifacts
```

`manifest.json` records run-level counts and SHA-256 digests for every exported
source artifact. Each run directory contains the sanitized result CSV, completed
run manifest, and terminal translation audit.

## Sanitization and failure provenance

Absolute local failure paths are replaced by stable `failures/<filename>`
archive references. The complete failure JSON archives remain local because
they can contain implementation and machine context; the published result CSV
retains failure categories and stable archive references for traceability.
Credentials and local Windows user paths are rejected before any package file
is written.
