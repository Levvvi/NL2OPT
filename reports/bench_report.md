# 公共基准测试报告

## English executive summary

This audited public run contains 2070 attempts from `public-20260710-off`. Strict 1e-6 success is 1098/2070 (53.0%); every outcome stays in the denominator.

## 运行溯源

- Started: `2026-07-10T12:23:25.607544Z`
- Completed: `2026-07-10T23:13:19.839801Z`
- Requested model: `deepseek-v4-flash`
- Actual extractor provider/model set: `deepseek/deepseek-v4-flash`
- Actual extractor identity unavailable (no usable extractor response): `377` rows
- Token totals: translation total=1104121 (prompt=306043, completion=798078); extractor total=5335294 (prompt=3044650, completion=2290644)

## 中文执行摘要

本次已审计公开运行包含 2070 次尝试，严格 1e-6 通过数为 1098/2070（53.0%）；所有结果均保留在分母中。
确定性的中文翻译抽样已完成：已批准：93，已拒绝：12。

## 双轨结果

| 数据集 | 语言轨道 | 尝试次数 | 严格通过 | 通过率 |
| --- | --- | ---: | ---: | ---: |
| industryor | en | 300 | 107 | 35.7% |
| industryor | zh | 300 | 44 | 14.7% |
| nl4opt | en | 735 | 586 | 79.7% |
| nl4opt | zh | 735 | 361 | 49.1% |

## 按重复次数的 Wilson 置信区间

| 重复次数 | 尝试次数 | 严格通过 | 通过率 | 95% Wilson 区间 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 690 | 364 | 52.8% | [49.0%, 56.5%] |
| 2 | 690 | 366 | 53.0% | [49.3%, 56.7%] |
| 3 | 690 | 368 | 53.3% | [49.6%, 57.0%] |

## IndustryOR 类型/难度分解

类型与难度只读取结果工件中记录的元数据；`unlabelled` 表示源工件没有提供该标签。

| 难度 | 类型 | 尝试次数 | 严格通过 | 通过率 |
| --- | --- | ---: | ---: | ---: |
| Easy | assignment | 6 | 0 | 0.0% |
| Easy | generic_lp_milp | 89 | 70 | 78.7% |
| Easy | jobshop | 9 | 2 | 22.2% |
| Easy | production | 33 | 0 | 0.0% |
| Easy | unlabelled | 88 | 0 | 0.0% |
| Easy | vrp | 9 | 3 | 33.3% |
| Hard | assignment | 3 | 0 | 0.0% |
| Hard | generic_lp_milp | 24 | 12 | 50.0% |
| Hard | jobshop | 3 | 0 | 0.0% |
| Hard | production | 18 | 8 | 44.4% |
| Hard | unlabelled | 65 | 0 | 0.0% |
| Hard | unsupported | 5 | 0 | 0.0% |
| Hard | vrp | 2 | 2 | 100.0% |
| Medium | assignment | 10 | 2 | 20.0% |
| Medium | generic_lp_milp | 68 | 44 | 64.7% |
| Medium | jobshop | 4 | 0 | 0.0% |
| Medium | production | 26 | 8 | 30.8% |
| Medium | unlabelled | 138 | 0 | 0.0% |

## 失败分布

| 失败类型 | 数量 |
| ---: | ---: |
| API_ERR | 106 |
| CODEGEN_ERR | 32 |
| EXTRACT_ERR | 260 |
| INFEASIBLE_MISMATCH | 22 |
| UNSUPPORTED | 146 |
| WRONG_OPT | 406 |

## 1e-4 敏感性

| 阈值 | 成功数 | 尝试次数 | 通过率 |
| --- | ---: | ---: | ---: |
| 严格 1e-6 | 1098 | 2070 | 53.0% |
| 宽松 1e-4 | 1098 | 2070 | 53.0% |

## Checker 重试消融

本表基于范围和数据集修订版均匹配的关闭与开启完整运行。

| 模式 | 严格通过 | 尝试次数 | 通过率 | Checker 重跑次数 |
| --- | ---: | ---: | ---: | ---: |
| 关闭 | 1098 | 2070 | 53.0% | 0 |
| 开启 | 1083 | 2070 | 52.3% | 412 |

## 局限性

1. 结果只适用于运行清单固定的数据集修订版、模型配置、超时和提示词版本，不能证明通用优化建模能力。
2. 中文翻译质量只对确定性样本进行检查，而不是检查每一条翻译；审计待完成或阿拉伯数字不一致时，发布门禁会阻止生成报告。
3. 目标值匹配和 checker 验证是必要条件，但不会使不受支持、非线性、随机性或其他不可表示的问题变得可解；这些结果仍计入失败分母。
4. 只有同时记录配对的重试模式时，重试行才能描述配置消融；它们本身不能证明重试导致了差异。

## 文献与数据集来源

本报告未使用外部基准性能数值。未来如加入比较，必须在本节中列出原始来源、完全一致的评测协议和对应指标。

- `industryor` 固定数据集来源：https://huggingface.co/datasets/chenyitian-shanshu/ORLMBenchmark/resolve/54ca621042b4619b90ce23ba3edd710611822e02/IndustryOR_fixedV2.json（修订版 `54ca621042b4619b90ce23ba3edd710611822e02`，许可证 `Apache-2.0`）。
- `nl4opt` 固定数据集来源：https://huggingface.co/datasets/chenyitian-shanshu/ORLMBenchmark/resolve/54ca621042b4619b90ce23ba3edd710611822e02/NL4OPT.jsonl（修订版 `54ca621042b4619b90ce23ba3edd710611822e02`，许可证 `Apache-2.0`）。
