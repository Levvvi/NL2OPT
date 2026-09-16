# NL2OPT · 中文需求到可检查的优化结果

**一个受控优化建模工作流：将中文业务需求抽取为结构化模型，用固定模板接入 OR-Tools，并独立复核约束与目标值。**

以生产计划为例：工时 100、材料 80，产品 A/B 每件利润 40/30。系统求出 A=40、B=20、利润 2200；checker 再计算工时 `2×40+20=100`、材料 `40+2×20=80` 和利润 `40×40+30×20=2200`。如果把结果篡改为 A=41、B=20，checker 会报告两项资源超限。

我完成的核心工作是将**规则路由、结构化抽取、模板求解、独立复核和失败记录**连成可测试、可追溯的流程。LLM 负责抽取；求解代码由固定模板生成。Router 是规则分类器，项目不采用通用自主工具循环。

- [成功与故障注入的真实检查记录](reports/portfolio/evidence.json)
- [公开基准失败索引](reports/portfolio/failure-index.json) · [完整指标与范围](reports/bench_report.md)
- [当前单题真实模型运行](reports/portfolio/live-smoke.json) · [请求原文](reports/portfolio/live-smoke-request.json)
- [当前验收与环境记录](docs/nl2opt_audit.md) · [90 秒演示脚本](docs/demo_script.md)

## 两个检查关口

```mermaid
flowchart LR
    A[中文需求] --> B[Router 规则分类]
    B --> C[DeepSeek 抽取 JSON]
    C --> D[前检：Normalizer / Schema / 缺参门禁]
    D --> E[Jinja2 固定模板]
    E --> F[OR-Tools 子进程求解]
    F --> G[后检：独立重算约束与目标值]
    G --> H[结果 / 检查明细 / 失败阶段]
```

前检检查字段、类型与已实现的业务规则，缺参时停止求解。后检根据同一份 `ProblemSpec` 独立重算资源使用、指派、排程或路径指标。**两关都不能保证原始中文没有被误解；checker 通过也不等于独立证明全局最优。** 详细设计见 [architecture.md](docs/architecture.md)。

## 三分钟无密钥演示

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 后，在仓库根目录运行。`uv.lock` 固定依赖；已验证版本及测试记录见审计文档。

```bash
uv sync --locked --extra dev --python 3.11
uv run pytest -q
uv run python examples/run_all_basic.py --timeout-sec 30
uv run python scripts/export_portfolio_evidence.py
```

四类演示的30秒是本地验收预算，在线入口仍遵守自身时限。最后一个命令实际求解 production，然后将超容量、小数产量及缺参输入送入真实检查器，导出 `reports/portfolio/`。故障样例会明确标为**人工故障注入**，不是历史模型失败。演示文案是人工转述，未调用 LLM。

本地交互界面：

```bash
uv run streamlit run src/nl2opt/ui/streamlit_app.py
```

上面的无密钥演示指CLI固定JSON求解、证据导出，以及网站的production参数求解。Streamlit预设与自定义输入都会进入模型抽取，需要服务端密钥。个人网站可使用预生成证据，或连接[受限演示服务](docs/api.md)。

## 能力与边界

| 输入模型 | 求解方式 | 复核重点 |
| --- | --- | --- |
| production 生产计划 | 整数线性规划 | 产量、资源容量、利润 |
| assignment 任务分配 | 整数线性规划 | 任务覆盖、人员容量、成本 |
| jobshop 作业排程 | CP-SAT | 工序先后、机器重叠、makespan |
| vrp 容量车辆路径 | RoutingModel | 客户覆盖、容量、距离 |
| `generic_lp_milp` 严格线性 LP/IP/MIP | GLOP / SCIP | 变量范围、整数性、线性约束、目标值 |

适用于受支持的小规模模型。非线性、随机、动态及其他未支持的形式会拒绝；不能静默当作普通线性问题处理。本地 runner 是子进程，不是任意代码的安全沙箱；公网演示须使用受限入口，不能把 Streamlit 直接当作生产服务。

English scope: `generic_lp_milp` supports strictly linear LP/IP/MIP (GLOP for continuous models, SCIP for integer variables); nonlinear, stochastic, dynamic formulations are refused rather than silently modeled. The historical self-built 20/20 evaluation is not a public-benchmark result.

