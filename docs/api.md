# 受限在线演示 API

这是调用仓库真实模板、OR-Tools 子进程和 checker 的小型 HTTP 服务。固定生产参数模式不需要模型密钥；自然语言模式调用真实 DeepSeek，缺少服务端配置时返回 503，绝不使用预置答案替代。故障注入接口只执行真实 checker，不宣称运行了求解器。

## 本地启动

```sh
uv sync --locked --extra dev
uv run python -m nl2opt.api
```

默认仅监听 `127.0.0.1:8765`。网站开发代理可转发 `/api/v1/nl2opt/*` 至此地址（代理应改写 Host 为目标主机）。浏览器直接跨域时，仅将自己的来源加入 `NL2OPT_ALLOWED_ORIGINS`，逗号分隔且不含路径；默认不允许任何跨域来源。

```sh
curl http://127.0.0.1:8765/api/v1/nl2opt/health
curl -H 'Content-Type: application/json' \
  -d '{"mode":"production","parameters":{"labor_capacity":100,"material_capacity":80}}' \
  http://127.0.0.1:8765/api/v1/nl2opt/solve
curl -H 'Content-Type: application/json' \
  -d '{"parameters":{"labor_capacity":100,"material_capacity":80},"quantities":{"A":41,"B":20},"objective_value":2240}' \
  http://127.0.0.1:8765/api/v1/nl2opt/check
```

第一个真实结果为 A=40、B=20、利润 2200。故障注入返回 HTTP 422，checker 独立计算工时 102 和材料 81，说明两项资源超限。`objective_value` 可省略，省略时按候选产量生成用于比对的声明值；填写错误目标值可以演示目标不一致。

## 接口与展示边界

| 接口 | 输入／响应 |
| --- | --- |
| GET `/api/v1/nl2opt/health` | `capabilities.production/check/text`、`deepseek_configured`、限制、版本；text 仅对持有效令牌且配置模型的请求启用 |
| POST `/api/v1/nl2opt/solve` | `{mode:"production",parameters:{labor_capacity,material_capacity}}` 或 `{mode:"text",text}` |
| POST `/api/v1/nl2opt/check` | `{parameters:{labor_capacity,material_capacity},quantities:{A,B},objective_value?}` |

运行响应统一包含 `run_id, mode, status, stage, problem_spec, solver_result, checker_report, diagnostics, provenance`。成功 `status=succeeded,stage=complete`；失败 `status=failed`，增加 `error.code/message/stage`。失败也可能包含有效的中间结果与完整 checker 明细，前端应读取非 2xx 的 JSON。

自然语言接口显式使用 v3 抽取提示，并记录 `provenance.prompt_version`。如果模型将 `problem_id` 标为缺失，服务以本次 `run_id` 生成这个运行元数据，在 `diagnostics.generated_metadata` 和 `assumptions` 中记录；只移除准确匹配的 `problem_id` 缺失标记，容量、利润等任何数学字段缺失仍阻止求解。

`checker_report` 有 `passed,violations,computed_objective,resource_usage,details`。`provenance.source=live_solver` 标记求解入口，`injected_check` 标记人工候选复核；`diagnostics.solver_executed` 指示求解进程是否实际启动。不将运行编号当成公开历史查询权限；不提供可枚举历史接口，临时产物随本次请求删除。需要保存证据时由访问者下载本次响应。

Checker 复核抽取后模型的可行性和目标一致性，不能证明中文需求完全正确地被建模，也不独立证明全局最优。求解器的 `OPTIMAL` 状态与独立 checker 结论应分别展示。

## 真实模型与服务器凭据

只在后端环境配置 `DEEPSEEK_API_KEY`。可选 `DEEPSEEK_MODEL` 和 `DEEPSEEK_BASE_URL`；HTTP 请求不能覆盖这些值。服务不会读取仓库 `.env` 或 Streamlit 配置，也不在健康检查或响应中返回密钥。

自然语言请求还必须携带 `Authorization: Bearer <NL2OPT_API_TOKEN>`，令牌至少 24 字符。**在网站服务器代理中注入令牌，不要将令牌或模型密钥放入浏览器代码、公开配置或用户界面。** 同源网站服务器代理到 Python 后端时，可以在请求中附带这个令牌，health 的 text 能力会相应启用。

