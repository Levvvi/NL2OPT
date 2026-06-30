# NL2OPT: 中文自然语言到优化模型的 Agent

NL2OPT 是一个面试级 MVP，用来验证“中文业务问题 -> 结构化优化模型 -> OR-Tools 求解 -> 独立校验 -> 评测报告”的闭环。用户可以输入中文生产计划、任务分配、作业车间排产或车辆路径配送问题，系统先用 Router 判断问题类型，再用 DeepSeek 抽取结构化 `ProblemSpec`。求解阶段不让 LLM 自由写 OR-Tools 代码，而是使用受控 Jinja2 模板生成模型代码并本地运行。求解结果会经过独立 checker 复核约束和目标值，并输出 pipeline/eval 报告和确定性中文解释。

## 核心亮点

- **Schema-first**：先把中文问题抽取为 Pydantic `ProblemSpec`，再进入求解，减少不可控字段和幻觉。
- **Template-based OR-Tools codegen**：使用固定模板生成 OR-Tools 代码，而不是让 LLM 直接自由生成求解代码。
- **Independent checker**：checker 独立重新计算资源使用、任务分配、makespan、路径距离等，不直接信任 solver 输出。
- **20-case live eval**：自建 20 题中文评测集，真实 DeepSeek v3 live eval 端到端通过率 **20/20**。

## 支持的问题类型

| problem_type | 中文名称 | 求解器 |
| --- | --- | --- |
| `production` | 生产计划 | OR-Tools linear solver |
| `assignment` | 任务分配 | OR-Tools linear solver |
| `jobshop` | 作业车间排产 | OR-Tools CP-SAT |
| `vrp` | 车辆路径配送 CVRP | OR-Tools RoutingModel |

## 系统架构

```mermaid
flowchart LR
    A["中文问题"] --> B["Router<br/>规则分类"]
    B --> C["Extractor<br/>DeepSeek JSON output"]
    C --> D["Normalizer<br/>字段标准化"]
    D --> E["ProblemSpec<br/>Pydantic schema"]
    E --> F["Template Renderer<br/>Jinja2"]
    F --> G["OR-Tools Solver<br/>generated_model.py"]
    G --> H["SolverResult<br/>solution.json"]
    H --> I["Checker<br/>独立约束复核"]
    I --> J["Pipeline / Eval Report"]
```

更多设计说明见 [docs/architecture.md](docs/architecture.md)。

## 快速开始

安装：

```bash
python -m pip install -e ".[dev]"
```

配置 DeepSeek 环境变量，或在项目根目录创建未提交的 `.env.local`。不要把 API key 写入 Git、README、聊天记录、日志或报告。

```bash
export DEEPSEEK_API_KEY="your_deepseek_api_key_here"
export DEEPSEEK_MODEL="deepseek-v4-flash"
```

Windows PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="your_deepseek_api_key_here"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
```

安全检查 key 来源，只输出来源，不输出 key：

```bash
python -m nl2opt.config
python -m nl2opt.eval.extractor_eval --check-env
```

运行测试：

```bash
pytest -q -o cache_dir=.tmp_pytest_cache
```

运行 mock demo：

```bash
python examples/run_mock_nl_basic.py --prompt-version v3
```

运行四类手写 JSON 基础 demo：

```bash
python examples/run_all_basic.py
```

运行本地 Streamlit demo：

```bash
streamlit run src/nl2opt/ui/streamlit_app.py
```

Streamlit demo 默认提供 production、jobshop、vrp 三个稳定案例。`custom` 输入会调用 DeepSeek API；页面只显示 API key 是否可用，不显示 key 内容。该 UI 是本地面试 demo，不是公网生产系统。

检查 20 题 case quality：

```bash
python -m nl2opt.eval.case_quality --difficulty all
```

运行真实 DeepSeek v3 final 20 eval：

```bash
python -m nl2opt.eval.extractor_eval --prompt-version v3 --difficulty all
python -m nl2opt.eval.failure_analysis --eval-dir outputs/deepseek_extractor_eval/all --report docs/deepseek_final_20_failure_analysis.md
```

## 示例

中文输入：

```text
某工厂生产 A 和 B 两种产品。A 每件利润 40 元，B 每件利润 30 元。
A 每件消耗 labor=2、material=1；B 每件消耗 labor=1、material=2。
labor 总容量 100，material 总容量 80。产品数量为非负整数，目标是最大化 profit。
```

抽取出的关键字段摘要：

```json
{
  "problem_type": "production",
  "objective": {"sense": "maximize", "name": "profit"},
  "products": [{"name": "A", "profit": 40}, {"name": "B", "profit": 30}],
  "resources": [{"name": "labor", "capacity": 100}, {"name": "material", "capacity": 80}],
  "consumption": {
    "A": {"labor": 2, "material": 1},
    "B": {"labor": 1, "material": 2}
  }
}
```

求解结果：

- `A = 40`
- `B = 20`
- `objective_value = 2200`
- `labor` 使用量为 `100`
- `material` 使用量为 `80`
- checker 通过：资源容量和目标值重新计算一致

## 评测集

| difficulty | cases | 说明 |
| --- | ---: | --- |
| easy | 8 | 四类问题各 2 题 |
| medium | 8 | 四类问题各 2 题，实体和矩阵更密集 |
| hard | 4 | 四类问题各 1 题，信息密度更高 |
| total | 20 | production / assignment / jobshop / vrp 全覆盖 |

## 评测结果

真实 DeepSeek v3 live eval，模型为 `deepseek-v4-flash`，prompt version 为 `v3`，mock 为 `false`。

| difficulty | total | end_to_end_success | spec_success | checker_success | objective_match | failure_breakdown |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| easy | 8 | 8/8 | 8/8 | 8/8 | 8/8 | `{}` |
| medium | 8 | 8/8 | 8/8 | 8/8 | 8/8 | `{}` |
| hard | 4 | 4/4 | 4/4 | 4/4 | 4/4 | `{}` |
| all | 20 | 20/20 | 20/20 | 20/20 | 20/20 | `{}` |

完整报告见：

- [docs/eval_report.md](docs/eval_report.md)
- [docs/deepseek_final_20_eval_report.md](docs/deepseek_final_20_eval_report.md)
- [docs/deepseek_final_20_failure_analysis.md](docs/deepseek_final_20_failure_analysis.md)

## 项目边界

- 这是面试级 MVP，不是工业级通用优化平台。
- 当前只支持四类小规模问题：production、assignment、jobshop、vrp。
- 不支持任意自然语言优化问题自动建模。
- 不开放公网执行任意代码。
- 当前 runner 是本地 subprocess，不是 Docker 沙箱；复杂安全防护不是本阶段重点。
- 当前 Streamlit UI 只用于本地演示，不包含登录、数据库、云部署或多用户权限系统。

## 技术栈

- Python 3.11+
- DeepSeek API
- Pydantic v2
- OR-Tools
- Jinja2
- pytest
- Streamlit：local demo

## 面试讲解 5 句话

NL2OPT 解决的是自然语言业务描述到可求解优化模型之间的落差。我的做法是 schema-first：先把中文问题抽取成受 Pydantic 校验的 `ProblemSpec`，再用 OR-Tools 模板化求解。LLM 只负责抽取实体、参数、目标和约束，不直接生成任意求解代码。求解后由 checker 独立复核约束和目标值，避免“代码跑了但结果不可信”。在自建 20 题中文评测集上，真实 DeepSeek v3 live eval 端到端通过率为 20/20。
