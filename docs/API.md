# 接口说明

默认前缀 `/api`，部署子路径时为 `/risk-agent/api`。在线 Swagger：`/api/docs`；机器可读规范见 `openapi.json`。受保护接口支持平台 JWT、联调 Bearer Token 或 HttpOnly Cookie。上传/编辑/生成需要 editor，删除/存储核验/LLM连接测试/专家评价需要 admin，查询和工具问答需要 viewer。具体权限以服务端为准。

## 数据与原件

数据集 ID：`accidents/enterprises/climate/economy`。业务请求字段必须取自 `/api/config.schemas`，保留 Excel 原字段；禁止新增未知字段。通用筛选为 `industry/region/start/end/q`，分页 `limit`（默认10，范围1–200）、`offset`。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/health` | 健康状态 |
| POST | `/auth/session` | `{"token":"平台令牌"}` 换取 Cookie |
| GET | `/config`、`/overview` | 字段标准、指标、配置状态、真实数量和大小 |
| GET | `/data/{dataset}` | 分页查询，返回 items/total/fields |
| GET | `/data/{dataset}/export` | 当前筛选范围 CSV 下载，含 BOM 和公式注入转义 |
| POST | `/data/{dataset}` | 创建业务字段记录，完全重复返回 409 |
| PUT | `/data/{dataset}/{id}` | `{"version":1,"data":{...原字段...}}`，乐观并发版本不符返回 409 |
| DELETE | `/data/{dataset}/{id}` | 删除记录，历史报告保留快照 |
| POST | `/uploads` | multipart `file`、可选 `dataset`，原件保存后提交解析任务 |
| POST | `/imports/{stage_id}/commit` | 将通过校验的暂存记录导入；重复/正在导入返回 409 |
| GET | `/imports/{stage_id}/errors` | JSONL 错误行清单 |
| GET | `/files`、`/files/{id}/preview` | 原件元数据、提取文本 |
| GET | `/files/{id}/download` | 原件下载，强制附件 |
| DELETE | `/files/{id}` | 删除原件及该文件导入记录，留下审计 |
| POST | `/storage/verify` | 核验每个对象实际字节数 |
| POST | `/analysis` | 按 Filters 返回统计、基础条件、66 指标及缺失原因 |

上传返回 `{"file_id":"...","job":{"id":"..."}}`。轮询任务完成后读取 `result.id`（暂存批次）、`valid/rejected/counts/previews`；检查预览和错误再提交。普通 PDF/DOCX/HTML/图片是原始资料，仅保存/提取文本，不会自动编造四表记录。

## 模型与仿真

师生页面每行业固定使用一个模型，不暴露版本或模型维护入口。以下模型编辑、导入导出和快照接口为后台维护能力；仿真请求中的情景参数不会修改固定模型定义。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET/POST | `/models` | 六行业模型列表/创建 |
| POST | `/models/validate` | 校验完整 JSON 模型 |
| POST | `/models/import` | multipart `file/industry`；risk-sd JSON 或受限 Vensim .mdl |
| PUT | `/models/{id}` | 完整模型，必须带当前 version；保存时新版本+1 |
| GET | `/models/{id}/versions` | 所有历史定义 |
| GET | `/models/{id}/export?version=N` | 当前或指定版本 JSON |
| DELETE | `/models/{id}` | 每行业至少保留一个模型 |
| POST | `/simulations` | 数据标定及三情景 RK4 计算 |
| GET | `/simulations` | 历史结果列表 |
| GET | `/simulations/{id}/export` | 实际计算点 CSV |

```json
{
  "model_id":"从models接口选取",
  "filters":{"industry":"工贸","region":"广东省","start":"2011-01-01","end":"2026-07-31"},
  "months":3,
  "parameters":{"prevention_rate":0.08},
  "threshold":60
}
```

响应包括模型 ID/版本、情景参数、`sampling_interval_months: 0.05`、每0.05月的 `points`、calibration 字段证据和模型限制。三个月每情景61点；CSV导出同样保留全部计算点。历史结果保持创建时的采样密度。编辑原模型不会更改已存历史结果。

## 报告与任务

`POST /reports` 提交以下结构并返回后台 job：

```json
{
  "industry":"工贸","region":"广东省",
  "start":"2011-01-01","end":"2026-07-31",
  "months":3,"scenario":"基准场景","model_id":"从models接口选取",
  "parameters":{},"threshold":60,
  "indicators":["事故总数","月度分布","管理因素频次","死亡人数","当前综合风险指数"],
  "coverage_confirmed":false,"use_llm":true,"llm_model":"从config.llm.models选取"
}
```

情景取值：基准场景/生产压力增大/安全投入减少；预测周期 1–36 月。indicators 必须为 `/config.indicator_groups` 中的候选项，至少一项，无重复。`llm_model` 为应用文字生成模型ID，必须属于 `/config.llm.models`，省略时固定使用当前默认模型并保存到报告参数；SD模型使用独立的 `model_id`。`GET /config` 的 `llm.model/models/configured` 分别表示默认模型、启用模型目录与连接配置状态，不返回密钥。

`coverage_confirmed` 是用户对区域事故采集完整性的确认，不能依据基础字段完整率自动勾选。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/reports` | 已生成报告、实际正文长度、LLM状态 |
| GET | `/reports/{id}/html` | 内联在线预览 |
| GET | `/reports/{id}/html?download=true` | HTML 附件下载 |
| GET | `/reports/{id}/evidence` | 统计/指标/数据哈希清单/模型快照/预测验证/LLM状态 |
| PATCH | `/reports/{id}/review` | 保存研判及预测结论与指标专家验证 |
| POST | `/reports/{id}/pdf` | 创建 PDF 后台任务 |
| GET | `/reports/{id}/pdf` | 已生成 PDF 下载 |
| DELETE | `/reports/{id}` | 删除报告及 HTML/PDF/证据文件 |
| GET | `/jobs`、`/jobs/{id}` | queued/running/completed/failed 与 progress/stage/result/error |

