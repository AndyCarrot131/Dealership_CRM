# 架构设计：AI-Augmented Dealership CRM

> 配套 `PROJECT.md`（需求与功能边界）。本文件描述**实现架构**：两个 exe 的拓扑、内部结构、首次运行、打包、安全与云迁移路径。

---

## 0. 已确认的关键决策

| # | 决策 | 取值 |
|---|------|------|
| 拓扑 | 共享 DB + 每 sales 一个客户端 | **A**：一台常开机器跑 `database.exe`，各 sales 机器跑 `crm.exe` 经局域网连过去 |
| DB | database.exe 装什么 | **便携版 PostgreSQL** 打进 exe（真服务进程） |
| 客户端壳 | crm.exe 怎么呈现 | **FastAPI + React 静态文件 + pywebview**，PyInstaller 打包 |
| 账号 | 用户/密码存哪 | **存 Postgres**（`users` 表，应用层认证） |
| 远景 | 后期上云 | 同一套 FastAPI 后端迁 AWS，丢弃 pywebview 壳 |

**一句话架构**：中央共享的只有数据库。业务逻辑 / agent / LLM 调用都内嵌在每个 `crm.exe` 的本地 FastAPI 里（只监听 127.0.0.1），该后端横向连中央 Postgres、纵向连 LLM。上云时把这个后端从"每客户端 loopback"提升为"一个中央服务"，DB 换 RDS，壳丢掉。

---

## 1. 部署拓扑

```
                          LAN（店内局域网）
  ┌────────────────────────────────────────────────────────────┐
  │                                                              │
  │  [Sales A 机器]        [Sales B 机器]        [Manager 机器]   │
  │  ┌──────────┐          ┌──────────┐          ┌──────────┐    │
  │  │ crm.exe  │          │ crm.exe  │          │ crm.exe  │    │
  │  │ FastAPI  │          │ FastAPI  │          │ FastAPI  │    │
  │  │ +webview │          │ +webview │          │ +webview │    │
  │  └────┬─────┘          └────┬─────┘          └────┬─────┘    │
  │       │  TCP 5432 (SQL/scram)   │                 │          │
  │       └─────────────┬──────────┴─────────────────┘          │
  │                     ▼                                        │
  │            ┌──────────────────┐                              │
  │            │  database.exe    │   ← 常开的一台机器            │
  │            │  Postgres server │                              │
  │            │  + pgdata (持久)  │                              │
  │            └──────────────────┘                              │
  └────────────────────────────────────────────────────────────┘
        每个 crm.exe 各自 ──► Internet ──► LLM（OpenAI 兼容）
```

- **中央**：`database.exe` 跑在一台常开机器上（manager 机 / 店内一台固定 PC），是全店唯一的真相源。
- **客户端**：每个 sales / manager 跑一份 `crm.exe`，配置里填中央 DB 的 `IP:端口`。
- **数据共享靠 DB**：`PROJECT.md` 里的"sales 只看自己客户 / manager 改归属"全部基于这张共享 Postgres 才能成立。
- **LLM 各连各的**：每个 `crm.exe` 用本地配置的 `base_url / key / model` 直连 LLM，互不影响。

---

## 2. `database.exe` 架构

目标：一个程序，在常开机器上提供一个对局域网可见的 Postgres 服务。

```
database.exe（onedir 分发，常开机器）
┌──────────────────────────────────────────────┐
│ launcher.py（入口，PyInstaller 打包）           │
│  ├─ 首次运行：                                  │
│  │    initdb → 创建 ./data/pgdata               │
│  │    设 superuser 密码                         │
│  │    改 postgresql.conf: listen_addresses='*' │
│  │    写 pg_hba.conf: 仅放行 LAN 网段 + scram   │
│  │    建应用角色 crm_app + 数据库 dealer_crm    │
│  ├─ 每次运行：pg_ctl start                       │
│  ├─（可选）系统托盘：显示状态 / 本机 LAN IP:端口 │
│  └─ 退出：pg_ctl stop（优雅关库）                │
│                                                │
│ 捆绑：PostgreSQL 便携二进制（bin/ lib/ share/）  │
│ 持久：./data/pgdata —— 必须在 exe 外、跨次保留   │
└──────────────────────────────────────────────┘
```

