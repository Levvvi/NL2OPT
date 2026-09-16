# NL2OPT portfolio audit · 2026-09-16 UTC

本文件记录此次个人主页准备工作的实际验证，不把历史勾选项当作当前验收。实现基于 `06b8fa740fe534bccf887a2b4a9aa8de1158ad10`；在隔离副本完成验证后同步，发布状态以Git提交与Actions实际记录为准。验证内容由 `reports/portfolio/evidence.json` 中的逐文件 SHA-256 与聚合 `source_sha256` 标识。

## 路径与修改范围

- 同步目标仓库：`/Users/a1/Documents/ChatGPT/电脑调试和管理/NL2OPT`。
- 实施副本：`/Users/a1/.codex/.chatgpt-projects/g-p-6aa8e34de4448191bb624d1de6d2f8ee/work/nl2opt-implementation/repo`。
- 公开运行证据会删除本机路径、原始日志与密钥上下文。这里记录本地审计路径以便所有者复查；它不是可供访问者下载的运行档案路径。

## 锁定环境

保留已有 `uv.lock`，未升级依赖。

- uv：0.12.9。
- 锁文件 SHA-256：`402a17a9f2e9e405c6a4fdee95de62ee689cc47a85c70254e08ad4103a7d1815`。
- Python 3.11.15：实施副本 `.venv/bin/python`。
- Python 3.12.14：隔离环境 `/private/tmp/nl2opt-venv312/bin/python`。
- 公共依赖：OR-Tools 9.15.6755、Pydantic 2.13.5、Jinja2 3.1.6、OpenAI SDK 3.14.0、pytest 9.1.1、Streamlit 1.63.0。
- NumPy 按锁文件的 Python 版本标记安装：3.11 为 2.4.6，3.12 为 2.5.3。
- 两个版本均已用 `uv sync --locked --extra dev --python <version>` 成功安装。

标准复现命令：

```bash
uv sync --locked --extra dev --python 3.11
uv run pytest -q
uv run python -m nl2opt.eval.case_quality --difficulty all
uv run python examples/run_all_basic.py --timeout-sec 30
uv run python scripts/export_portfolio_evidence.py
```

另一个隔离环境可使用 `UV_PROJECT_ENVIRONMENT=/tmp/nl2opt-312 uv sync --locked --extra dev --python 3.12`，随后用该环境的 Python 执行同一测试。安装所需的网络访问与测试时不调用模型是不同事项；本次测试没有真实模型调用。

## 当前结果

运行库产品代码在下列验证中保持一致。Python3.11两轮先完成；随后补齐4个测试文件的超时预算，并给示例CLI新增默认不变的可选timeout参数；Python3.12两轮验证最终文件。不能将3.11记录表述为最终全部文件逐字一致。日志与快照说明保留在`reports/portfolio/`。

| 验证 | 2026-09-16 实际结果 |
| --- | --- |
| Python 3.11 全量测试，第1次（最终预算补齐前） | [412 passed，3条既有SWIG弃用warning，118.61秒](../reports/portfolio/pytest-python311-pass1.txt) |
| Python 3.11 全量测试，第2次（最终预算补齐前） | [412 passed，3条同类warning，117.79秒](../reports/portfolio/pytest-python311-pass2.txt) |
| Python 3.12 全量测试，第1次（最终文件） | [412 passed，3条同类warning，116.68秒](../reports/portfolio/pytest-python312-pass1.txt) |
| Python 3.12 全量测试，第2次（最终文件） | [412 passed，3条同类warning，116.21秒](../reports/portfolio/pytest-python312-pass2.txt) |
| 20题静态质量检查 | 20/20；不代表新的模型评测 |
| 四类确定性示例 | production 2200、assignment 21、jobshop 7、VRP 44；checker全部通过 |
| 完整公开报告重建 | 含 retry-on 对照参数，生成内容与已提交报告逐字相同 |
| 证据导出 | 1次真实求解成功 + 3例明确标注的故障注入；972/987条公开失败行 |
| 当前单题真实模型smoke | 2次真实调用：首轮schema拒绝；修复后成功，2.135秒、1478tokens、目标2200、checker通过 |
| GitHub Actions | 已新增3.11/3.12无密钥工作流；本地验收不替代远程CI成功记录 |

初次文档改版曾触发1项README固定词句断言，随后恢复英文范围说明并通过；API最终补充完成前的一轮旧403项测试也全部通过。首次Python3.12全量为411 passed / 1 failed：`test_evaluate_mock_extractor_cases_metrics`中的`extractor_jobshop_01`子进程超过测试默认10秒，逐题产物确认其余7题通过。随后仅统一包含jobshop的测试运行预算为30秒，产品默认时限不变，并以3.12连续两次全量复核。示例脚本增加可选`--timeout-sec`（默认仍10），CI与验收命令显式传30，给求解器、解释器启动和调度留出余量；这不是放宽在线接口时限。上述预验收不计入最终通过轮次。

3.11两轮之后的改动范围仅为 `tests/test_extractor_eval.py`、`tests/test_extractor_eval_prompt_version.py`、`tests/test_mock_nl_pipeline.py`、`tests/test_pipeline_cli.py` 的测试预算，及 `examples/run_all_basic.py` 的可选 `--timeout-sec` 参数（默认仍10）。`src/`、证据导出脚本、`pyproject.toml`、`uv.lock` 与3.11验证快照一致。最终3.12覆盖上述测试/示例调整。快照包含的文件范围与哈希以 `reports/portfolio/validation.json` 为准。

