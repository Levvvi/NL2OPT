# 90 秒演示脚本

演示入口使用个人网站 NL2OPT 项目页；无网络或无后端时直接打开仓库的 `reports/portfolio/evidence.json`。所有故障注入均明确标注，不冒充历史模型失败。

## 展示顺序

| 时间 | 操作 | 讲解重点 |
| --- | --- | --- |
| 0–15 秒 | 展示中文生产计划与两个检查关口 | 我把中文需求接入受控建模工作流。规则 Router 分类，模型抽取，固定模板求解。 |
| 15–35 秒 | 查看成功案例 | 实际 OR-Tools 求得 A=40、B=20。checker 独立重算工时100、材料80、利润2200。 |
| 35–55 秒 | 切到“故障注入：资源超限” | 人工改为 A=41、B=20 后，真实 checker 报告102>100、81>80；失败能够定位到后检。 |
| 55–65 秒 | 切到“小数产量”或“缺参前检” | 资源不超限仍可能违反整数约束；缺参则在求解前拒绝，而不是编造参数。 |
| 65–80 秒 | 打开公开失败索引，按类别筛选 | 每轮345题、2种语言、3次重复。索引来自已公开CSV；未公开的完整档案不提供伪链接。 |
| 80–90 秒 | 展示边界及证据入口 | 前后检查不能证明中文理解完全正确，也不能独立证明最优性；给出版本、范围与可复现命令。 |

## 无密钥重建演示产物

```bash
uv sync --locked --extra dev --python 3.11
uv run pytest -q
uv run python examples/run_all_basic.py --timeout-sec 30
uv run python scripts/export_portfolio_evidence.py
```

可展示的现有文件：

- `reports/portfolio/evidence.json`：真实成功求解、真实故障检查、结构化输入和运行来源。
- `reports/portfolio/failure-index.json`：公开CSV全部失败行的白名单字段。
- `reports/artifacts/`：公开基准CSV、manifest、翻译审计和哈希。
- `docs/nl2opt_audit.md`：本次环境、测试、未完成的外部验证。

不再要求打开未随仓库提供的 `outputs/deepseek_extractor_eval/all/<case>/raw_response.txt` 等历史逐题目录。历史20题真实模型结果仅以已公开的 summary/report 为依据。

## 现场操作备选

```bash
uv run python -m nl2opt.pipeline examples/specs/production_basic.json --output-dir outputs/demo/production_basic
uv run streamlit run src/nl2opt/ui/streamlit_app.py
```

生产样例生成的 `outputs/demo/production_basic/` 可查看 `solution.json`、`checker_report.json`、`pipeline_report.json`；这些路径在运行后才存在，不把它们当作已提交的历史产物。

Streamlit的预设与自定义输入均需模型密钥；无密钥演示使用前述CLI固定JSON、静态证据或网站production参数求解。

## 在线测试说明

受限服务操作及配置见 [api.md](api.md)。在线求解应显示“本次实际执行”或“预生成证据”；live中文抽取仅在后端明确启用且配置密钥后可用。没有真实模型调用时，不能称作本次端到端模型验证。

现场失败时展示准确阶段：输入/缺参、抽取/解析、求解超时、结果解析或checker拒绝。保留 request/run ID、版本与脱敏明细，不打印密钥或请求头。