## 问答、历史与验证

`POST /chat`：`{"content":"问题","filters":{...},"sessionId":"可选既有会话","llm_model":"可选应用模型ID"}`，返回 `answer/message/sessionId/trace/sources`。允许的工具为真实数据查询和 SD 仿真，禁止任意 SQL 或执行用户上传脚本。历史会话按平台 sub 隔离，`GET /history`、`PATCH /history/{id}`（title/pinned）、`DELETE /history/{id}`。

`POST /llm/test` 实际调用配置模型；`GET /audit` 返回管理员审计；`GET /acceptance` 返回当前数量、指标、基础字段完整率和未验证项。`POST /acceptance/expert` 接收人工独立标注，格式见 `integration/expert-evaluation.example.json`，返回点估计与 90% Wilson 区间。该接口不自动生成专家评价，也不替代专家评审。

错误：400/422 参数或数据不合法；401 未认证；403 无权限或请求来源不允许；404 对象不存在；409 并发冲突/重复提交；413 文件超限；500 服务故障。任务失败在 job 的 error 中查看，页面显示业务错误，内部异常详情保留在服务日志。


## 行业模型与标定结果（v2）

`GET /api/health` 新增 `model_engine_version: industry-report/2.0`，可用于检查运行中的进程是否加载行业算法；`simulation_samples_per_month: 20` 表示加载了本轮加密采样。

`GET /api/models` 中内置模型包含 `profile_version` 与 `feature_labels`。参数的 `calibrate` 可为原原因字段，也可为 `industry:<类别>:initial|weight|trend`；绑定字段必须属于模型行业。模拟请求仅接受手动参数覆盖，自动标定项不能通过 `parameters` 覆盖。

`POST /api/simulations` 除原曲线和参数外，返回 `stock_labels`、`source_manifest_sha256` 与 `industry_evidence`。后者含实际样本数、命中数、各类数量/占比/权重/趋势、来源片段与趋势不足原因；不足的趋势是null，不能展示为已估计的零增长。标定明细中的对应项带 `status: insufficient`，数值0仅为积分时采用的中性漂移。

新增内容不改变Excel字段、已有报告证据快照、版本导出和模型原生格式。未修改的旧内置模型启动后升级为新版本；用户自定义模型保留。
