# 部署与平台接入

## 1. Windows 本地运行

代码默认监听 `127.0.0.1:8001`，本地权限模式仅允许回环访问。不要在 `AUTH_MODE=local` 时作为公开服务使用。

```powershell
cd "C:\Users\Administrator\Desktop\科大\智能体\risk-agent-design"
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install --omit=dev
Copy-Item .env.example .env
# 编辑 .env：设置随机 SESSION_SECRET、LLM_API_KEY 等
.venv\Scripts\python.exe scripts/bootstrap.py
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

本机交付目录已完成以上步骤，请直接使用启动脚本。Windows批处理必须保存为ASCII/CRLF，PowerShell脚本保存为UTF-8 BOM/CRLF；使用 `重启智能体.cmd -Check` 可检查路径与语法而不启停服务。设计副本通过preview.ps1使用8001和独立runtime，并校验进程身份；运行中的任务未结束时拒绝重启。`bootstrap.py` 导入 `reference/data-standard.xlsx`，重复执行会跳过已导入原件；`--refresh-source` 仅用于明确需要重新解析这一原件的情况。切勿用它替代生产数据迁移。

PDF 依赖 Node/Playwright。Windows 默认使用 Edge；无 Edge 时执行 `npx playwright install chromium` 并将 `BROWSER_BINARY` 留空。`NODE_BINARY` 指定 Node 可执行文件；正常安装 Node 后可留空。`NODE_PATH` 仅在使用外部预装模块目录时填写。

### 密码访问

需要把服务提供给同一网络中的其他电脑时，应先设置访问密码，再调整监听地址和防火墙。Windows 双击根目录 `设置访问密码.cmd`，或执行：

```powershell
.venv\Scripts\python.exe scripts\set_password.py
```

脚本会将 `AUTH_MODE` 改为 `password`，生成或保留独立的 `SESSION_SECRET`，并只把 PBKDF2-SHA256 密码哈希写入 `.env`。重启后页面会显示访问验证。不要把 `.env` 提交到代码仓库，也不要在聊天、截图或启动参数中传递密码。

## 2. 本机 PostgreSQL 与 S3 对象存储

设计副本已配置为结构化数据库与对象存储分离部署：业务记录、模型、报告元数据和审计记录进入 PostgreSQL；上传的原始资料进入 SeaweedFS 提供的 S3 接口。服务只监听 `127.0.0.1`，持久化目录为 `C:\RiskAgentData`。项目中文路径仅保存应用代码，避免 PostgreSQL Windows 版初始化 UTF-8 数据目录时受系统代码页影响。

```powershell
./scripts/local_stores.ps1 -Action install
./scripts/local_stores.ps1 -Action status
./scripts/local_stores.ps1 -Action stop
```

`install` 首次运行会生成本机专用随机凭据，初始化 PostgreSQL 17 数据库集群和 S3 身份，并把连接配置写入 `.env`。凭据及数据库文件不进入代码包。`preview.ps1` 检测到 `postgres + s3` 配置后会自动启动两个存储服务。
若本机尚无运行组件，安装脚本会从 EDB 官方地址下载 PostgreSQL 17.11，并从 SeaweedFS 官方 GitHub Release 下载 4.48；SeaweedFS 校验发布方 SHA-256，PostgreSQL 解压时执行 ZIP CRC 校验。

迁移现有 SQLite 数据前先停止应用并备份，再执行：

```powershell
python scripts/backup_local.py
python scripts/migrate_local_stores.py runtime/backups/<备份目录>
python scripts/check_storage.py
```

迁移要求目标数据库为空，会逐表比对所有行；对象文件按数据库中保存的 SHA-256 校验上传和下载。任何一步不一致都会回滚结构化数据事务。企业、气候和经济数据允许保持空表，后续通过页面导入。

## 3. DM8 与 MinIO（可选的组织环境）

用户当前未提供服务地址或正式模型，本次仅完成适配和本地验证，不能将 SQLite/本地文件测试等同于 DM8/MinIO 联调。

先按组织数据库规范创建专用 DM 用户和存储空间，执行 `database/dm8.sql`（建表脚本面向空业务 Schema；应用启动会检查并补建缺失表）。安装与 DM8 客户端/DPI 匹配的 `dmPython` 驱动，并将所需动态库加入 PATH 或 LD_LIBRARY_PATH。驱动需由部署方的 DM 安装包提供。本项目不包含数据库授权、数据库安装介质或服务账号。

```dotenv
DB_BACKEND=dm8
DM_HOST=数据库地址
DM_PORT=5236
DM_USER=RISK_AGENT
DM_PASSWORD=服务密码
STORAGE_BACKEND=minio
MINIO_ENDPOINT=对象存储地址:9000
MINIO_ACCESS_KEY=访问键
MINIO_SECRET_KEY=私钥
MINIO_BUCKET=risk-agent
MINIO_SECURE=true
```

`MINIO_ENDPOINT` 不带协议前缀；`MINIO_SECURE` 控制 TLS。生产环境为账号授予该 Bucket 的必要权限。已有 Bucket 推荐由管理员预创建；应用可尝试创建不存在的 Bucket。启动失败会报错，不会自动退回本地存储。

切换数据库会指向一个新的数据环境，SQLite 历史报告不会自动迁移。业务数据可从页面导出 CSV 后在新环境导入；文件、模型版本和审计记录需按组织迁移流程整体迁移。切换后至少验证四表中文字段、长文本 CLOB、分页、事务回滚、重复约束、MinIO 上传/下载/删除和对象大小核验，再安排大数据压力测试。

DM 官方开发参考：[Python 开发指南](https://eco.dameng.com/document/dm/zh-cn/start/python-development.html)。对象接口参考：[MinIO Python SDK](https://github.com/minio/minio-py/blob/master/docs/API.md)。

## 4. 接入既有智能体广场

本地 `/` 已提供可点击卡片，整页跳转 `/agent`。目标页为独立智能体工作台，无平台侧栏或学校标识；顶部展示真实业务概览，三个功能区通过左侧业务入口切换，手机上入口横向排列。报告配置在左、预览在右；查看记录、使用说明、系统设置常驻左侧业务导航底部。应用模型下拉位于生成按钮旁，SD模型保留在预测设置中，二者独立。集成卡片使用 `target="_top"`，从嵌入容器打开时也跳转整个页面。真实平台源码和发布权限尚未提供，本次没有修改 `cumtai.fifedu.com` 的在线广场。将 `integration/agent-manifest.json` 中的业务信息与 `integration/gallery-card.html` 的入口接入平台现有卡片组件即可。

页面返回 `Cache-Control: no-store`，脚本和样式返回 `no-cache` 并携带内容哈希版本参数。反向代理应保留这些缓存头和查询参数，避免升级后沿用旧脚本。首次加载提供加载状态，脚本或接口异常时可点击“重新加载”恢复。

推荐与平台同域，反向代理将 `/risk-agent/` 转发到本服务，同时去掉该前缀，应用设置：

```dotenv
PUBLIC_BASE_PATH=/risk-agent
PLATFORM_BASE_URL=https://实际平台域名
AUTH_MODE=platform
SESSION_SECRET=至少32字符的独立随机会话密钥
PLATFORM_JWT_SECRET=与平台约定的至少32字符HS256验证密钥
JWT_ISSUER=平台约定签发者
JWT_AUDIENCE=risk-agent
ALLOWED_ORIGINS=https://实际平台域名
```

Nginx 示例：

```nginx
location /risk-agent/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 240s;
    client_max_body_size 10g;
}
```

只信任组织受控代理：使用 Uvicorn `--proxy-headers --forwarded-allow-ips=<代理IP>`。反向代理需禁用对应接口的缓存，保留任务轮询通道。PDF 任务不需要公开原件 URL。

平台继续负责登录、用户和账号管理，本应用只验证既有凭据。支持标准 HS256 JWT，要求 `sub`、`role`、`iss`、`aud`、`exp`，可选 `nbf`。角色映射为 `admin/editor/viewer`。平台可直接以 `Authorization: Bearer ...` 调用接口，或同域页面以 `POST /api/auth/session` 换取 HttpOnly 会话 Cookie。页面令牌弹窗可完成手工接入验证；正式平台应通过其现有登录交接流程调用此接口，不把长效密钥写入前端。

平台若使用 RS256、OIDC、网关签名或另一套权限声明，需要在 `app/auth.py` 增加组织约定的验证适配；不要把 HS256 密钥当作 JWT 公开验证证书。可选 `AUTH_MODE=token` 用于接口联调，`ROLE_TOKENS` 是服务端静态测试凭据，正式用户会话推荐使用平台模式。

当前数据集采用平台共享业务库，角色控制读写；聊天历史按 `sub` 隔离。没有实现多租户的数据行隔离，需由平台业务授权范围或后续数据权限适配提供。页面可能显示操作按钮，权限最终由服务端校验。

`integration/chatflow-adapter.js` 提供现有 ChatFlow 的 `/chat` 调用适配。上传的 Vue 导航、历史与 ChatFlow 组件保存在 reference 中；当前独立前端复用规范 Token/字体并实现对应交互，没有构建另一套平台账号系统。

## 5. LLM 服务切换

```dotenv
LLM_PROVIDER=DeepSeek
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_MODELS=deepseek-flash,deepseek-v4-pro
LLM_API_KEY=仅服务端保存
```

本地 DeepSeek、讯飞或其他服务若提供 OpenAI 兼容的 `/chat/completions`、JSON 响应和 tools 协议，可改 `LLM_BASE_URL/LLM_MODEL/LLM_MODELS/LLM_API_KEY` 后重启。`LLM_MODEL` 为默认模型，`LLM_MODELS` 为逗号分隔的启用模型ID；应填写实际服务支持的模型。应用模型下拉使用服务端目录，每次报告和问答分别传递模型ID，不修改全局默认值；服务端拒绝未配置的模型。当前两个模型均已实际连接验证，结果见 `application-model-results.json`。讯飞原生 WebSocket 等不同协议需要实现 `app/llm.py:complete` 的对应传输适配，本次没有声称已接通。切换后需重新检查工具调用与定量绑定校验。

API 参考：[DeepSeek Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion/)。

## 5. 容器、运维与容量

提供 Dockerfile 和 compose 配置；本机未安装 Docker，因此未验证容器构建。生产部署先配置 `.env.production`，调整运行数据目录权限，使用外部 DM8 与受控 MinIO。

```shell
docker build -t risk-agent:1.0.0 .
docker compose --env-file .env.production up -d agent
```

compose 的可选 MinIO Profile 需要部署方在 `.env.production` 指定已经审核的 `MINIO_IMAGE` 和 `MINIO_ROOT_USER/MINIO_ROOT_PASSWORD`；Compose 解析会要求这些值，即使不启用 Profile。不需要容器 MinIO 时可删除该服务段，直接连接现有 MinIO。

当前使用单应用进程和两个后台任务线程；启动参数固定 `--workers 1`，避免多个进程重复恢复任务。重启会将中断任务标记失败，支持重新提交，不承诺自动续跑。多实例正式部署需将任务执行接入平台现有任务队列和分布式互斥；不重复开发平台队列。

原件流式上传，默认单文件上限 10GB，导入分批写入 500 条，查询分页且筛选字段有索引。3TB 是实际原件总量目标，需配置足够的 MinIO 容量和备份；本地模式不是生产 3TB 验证环境。统计和模型标定会读取所选样本，20万条及更大规模必须做实际性能测试，必要时采用平台批计算与统计缓存。不得通过复制文件、填充空白或生成假记录提高验收量。

定期备份数据库、MinIO、模型版本、报告和审计记录；凭据独立保存。日志在 `runtime/logs`，健康检查 `/api/health`，任务状态 `/api/jobs/{id}`。应用默认不记录 Authorization 或请求正文。原件解析不是恶意软件扫描；公开上传应复用平台已有扫描能力。图片已保存，未配置 OCR，扫描 PDF 不会伪称已经结构化。旧版 `.doc` 需先转换为 `.docx`。