### 关键点
- **用官方便携二进制**：取 PostgreSQL 的 Windows zip 版（含 `bin/lib/share`，无需安装器），作为 PyInstaller 的 data 一起打包。
- **数据目录必须持久**：`pgdata` 放在 exe 同级 `./data/` 或 `%PROGRAMDATA%\dealer-crm\pgdata`，**绝不能**放在 onefile 解压的临时目录（那个每次启动重建、退出删除，会丢库）。→ 这也是 `database.exe` **建议用 onedir 而非 onefile** 打包的原因（onedir = 一个文件夹，含 exe + 二进制 + 持久 data）。
- **首次 vs 后续**：launcher 检测 `pgdata` 是否存在；不存在走 initdb 全套，存在则直接 `pg_ctl start`。
- **网络配置**：`listen_addresses='*'` 让 LAN 可连；`pg_hba.conf` 限定到本店网段（如 `192.168.1.0/24`）并强制 `scram-sha-256`，不开 `trust`。
- **schema 谁建**：见 §8 —— 迁移由后端拥有，`database.exe` 只负责把空库和角色准备好。

---

## 3. `crm.exe` 架构

目标：每个 sales 机器上的一个桌面程序，内含完整后端 + 前端 + 窗口壳。

```
crm.exe（单个 sales 机器）
┌────────────────────────────────────────────────────┐
│  pywebview 窗口（Windows 系统自带 WebView2）          │
│        │  指向 http://127.0.0.1:8756                 │
│        ▼                                             │
│  ┌──────────────────────────────────────────────┐  │
│  │ FastAPI（uvicorn，仅绑 127.0.0.1，回环）        │  │
│  │                                                │  │
│  │  ① StaticFiles  → React dist/（SPA 界面）       │  │
│  │  ② /api 路由层  （REST 端点）                   │  │
│  │  ③ Auth 中间件  （JWT 校验 + 角色 + 归属隔离）   │  │
│  │  ④ Service 层   （customer/inventory/outreach/  │  │
│  │                   style 业务逻辑）              │  │
│  │  ⑤ Agent 层 + LLMClient ───────► Internet(LLM)  │  │
│  │  ⑥ Data 层（SQLAlchemy session）──► LAN Postgres│  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  本地配置：DB host:port / app 角色凭据 / LLM 配置      │
└────────────────────────────────────────────────────┘
```

### 分层职责
1. **窗口壳（pywebview）**：开一个原生系统 webview 窗口，指向本进程内的 `127.0.0.1:8756`。用 Windows 自带 Edge WebView2，不打包 Chromium，体积小、外观像独立桌面 app。
2. **HTTP 服务（FastAPI / uvicorn）**：进程内起服务，**只绑回环地址**（外部连不到这个客户端，保证隔离）。
3. **静态前端**：React（Vite）build 出的 `dist/` 由 FastAPI `StaticFiles` 托管在 `/`；前端只请求相对路径 `/api/...`（为上云换域名零成本）。
4. **Auth 中间件**：校验应用层 JWT，注入当前用户 + 角色，对所有客户相关查询强制 `assigned_sales_id = 当前用户`（manager 可绕过）。
5. **Service 层**：`PROJECT.md` §6 的业务（录入 / 更新 / inventory / 风格 / 复访外联）。
6. **Agent 层 + LLMClient**：`PROJECT.md` §7 的 5 个 LLM 职责，统一走 `LLMClient(base_url, api_key, model)`。**运行在客户端**——每个 sales 用自己的 LLM 配置。
7. **Data 层**：SQLAlchemy + asyncpg/psycopg，连中央 Postgres。

### 启动顺序（壳内）
`shell.py`（PyInstaller 入口）→ 在后台线程起 uvicorn(FastAPI) → 等端口就绪 → `webview.create_window(url="http://127.0.0.1:8756")` → 进入 webview 事件循环 → 关窗时停 uvicorn。

---

## 4. 认证与权限（两级）