SDK 自动重试已关闭，输出上限 2048 tokens。响应仅保留 token 计数、模型标识等安全诊断，不返回 prompt、原始模型响应、traceback、stdout/stderr、服务器路径或供应商异常文本。`provenance.requested_model` 保留请求别名；`model` 优先采用供应商响应的 model 字段，并标明 `model_identifier_source=provider_response`。缺少该字段时回退为请求别名并标注 `requested_model`，不能将回退值当作实际返回模型。启用自然语言后，输入文本会发送给 DeepSeek；网站应在提交前明确说明这一点。

## 限制与失败归因

- 请求体最多 16 KiB，文本最多 2000 字，不接受原始 ProblemSpec 或代码。
- 参数模式的容量只能是 1–200 的整数；候选 A/B 为 -500–500 的有限数字（允许小数和负数进入 checker，以演示拒绝）。
- 自然语言只开放 production、assignment、jobshop、vrp 四类白名单模板。生产最多 10 产品/10 资源；指派最多 10 员工/10 任务；车间最多 5 机器/5 工件/20 工序；车辆路径最多 3 车辆/8 客户。抽取后数字必须有限且绝对值不超过 10000。
- 每请求整体时限 30 秒，模型请求 18 秒，求解器子进程 10 秒。Linux/macOS 整体超时终止隔离进程及同组求解器子进程。
- 最多 2 个同时执行的请求、8 个 HTTP 连接线程；每直接连接 IP 每分钟 12 次，全局每分钟 40 次。服务不信任 `X-Forwarded-For`；站点代理后的访问者共享后端 IP 额度。
- 真实模型全服务滚动 24 小时最多 50 次，可用 `NL2OPT_TEXT_REQUESTS_PER_DAY=0..1000` 调整，0 禁用。该计数只在内存中，重启后清零，多副本各自计数。它不是持久费用上限；公网开放自然语言前应在网站网关设置持久配额、访客限制及供应商预算。

常见 `error.code`：`INVALID_INPUT`（400）、`UNSUPPORTED_TYPE`（422）、`SCHEMA_VALIDATION_FAILED`（422）、`MISSING_REQUIRED_FIELDS`（422）、`CHECKER_REJECTED`（422）、`AUTH_REQUIRED`（401）、`RATE_LIMITED`（429）、`MODEL_NOT_CONFIGURED`（503）、`SERVER_BUSY`（503）、`SOLVER_TIMEOUT` / `REQUEST_TIMEOUT`（504）。故障注入被拒绝是演示的预期结果，不应显示成网页故障。

## 部署

Docker 镜像使用仓库 `uv.lock` 安装依赖，以非 root 用户运行，密钥不进入镜像构建上下文。未授权的远端绑定会拒绝启动。

```sh
docker build --build-arg NL2OPT_REVISION="$(git rev-parse HEAD)" -t nl2opt-api .
# 公开生产参数与候选复核，不启用付费模型。
docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --memory=1g --cpus=2 --pids-limit=64 \
  -p 127.0.0.1:8765:8765 -e NL2OPT_PUBLIC_DEMO=1 nl2opt-api
```

`noexec` 仍允许 Python 解释器读取生成的模型文件。公网前使用 TLS 反向代理，设置请求头/请求体超时与 16 KiB 大小限制；此标准库 HTTP 服务不直接承担互联网边缘防护。固定域名网站代理可以保持所有浏览器请求同源，从浏览器角度不需要 CORS；但后端仍校验代理转发的 `Origin`。必须将该来源加入 `NL2OPT_ALLOWED_ORIGINS`，或让可信网站代理先验证来源、再剔除转发请求中的 `Origin`。仅改写 `Host`（例如 Vite `changeOrigin`）不会自动移除 `Origin`。

需要真实模型时，改用部署平台的 Secret 存储提供 `NL2OPT_API_TOKEN` 和 `DEEPSEEK_API_KEY`，不要将它们写入启动脚本或 Git。默认远端所有接口需令牌；`NL2OPT_PUBLIC_DEMO=1` 仅豁免 production/check/health，text 始终需令牌。用供应商网络策略仅允许后端被网站代理访问。Docker 健康检查自动读取服务端令牌。

部署验收：health 返回准确能力；production 参数 100/80 返回 2200；90/60 返回 1900；41/20 的注入返回资源超限；缺密钥 text 返回 503；非法 Origin 被拒绝；设置的版本出现在响应。只有配置真实服务器和密钥后，才另做单题真实模型 smoke test；本仓库测试不消耗模型额度。