## 评测：分清不同数字

| 记录 | 结果 | 能说明什么 |
| --- | --- | --- |
| 自建中文 20 题历史真实模型评测（2026-06-30，prompt v3，模型 `deepseek-v4-flash`） | 20/20 端到端通过 | 限定在四类自建小题；未重跑此20题集，当前单题smoke另记于审计文档 |
| 公开基准，checker retry off | 1,098/2,070，53.0% | NL4Opt 245 题 + IndustryOR 100 题，英语/中文 × 3 次重复 |
| 同一公开协议，独立 retry on 运行 | 1,083/2,070，52.3% | 发生 412 次 checker 重试；比 off 低 0.7 个百分点 |

公开基准每轮有 **345 个原始题、2,070 次尝试**。两轮不是配对因果实验，**不能宣称重试提高准确率**。翻译审计与拒绝项仍保留在协议及分母中。题集质量检查的 `20/20` 只检查题集本身；软件测试通过数量也不是模型成功率。

[历史自建评测](docs/deepseek_final_20_eval_report.md) · [公开报告](reports/bench_report.md) · [CSV、运行清单、翻译审计与哈希](reports/artifacts/README.md) · [对外声明规则](docs/claim_registry.md)

失败索引提供 CSV 中真实存在的失败类别、原因、耗时和版本字段。历史完整失败 JSON 未公开；页面不会把档案引用伪装成可下载链接。新导出的 production 演示提供完整脱敏输入、求解结果与 checker 明细。

## 真实模型单题检查（可选）

通过未提交的 `.env.local` 或服务端环境配置 `DEEPSEEK_API_KEY`；不要将密钥放在前端。可另设 `DEEPSEEK_MODEL`。下列检查只显示配置是否可用：

```bash
uv run python -m nl2opt.config
uv run python -m nl2opt.eval.extractor_eval --check-env
uv run python -m nl2opt.eval.case_quality --difficulty all
```

2026-09-16 已完成单题真实模型检查：provider返回 `deepseek-flash`，prompt v3，端到端 2.135 秒、1,478 tokens，A=40/B=20、利润2200、checker通过。首轮遇到problem_id元信息被误标缺参，已保留失败产物并修复后复测；这不是新一轮20题评测。详见[验收记录](docs/nl2opt_audit.md)。

需要复测时，使用受限服务的 text 模式并记录日期、版本、模型返回标识、端到端耗时与 usage。缺少密钥时保持“未验证”状态，不用 mock 结果代替真实模型证据。不需要为主页展示重跑完整公开基准。

## 公共基准运行与报告复现

有密钥时可运行受限 smoke（会产生 API 调用费用）：

```bash
uv run python -m nl2opt.eval.run_bench --dataset all --track all --repetitions 1 --checker-retry off --limit 1 --timeout-sec 60 --run-id smoke-local
```

运行记录位于 `eval/results/<run-id>/`，中断后可追加 `--resume`。smoke 或不完整产物不能用来生成正式公开报告。正式发布要求完整双语言三次重复、固定 10% 翻译审计且所有审计决定已完成。

使用仓库已有公开产物，无密钥重建完整对照报告：

```bash
uv run python -m nl2opt.eval.bench_report \
  --results-csv reports/artifacts/public-20260710-off/results.csv \
  --run-manifest reports/artifacts/public-20260710-off/run_manifest.json \
  --audit-csv reports/artifacts/public-20260710-off/translation_audit.csv \
  --comparison-results-csv reports/artifacts/public-20260711-on-rerun/results.csv \
  --comparison-run-manifest reports/artifacts/public-20260711-on-rerun/run_manifest.json \
  --comparison-audit-csv reports/artifacts/public-20260711-on-rerun/translation_audit.csv \
  --output reports/bench_report.md
```

GitHub Actions 使用 Python 3.11/3.12 和同一锁文件运行无密钥测试、四类演示和证据导出，不配置模型密钥、不自动运行付费评测。[本次远程 CI](https://github.com/Levvvi/NL2OPT/actions/runs/35070598463) 已在两个 Python 版本上通过。

技术栈：Python · Pydantic · DeepSeek API · Jinja2 · OR-Tools · pytest · Streamlit。