| 级别 | 谁认证谁 | 机制 |
|------|---------|------|
| **DB 级** | `crm.exe` → Postgres | 所有客户端共用一个**应用角色** `crm_app`（密码由部署 `database.exe` 的人分发）。`pg_hba` 限 LAN 网段 + scram。 |
| **应用级** | sales / manager → 应用 | `users` 表存邮箱 + 密码哈希（argon2/bcrypt）。登录签发 **JWT**；FastAPI 按角色 + `assigned_sales_id` 做数据隔离。 |

- Postgres 只看到一个 `crm_app` 在连；真正的"谁是谁、能看谁"由应用层 JWT + 查询过滤决定。
- 这是标准做法，避免给每个 sales 建独立 Postgres 角色（MVP 不值得）。
- **无状态**：JWT 不依赖客户端本地 session 文件，多客户端 / 上云都不用改。

---

## 5. 配置与密钥管理

`crm.exe` 首次运行需要的配置（本地存储）：

| 配置 | 例子 | 存哪 |
|------|------|------|
| DB 连接 | `host=192.168.1.10 port=5432 db=dealer_crm` | 本地 config |
| app DB 角色凭据 | `crm_app` / `<password>` | **OS 凭据库**（Windows Credential Manager，经 `keyring`） |
| LLM 配置 | `base_url / api_key / model` | base_url/model → config；`api_key` → OS 凭据库 |
| 监听端口 | `127.0.0.1:8756` | 默认值，可改 |

- 非密配置放 `%APPDATA%\dealer-crm\config.json`；**密钥（DB 密码、LLM key）走 OS 凭据库**，不落明文。
- **一切走配置、零硬编码**：DB 串、LLM 参数、监听地址端口都是配置项——这是云迁移能平滑的前提（桌面填本地值，云上换 RDS 端点 + 云 LLM，代码不动）。

---

## 6. 首次运行流程

### `database.exe`（部署机，一次性）
1. 检测无 `pgdata` → `initdb`，设 superuser 密码。
2. 配置 `postgresql.conf`（`listen_addresses`、`port`）与 `pg_hba.conf`（LAN 网段 + scram）。
3. 建数据库 `dealer_crm` 与应用角色 `crm_app`。
4. `pg_ctl start`。
5. 显示**本机 LAN IP:端口** + `crm_app` 凭据，交给各 sales 填进 `crm.exe`。
6. 之后每次：直接 `pg_ctl start`。

### `crm.exe`（每个 sales，一次性）
1. 设置页：填 DB `host:port` + `crm_app` 凭据 + LLM `base_url/key/model`。
2. 自检：测 DB 连接、ping LLM。
3. **首启自动跑迁移**（见 §8，带 advisory lock 防并发）。
4. 保存配置（密钥入凭据库）。
5. 应用登录页 → sales/manager 用自己邮箱密码登录。
6. 之后每次：直接到登录页。

> 首个 manager 账号：由 `database.exe` 在建库时 seed 一个初始 manager（默认凭据，首登强制改密），或由第一个连上的 `crm.exe` 引导创建。

---

## 7. 关键请求时序

**登录**
`React 登录表单 → POST /api/auth/login → Service 查 users 表(验 argon2) → 签发 JWT → 前端存内存/会话 → 后续请求带 Bearer`

**对话式录入（PROJECT §6.2）**
`前端聊天框 → POST /api/intake/chat（带历史）→ Intake Agent 调 LLM(tool-call) 抽字段 → 缺字段则反问 → 返回结构化草稿给前端确认 → 用户确认 → POST /api/customers（ORM insert 客户 + 名下 customer_car）`
（模型不碰 raw SQL；写入是确定性 ORM。）

**复访外联（PROJECT §6.6，核心流程）**
```
sales 点"运行规则"
   → POST /api/outreach/run {rule_id}
   → Rule Parser Agent: 规则文本 → JSON 谓词(列白名单校验)
   → 后端编译成 parameterized SQL（join customers ⨝ customer_car）
   → 查命中客户 ∧ last_contacted_at 超 cadence_days
   → 对每人: Email Composer Agent 综合
        [客户+note+偏好] × [inventory 匹配] × [email_style.md]
   → 草稿入 email_drafts(status=pending)
   → 前端 inbox 展示 → sales 编辑/approve
   → approve: 标记 approved + 更新 last_contacted_at + 记 interactions
   → sales 手动 copy 发送（MVP 不真发）
```