## 调用链与检查范围

`中文输入 → route_text → extract_problem_spec → DeepSeekClient.complete_json → JSON解析 / Normalizer / Pydantic → run_problem_spec → 缺参门禁 → Jinja2模板 → OR-Tools子进程 → checker → report`

- Router 为规则分类，不是通用自主代理循环。
- 首关校验结构化字段及已有业务规则；`missing_fields` 非空时在代码生成前停止，网页与评测共用门禁。
- 次关根据 `ProblemSpec` 重新计算约束与目标值。production 拒绝小数、负数、非有限量、未知产品名、资源超限与目标值不一致；未提供的产品产量按0处理，不承诺检测缺失产品条目。结果模型也拒绝非有限数。
- `pipeline_report.json` 记录 `failure_stage`，`checker_report.json` 保留完整结构化 checker 内容。失败没有 checker 结果时明确记为未运行，不能制造“通过”状态。
- 以上不能证明中文需求被完整理解，也不能独立证明全局最优。

## 手算与故障证据

成功样例为仓库已有 `examples/specs/production_basic.json`。本次实际运行结果：A=40、B=20，工时 `2×40+20=100`，材料 `40+2×20=80`，利润 `40×40+30×20=2200`。checker 分别重新计算并对照容量与solver目标值。

故障注入不是历史模型输出：

1. 人工令 A=41、B=20；真实 checker 拒绝工时102>100与材料81>80。
2. 人工令 A=0.5、B=0；真实 checker 拒绝非整数数量。
3. 将 `material.capacity` 标为未解决字段（残留数值视为占位）；真实 pipeline 在模板生成前拒绝。

`reports/portfolio/evidence.json` 含上述输入、solver/result、checker报告、运行标记、依赖与源码哈希。导出脚本会对“成功没通过”“故障被误接受”“缺参仍生成代码”直接报错，不会生成表面成功的证据。

## 评测证据索引

| 证据 | 路径 / 范围 |
| --- | --- |
| 历史自建中文真实模型20/20 | `docs/deepseek_final_20_eval_report.md`，2026-06-30；`outputs/deepseek_extractor_eval/all/summary.json` |
| 公开基准正式报告 | `reports/bench_report.md` |
| retry-off CSV/运行清单/翻译审计 | `reports/artifacts/public-20260710-off/` |
| retry-on CSV/运行清单/翻译审计 | `reports/artifacts/public-20260711-on-rerun/` |
| 公开产物哈希与脱敏说明 | `reports/artifacts/manifest.json`、`reports/artifacts/README.md` |
| 网站失败查询索引 | `reports/portfolio/failure-index.json`，只含公开CSV白名单字段 |
| 对外用词边界 | `docs/claim_registry.md` |

每轮为245道NL4Opt + 100道IndustryOR，2种语言、3次重复，共2070次尝试。retry-off为1098/2070（53.0%），独立retry-on为1083/2070（52.3%），后者发生412次checker重试。不能声称重试提升准确率。历史完整失败JSON并未公开，CSV中的档案引用不作为可用下载链接。

## 当前真实模型单题 smoke

本任务最初在未配置的进程环境执行配置检查，结果为missing；随后使用用户授权的本地服务端配置进行单题真实API调用。没有将凭据写入网页、日志或产物。

输入原文与API请求体见 [`live-smoke-request.json`](../reports/portfolio/live-smoke-request.json)。这是完整的生产计划输入，不含机密业务信息。

| 尝试 | 记录 | 结果 |
| --- | --- | --- |
| 首轮，2026-09-16 07:29:22 UTC | [`live-smoke-first-attempt.json`](../reports/portfolio/live-smoke-first-attempt.json)，run `e4514c5cc2c0478386c0480f2cabc14f` | prompt v2把`problem_id`标为缺参，schema门禁停止，solver未执行；5503ms、1804 tokens |
| 修复后，2026-09-16 07:32:01 UTC | [`live-smoke.json`](../reports/portfolio/live-smoke.json)，run `1deca11080124439b68314f7110359cf` | HTTP200、complete；prompt v3，provider返回model=`deepseek-flash`，requested_model相同、来源`provider_response`；2135ms、1478 tokens；A=40、B=20、利润2200，checker通过 |

修复仅由服务器补充`problem_id`元信息，并显式使用v3抽取提示；资源容量等业务缺参仍会被拒绝。新增回归覆盖两种情况。成功调用usage为prompt 1351、completion 127、total 1478 tokens；两次合计3282 tokens。没有重跑历史20题集或每轮2070次公开基准。

首轮产物中的model字段尚未区分请求别名与供应商返回标识，保留原始记录，不将其反推为已验证的返回标识。第二轮使用修复后的标识来源字段。两份响应中的`06b8fa7+portfolio-reliability`是运行版本标签，不是已提交Git哈希；最终实现以基线提交和当前源码哈希对应。

## 尚依赖外部条件的验证

真实模型单题 smoke 已完成，不能据此推断完整20题集或公开基准在当前版本重新通过。公开后端可用性与远程CI需要实际部署/推送才能验证。许可协议涉及作者授权选择，本次未擅自赋予开源许可。
