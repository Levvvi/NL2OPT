# Demo Script

## Recommended Demo Order

1. Show README and final eval table.
2. Start the Streamlit demo and point out final live eval `20/20` in the sidebar.
3. Run the production demo and show `ProblemSpec JSON`, objective value, and checker report.
4. Run the jobshop demo and show makespan plus precedence / machine-overlap checker output.
5. Run the VRP demo and show route solution JSON plus capacity / distance checker output.
6. Close with project boundaries: four small problem families, not an arbitrary optimization platform.

## Commands

Install and test:

```bash
python -m pip install -e ".[dev]"
pytest
```

Check case quality:

```bash
python -m nl2opt.eval.case_quality --difficulty all
```

Run basic local demos:

```bash
python examples/run_all_basic.py
```

Run Streamlit local demo:

```bash
streamlit run src/nl2opt/ui/streamlit_app.py
```

Run final live eval only when needed:

```bash
python -m nl2opt.eval.extractor_eval --prompt-version v3 --difficulty all
```

## Streamlit Demo Flow

1. Open the page and show the sidebar:
   - provider: DeepSeek
   - model: `deepseek-v4-flash`
   - prompt_version: `v3`
   - mock: `false`
   - final live eval: `20/20`
   - API key status: `available` / `missing`, never the key value
2. Select `production`, click `Run`, and show:
   - input Chinese prompt
   - `ProblemSpec JSON`
   - `Solver Result`
   - `Checker Report`
   - deterministic Chinese explanation
3. Select `jobshop`, click `Run`, and focus on:
   - operations
   - makespan
   - checker validation for precedence and machine non-overlap
4. Select `vrp`, click `Run`, and focus on:
   - routes
   - total distance
   - checker validation for customer coverage, capacity, and route distance
5. If time permits, paste a custom Chinese problem. Explain that this calls the real DeepSeek API.

## Command-line Backup Cases

### 1. Production

Command:

```bash
python -m nl2opt.pipeline examples/specs/production_basic.json --output-dir outputs/demo/production_basic
```

Show:

- `examples/specs/production_basic.json`
- generated `outputs/demo/production_basic/solution.json`
- generated `outputs/demo/production_basic/pipeline_report.json`
- checker passed and objective value `2200`

Talk track:

> This is the simplest example of schema -> template -> OR-Tools -> checker. The checker recomputes resource usage and objective value.

### 2. Jobshop

Command:

```bash
python -m nl2opt.pipeline examples/specs/jobshop_basic.json --output-dir outputs/demo/jobshop_basic
```

Show:

- job operations in the spec
- CP-SAT solution operations
- makespan `7`
- checker verifies precedence and machine non-overlap

Talk track:

> This case demonstrates why a CP-SAT template is more appropriate than asking an LLM to hand-write scheduling code.

### 3. VRP

Command:

```bash
python -m nl2opt.pipeline examples/specs/vrp_basic.json --output-dir outputs/demo/vrp_basic
```

Show:

- depot, customers, demands, distance matrix
- route list in `solution.json`
- total distance `44`
- checker verifies customer coverage, capacity, and route distance

Talk track:

> The checker is useful here because route order and vehicle assignment can vary, but feasibility and total distance still have to be correct.

## DeepSeek Live Artifact To Show

Open one case directory, for example:

```text
outputs/deepseek_extractor_eval/all/extractor_production_01/
```

Show:

- `raw_response.txt`
- `parsed_spec.json`
- `pipeline_report.json`
- `extractor_result.json`

Do not show or print environment variables or API keys.

## If Something Fails During A Live Demo

Do not rerun blindly. Explain the failure stage:

- Router mismatch: classification keyword or problem wording issue.
- Schema validation error: LLM output did not match required schema.
- Missing required fields: input problem did not provide enough numeric data.
- Checker failed: extracted model or solver result violates constraints.
- Objective mismatch: feasible result exists but objective value differs from expected benchmark.
- API error: key, model, network, quota, or provider issue.

Then open the relevant `failure.json`, `extractor_result.json`, or `pipeline_report.json`. This is a strength of the project: failures are classified rather than hidden.