---

## 8. Schema 落地与迁移

- **迁移归后端拥有**：Alembic 迁移脚本放在后端代码里（schema 跟着应用走，桌面与云共用同一套）。
- **`database.exe` 只准备空壳**：建空库 `dealer_crm` + 角色，不建表。
- **首个连上的 `crm.exe` 跑 `alembic upgrade head`**：用 Postgres **advisory lock** 串行化，避免多客户端同时首启时并发建表。后续启动迁移是幂等的（已是最新则跳过）。
- 上云时迁移在部署流水线里跑，行为一致。
- 表结构见 `PROJECT.md` §5（含本轮新增的 `customer_car` 一对多、`sample_messages` / `style_profiles` 双通道）。

---

## 9. 代码组织（monorepo）

```
dealer-crm/
├─ backend/                 # FastAPI 后端（桌面 + 云 共用，核心资产）
│  ├─ app/
│  │  ├─ main.py            # FastAPI 实例 + 路由挂载 + StaticFiles
│  │  ├─ config.py          # 读环境变量/配置（DB、LLM、监听）
│  │  ├─ db.py              # SQLAlchemy engine/session
│  │  ├─ auth/              # JWT、密码哈希、依赖注入(当前用户/角色)
│  │  ├─ models/            # ORM 模型(users, customers, customer_car, …)
│  │  ├─ schemas/           # Pydantic I/O 模型
│  │  ├─ api/               # 路由: auth, customers, inventory,
│  │  │                     #        intake, outreach, style
│  │  ├─ services/          # 业务逻辑层
│  │  ├─ agents/            # Intake/Update/RuleParser/EmailComposer/
│  │  │                     #   StyleSummarizer + 工具定义
│  │  └─ llm/               # LLMClient(OpenAI 兼容) 抽象层
│  └─ alembic/              # 迁移脚本
│
├─ frontend/                # React (Vite) SPA
│  ├─ src/
│  └─ dist/                 # build 产物，打包进 crm.exe
│
├─ desktop/                 # crm.exe 壳与打包
│  ├─ shell.py              # 起 uvicorn(线程) + pywebview 窗口
│  └─ crm.spec              # PyInstaller 配置（含 frontend/dist 资源）
│
├─ database_app/            # database.exe
│  ├─ launcher.py           # initdb/配置/pg_ctl 生命周期 + 托盘
│  ├─ postgres/             # 便携 PostgreSQL 二进制(打包资源)
│  └─ database.spec         # PyInstaller 配置(onedir)
│
└─ docker-compose.yml       # 本地开发用(db + 后端热重载)，非分发物
```

> `backend/` 是从桌面到云不变的内核。`desktop/` 和 `database_app/` 是桌面阶段专属、上云即弃。

---

## 10. 打包

### `crm.exe`
- **PyInstaller**，入口 `desktop/shell.py`。
- 把 `frontend/dist/` 作为 `--add-data` 打进去，FastAPI `StaticFiles` 指向解包后的相对路径。
- 依赖 **WebView2 运行时**（Win10/11 多自带）；缺失则随附 Evergreen Bootstrapper 引导安装。
- 体积小（不带 Chromium），可 onefile 或 onedir。

### `database.exe`
- **PyInstaller onedir**，入口 `database_app/launcher.py`。
- 便携 PostgreSQL 二进制作为资源；运行时定位到解包目录调用 `initdb` / `pg_ctl`。
- **`pgdata` 必须指向持久外部目录**（exe 同级 `./data` 或 `%PROGRAMDATA%`），不在解包临时目录。
- 分发为一个文件夹（或 zip），里面就一个 `database.exe` + 依赖 + `data/`。

> "两个 exe" = 两个可执行程序；onedir 下每个程序是"一个 exe + 同目录依赖"，属正常形态。

---

## 11. 网络与安全

