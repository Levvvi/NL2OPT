# Release Checklist

## Core Validation

- [x] `python -m pip install -e ".[dev]"`
- [x] `pytest -q -o cache_dir=.tmp_pytest_cache`
- [x] `python -m nl2opt.eval.case_quality --difficulty all`
- [x] `python examples/run_mock_nl_basic.py --prompt-version v3`
- [x] `python examples/run_all_basic.py`
- [x] `python -c "import nl2opt.ui.streamlit_app; print('STREAMLIT_APP_IMPORT_OK')"`
- [x] Streamlit headless health check returned HTTP 200 during P3-T18 validation.

## Eval Validation

- [x] Final 20 live eval summary exists at `outputs/deepseek_extractor_eval/all/summary.json`.
- [x] `provider=deepseek`
- [x] `model=deepseek-v4-flash`
- [x] `mock=false`
- [x] `prompt_version=v3`
- [x] `end_to_end_success=20/20`
- [x] `spec_success=20/20`
- [x] `checker_success=20/20`
- [x] `objective_match=20/20`
- [x] `failure_breakdown={}`

## Documentation Validation

- [x] README complete.
- [x] Architecture doc complete: `docs/architecture.md`.
- [x] Eval report complete: `docs/eval_report.md`.
- [x] Demo script complete: `docs/demo_script.md`.
- [x] Interview notes complete: `docs/interview_notes.md`.
- [x] Final 20 live report complete: `docs/deepseek_final_20_eval_report.md`.
- [x] Final 20 failure analysis complete: `docs/deepseek_final_20_failure_analysis.md`.

## Security Validation

- [x] No real API key committed.
- [x] `.env` and `.env.local` are ignored.
- [x] `.streamlit/secrets.toml` is ignored.
- [x] No Authorization header saved in project docs or source files.
- [x] No key prefix, suffix, length, or hash is printed by diagnostics.

## Scope Validation

- [x] No claim of industrial production readiness.
- [x] No claim of supporting arbitrary optimization problems.
- [x] No claim of public sandbox safety.
- [x] Streamlit is documented as a local interview demo, not a public production service.

## Release Recommendation

P3 is ready for GitHub portfolio use and interview demonstration after a final human review of README wording and repository visibility.
