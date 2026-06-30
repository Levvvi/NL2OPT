# NL2OPT Project Status

## Current Status

P3 is feature-complete as an interview MVP.

The project demonstrates a complete Chinese natural-language optimization workflow:

```text
Chinese prompt -> Router -> DeepSeek Extractor -> ProblemSpec -> OR-Tools -> Checker -> Report / Streamlit demo
```

## Completed

- Four supported problem types:
  - production
  - assignment
  - jobshop
  - vrp / CVRP
- DeepSeek v3 extractor with `deepseek-v4-flash`.
- `prompt_version=v3`.
- Deterministic normalizer for common LLM field aliases.
- Pydantic schema validation with forbidden extra fields.
- OR-Tools solver templates:
  - linear solver for production
  - linear solver for assignment
  - CP-SAT for jobshop
  - RoutingModel for VRP/CVRP
- Independent checkers for all four problem types.
- `case_quality` gate for easy, medium, hard, and all cases.
- 20-case live DeepSeek eval.
- Streamlit local demo with three stable cases.
- README, architecture, eval, demo, interview, and release docs.

## Final Metrics

| difficulty | total | end_to_end_success | spec_success | checker_success | objective_match | failure_breakdown |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| easy | 8 | 8/8 | 8/8 | 8/8 | 8/8 | `{}` |
| medium | 8 | 8/8 | 8/8 | 8/8 | 8/8 | `{}` |
| hard | 4 | 4/4 | 4/4 | 4/4 | 4/4 | `{}` |
| all | 20 | 20/20 | 20/20 | 20/20 | 20/20 | `{}` |

Final live artifacts:

- `outputs/deepseek_extractor_eval/all/summary.json`
- `docs/deepseek_final_20_eval_report.md`
- `docs/deepseek_final_20_failure_analysis.md`

## Run Commands

Install and test:

```bash
python -m pip install -e ".[dev]"
pytest -q -o cache_dir=.tmp_pytest_cache
```

Run quality and demos:

```bash
python -m nl2opt.eval.case_quality --difficulty all
python examples/run_mock_nl_basic.py --prompt-version v3
python examples/run_all_basic.py
```

Check DeepSeek environment without printing secrets:

```bash
python -m nl2opt.config
python -m nl2opt.eval.extractor_eval --check-env
```

Run Streamlit local demo:

```bash
streamlit run src/nl2opt/ui/streamlit_app.py
```

## Known Boundaries

- Four small-scale problem types only.
- Not an arbitrary optimization modeling system.
- Not a public code execution service.
- No industrial-grade sandbox.
- No login, database, cloud deployment, or multi-user permission system.
- Custom inputs may fail if required fields are missing or outside the supported schema.

## Recommended Next Use

- Record a short demo video or GIF.
- Add GitHub screenshots after launching the Streamlit app locally.
- Use one of the resume bullets in `docs/interview_notes.md`.
- Keep final eval metrics tied to real DeepSeek live artifacts, not mock runs.