- **端口**：Postgres `5432`（可配）对 LAN；每个 `crm.exe` 的 FastAPI 在 `127.0.0.1:8756` 仅回环，外部不可达。
- **`pg_hba`**：仅放行店内网段 + `scram-sha-256`，禁 `trust`。
- **防火墙**：`database.exe` 那台机需放行入站 5432（仅 LAN）。
- **TLS**：LAN MVP 可暂不开 Postgres TLS；但库里是客户 PII，建议尽早开（尤其若机器跨子网）。云阶段 RDS 强制 TLS。
- **密钥**：DB 密码、LLM key 入 OS 凭据库，不落明文。
- **回环隔离**：每个客户端后端只绑 127.0.0.1，sales 之间无法互相访问彼此的 `crm.exe`，隔离只在共享 DB 这一层用应用逻辑保证。

---

## 12. 备份与运维（重要）

DB 现在是全店唯一真相源，单点风险需正视：

- **定期 `pg_dump`**：`launcher.py` 可挂一个每日定时 dump 到本机另一目录 / 网络盘。
- **pgdata 不可随意删**：onedir 升级时只换程序文件，保留 `./data`。
- **常开机要求**：`database.exe` 那台机关机 = 全店离线，部署时要选一台稳定常开的。
- **升级路径**：换 Postgres 大版本需 `pg_upgrade` 或 dump/restore，写进运维说明。

---

## 13. 云迁移路径（保留 / 变更对照）

| 组件 | 桌面阶段 | 云阶段 | 改动量 |
|------|---------|--------|--------|
| FastAPI 后端 | 每客户端内嵌，绑 127.0.0.1 | **中央服务**，ECS Fargate，绑 0.0.0.0，ALB 前置 | 仅配置（监听地址 + DB 串），代码近乎不动 |
| Postgres | `database.exe` 便携版（LAN） | **RDS**，TLS 强制 | 改连接串 |
| React 前端 | StaticFiles 由本地后端托管 | S3 + CloudFront 或后端托管 | 不动（已用相对 `/api`） |
| 窗口壳 | pywebview | **丢弃**，浏览器访问 | 删 `desktop/` |
| 认证 | JWT（应用级） | JWT 不变 | 不动 |
| LLM key | 各客户端本地 | 后端环境变量集中 | 配置迁移 |
| Agent / 业务 | 客户端进程内 | 后端进程内（可拆后台任务/队列） | 基本不动，按需异步化 |

平滑迁移的四条纪律（从第一行代码就遵守）：
1. 后端无状态（JWT，不依赖本机内存/文件）。
2. 全配置走环境变量 / 配置项，零硬编码。
3. 前端只认相对 `/api`，不写死 `localhost`。
4. DB 访问层(SQLAlchemy)不绑部署形态，便携 PG 与 RDS 同一套。

---

## 14. 技术栈汇总

| 层 | 选型 |
|----|------|
| 前端 | React + Vite（SPA，相对 `/api`） |
| 桌面壳 | pywebview（系统 WebView2） |
| 后端 | Python + FastAPI + uvicorn |
| ORM / 迁移 | SQLAlchemy + Alembic |
| DB | PostgreSQL（桌面=便携版打包，云=RDS） |
| 认证 | JWT + argon2/bcrypt |
| LLM | OpenAI 兼容 `LLMClient(base_url, key, model)` |
| 密钥存储 | OS 凭据库（keyring） |
| 打包 | PyInstaller（crm onefile/onedir，database onedir） |
| 开发 | docker-compose（db + 后端热重载） |

---

## 15. 假设与待确认

1. **单一 LAN 子网**，`database.exe` 那台机常开且 IP 稳定（建议设静态 IP）。
2. sales 机器是 **Windows + WebView2 可用**（缺失则随附引导）。
3. **共享 `crm_app` 角色**对 MVP 可接受（不为每 sales 建独立 PG 角色）。
4. `database.exe` 由谁部署、跑在哪台机——需指定一台责任机器。
5. **DB 备份策略**需落实（单一真相源，见 §12）。
6. 首个 manager 账号的初始化方式（seed 默认账号首登改密 vs 首个客户端引导）——倾向前者。

确认或纠正以上后，下一步可以三选一落地：① backend 骨架（FastAPI + SQLAlchemy 模型 + auth + LLMClient）；② `database.exe` 的 `launcher.py`（initdb/配置/pg_ctl 全流程）；③ `crm.exe` 的 `shell.py` + PyInstaller spec。
