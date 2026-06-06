# 项目描述：AI-Augmented Dealership CRM

> 代号待定（暂称 `dealer-crm`）。一个面向汽车销售（sales）个人使用的、带 AI 能力的轻量 CRM。
> 本文档为 MVP 阶段的 project 描述与边界说明，作为后续开发的基线。

---

## 1. 背景与目标

与本地车行 sales 的交流暴露出三个真实痛点：

1. **现有 CRM 仅"能用"**：数据库交互笨拙，sales 要逐个手动搜索、发邮件 / 短信 / 打电话，没有任何自动化或辅助。
2. **录入信息维度太少**：客户档案结构化字段稀薄，缺少能支撑个性化外联的"软信息"。
3. **获客 / 外联（posting）成本高**：撰写有针对性的推销内容耗时，缺乏对老客户的系统性持续触达。

**目标**：构建一个 AI 增强的个人 CRM，把"录入 / 更新 / 老客户复访外联"这三个高摩擦环节分别用对话式录入、结构化辅助更新、规则筛选 + 风格化邮件生成来降本。MVP 聚焦单个 sales 的私下使用，不涉及团队协作与汇报。

---

## 2. MVP 范围与边界

### 范围内（In Scope）
- 登录与角色权限（sales / manager）
- 客户、库存（inventory）、备注、外联规则的数据模型
- **对话式新客户录入**（agent 抽取字段 → 后端确定性 insert）
- **客户更新**（前端手动 + agent 辅助）
- **inventory 管理**（车行现有可售车辆）
- **风格学习**：sales 选取样例邮件 → agent 整理成统一 `style.md`
- **老客户回顾**：自然语言规则 → AI 解析为结构化筛选 → 命中客户 → 风格化邮件草稿 → 待审队列（approve）
- 邮件 **仅生成草稿**，sales 手动 copy 后自行发送

### 明确不在 MVP（Out of Scope，见第 10 节 Roadmap）
- 真实邮件发送（Gmail / SMTP / Outlook 集成）
- CASL 合规（consent 记录、退订链接）—— 因为 MVP 不真发邮件，暂不需要
- 后台定时调度（scheduler / cron worker）—— MVP 用 sales 主动触发代替
- 历史数据导入 / 现有 CRM 迁移
- 团队协作、汇报、多 sales 数据互通
- 多 LLM provider 适配（MVP 只做 OpenAI 兼容格式）

---

## 3. 用户与权限模型

两种角色，权限在**后端强制**（不依赖前端隐藏）：

| 角色 | 能力 |
|------|------|
| **sales** | 只能 CRUD / 查看 **分配给自己** 的客户；管理自己的样例邮件、风格档案、外联规则；查看 inventory |
| **manager** | sales 的全部能力，外加：查看全部客户、**改某个客户归属哪个 sales**（reassign `assigned_sales_id`） |

- 客户数据隔离的核心是 `customers.assigned_sales_id`。每个面向客户的查询都强制带上 `assigned_sales_id = current_user.id`（manager 角色可绕过此约束）。
- MVP 是"私下使用"，但权限模型从一开始就做对，避免后期重构。

---

## 4. 系统架构

容器拆分（DB 与应用分离，符合你的要求）：

```
┌─────────────┐      ┌──────────────────────────┐      ┌──────────────┐
│  React 前端  │ ───▶ │  Python 后端 (FastAPI)    │ ───▶ │  Postgres    │
│  (Vite/SPA) │ HTTP │  - REST API               │ ORM  │  (独立容器)   │
└─────────────┘      │  - Auth / 权限             │      └──────────────┘
                     │  - Agent 编排 + 工具        │
                     │  - LLM Client (OpenAI兼容) │ ───▶  LLM (base_url/key/model)
                     └──────────────────────────┘
```

- **db 容器**：Postgres，独立 volume 持久化。
- **app 容器**：Python 后端，承载 API、鉴权、agent 编排、LLM 调用。
- 前端 React（开发期独立 dev server，生产期可由后端或静态托管提供）。
- `docker-compose` 编排，db 与 app 各自一个 service。

### 技术栈
- **前端**：React（Vite）
- **后端**：Python + **FastAPI**（异步、对 agent tool-calling 与流式响应友好）
- **DB**：Postgres（建议配 SQLAlchemy + Alembic 做 ORM 与迁移）
- **LLM**：OpenAI 兼容接口，配置项 `base_url` / `api_key` / `model`，封装在一个 `LLMClient` 抽象层后面，便于后期换 provider

---

## 5. 数据模型（初版 Schema）

> 字段为初版建议，开发时再细化类型 / 索引。

**users**
- `id`, `email`(unique), `password_hash`, `name`, `role`(sales|manager), `created_at`

**customers**
- `id`, `assigned_sales_id`(FK users)
- 联系方式：`full_name`, `email`, `phone`
- 软信息：`note`(text，sales 记录的非公式化特点，如"大学刚毕业""两个孩子的家庭""喜欢科技")
- 触达状态：`last_contacted_at`
- `created_at`, `updated_at`

**customer_car**（客户名下车辆，一对多 —— 一个客户可有多辆）
- `id`, `customer_id`(FK customers)
- `make`, `model`, `year`, `ownership_type`(own|lease|finance), `lease_end_date`
- `is_primary`(bool，标记主力车，便于展示与默认匹配)
- `created_at`, `updated_at`
- 注意：这是**客户自己拥有 / 租赁的车**，与 `inventory`（车行待售库存）是两张完全独立的表

**interactions**（接触历史 / 触达日志，支撑去重与复盘）
- `id`, `customer_id`(FK), `sales_id`(FK), `channel`(email|phone|sms|note), `summary`, `created_at`

**inventory**（车行现有可售车辆）
- `id`, `make`, `model`, `year`, `trim`, `mileage`, `price`, `vin`, `status`(available|sold), `added_at`
- MVP 默认 **全行共享**（这是车行的车，不按 sales 隔离）

**sample_messages**（sales 主动喂入的优质样例原文，覆盖 email 与 text）
- `id`, `sales_id`(FK), `channel`(email|text), `raw_content`, `label`, `created_at`

**style_profiles**（风格总结 job 的产物，每个 sales × 每个通道一份最新）
- `id`, `sales_id`(FK), `channel`(email|text), `style_md`(text), `updated_at`
- 即每个 sales 维护两份：`email_style.md` 与 `text_style.md`

**outreach_rules**（老客户复访规则）
- `id`, `sales_id`(FK), `name`, `rule_text`(自然语言原文), `compiled_filter`(JSON 谓词，见 6.6), `cadence_days`(如 30), `active`, `created_at`

**email_drafts**（待审队列 / inbox）
- `id`, `sales_id`(FK), `customer_id`(FK), `rule_id`(FK, nullable), `subject`, `body`, `status`(pending|approved|dismissed), `created_at`, `approved_at`

---

## 6. 核心功能模块

### 6.1 认证与权限
邮箱 + 密码登录（哈希存储），签发 session/JWT。所有客户相关接口在后端按第 3 节规则校验归属。

### 6.2 客户录入（对话式 — 需求 3）
- sales 与 **Intake Agent** 自然语言对话（"新客户，叫 John，刚大学毕业，看 SUV，现在开一辆 2017 的 Civic，lease 明年三月到期……"）。
- agent 通过 **structured tool-call** 把对话抽成固定 schema 字段，缺字段时反问澄清。
- 抽取结果先展示给 sales **确认**，再由后端用 ORM 做确定性 insert。**模型不生成 / 不执行 raw SQL。**

### 6.3 客户更新（需求 5）
找到目标客户后，两条更新路径并存：
- **手动**：前端表单直接改字段。
- **agent 辅助**：对话描述变更（"他换了工作，预算提高了""note 加一句喜欢混动"），**Update Agent** 经 tool-call 产出字段 diff → sales 确认 → ORM update。
- 每次有意义的更新可写一条 `interactions` 记录。

### 6.4 Inventory 管理（需求 7）
- 车行现有车辆的表格 CRUD：增 / 改 / 标记售出。
- 供邮件生成时做"客户偏好 ↔ 在库车辆"的匹配（如 lease 快到期 + 偏好科技 → 推荐在库的某混动 SUV）。

### 6.5 风格学习
- sales 主动把写得好的 **email 和 text** 喂给系统，按通道存入样本库 `sample_messages`（`channel` = email | text）。
- 一个**独立的 Style Summarizer job** 读取样本库，按通道分别总结，产出 / 更新两份风格档案：
  - `email_style.md`（邮件语气、称呼、结构、签名、常用措辞）
  - `text_style.md`（短信的简短风格、口吻、缩写习惯等）
  - 两者写入 `style_profiles`（每个 sales × 每个通道一行，覆盖更新为最新版）。
- 触发方式：sales 喂入新样本后触发刷新（或手动点"重新总结"）。**不是后台定时**，与第 9 节触发原则一致。
- 这两份 `style_md` 作为后续邮件 / 短信生成的风格输入（MVP 外联生成先用 `email_style.md`）。

### 6.6 老客户回顾（需求 4 — 核心 AI 流程）
完整链路：

1. **设规则**：sales 用自然语言写规则（"车龄 > 5 年、lease 半年内到期、未在过去 30 天联系过"）。
2. **AI 解析筛选**：**Rule Parser Agent** 把规则解析成 **结构化 filter（JSON 谓词树）**，列名 / 操作符走**白名单校验**；后端把它编译成 **parameterized SQL** 执行。
   - 白名单覆盖 `customers` 与 `customer_car` 两表的可筛选列；涉及车辆条件（如 lease 到期、车龄）时按"客户名下**任一**车辆满足即命中"做 join。
   - 这样既满足"AI 解析 SQL 过滤条件"，又杜绝模型吐 raw SQL 带来的注入与脏查询风险。
3. **命中客户**：返回符合条件、且距 `last_contacted_at` 超过 `cadence_days` 的客户列表（cadence 去重）。
4. **生成邮件**：对每个命中客户，**Email Composer Agent** 综合 [客户字段 + note + 偏好] × [inventory 匹配] × [该 sales 的 `email_style.md`]，写出针对性草稿。
5. **审批发送**：草稿进入 `email_drafts` 待审队列（前端 inbox）。sales 过目、可编辑、approve；approve 后 **手动 copy 自行发送**，系统更新 `last_contacted_at` 并记一条 `interactions`。

> **MVP 触发方式**：sales 主动点"运行我的规则 / 今天该联系谁"。不做后台定时（Phase 2 再加 scheduler）。

---

## 7. AI Agent 设计

MVP 共 5 个 LLM 职责（4 个对话 / 任务型 agent + 1 个独立的总结 job），共享同一个 `LLMClient`（OpenAI 兼容），各自有独立的 system prompt 与工具集：

| Agent / Job | 职责 | 输出形式 |
|-------|------|----------|
| Intake Agent | 对话式抽取新客户字段（含名下车辆） | tool-call → 字段 JSON |
| Update Agent | 对话式产出客户 / 车辆字段 diff | tool-call → 字段 diff |
| Style Summarizer (独立 job) | 把样本库的 email / text 样例分别总结 | `email_style.md` + `text_style.md` |
| Rule Parser | 自然语言规则 → 结构化 filter | JSON 谓词树（白名单校验） |
| Email Composer | 生成针对性推销邮件草稿 | subject + body |

**LLM 抽象层**：所有 agent 走统一 `LLMClient(base_url, api_key, model)`。MVP 只支持 OpenAI 兼容格式；后期在该接口后增加适配器即可接入别的格式（见 Roadmap）。

---

## 8. 关键设计决策与风险

- **模型绝不碰 raw SQL**：写入走 tool-call + ORM；筛选走 structured filter + parameterized SQL。这是贯穿录入 / 更新 / 筛选三处的统一安全原则。
- **筛选列名白名单**：Rule Parser 只能引用预定义的可筛选列与操作符，非法字段直接拒绝。
- **AI 输出皆经人确认**：录入、更新、邮件都有 sales 的 approve 关口，模型不直接改库、不直接对外发声。
- **权限在后端**：数据隔离不靠前端。
- **风险点**：邮件质量与风格还原度依赖样例数量和 prompt；inventory 匹配逻辑 MVP 先做简单规则，效果不足再升级。

---

## 9. 我做的默认假设（请你确认 / 纠正）

1. **复访触发方式** = sales 主动触发，**非**后台定时（scheduler 入 Phase 2）。
2. **inventory** = 全行共享，不按 sales 隔离。
3. **note** 采用「customer 上一个持久 `note` 字段（记长期特点）+ 独立 `interactions` 表（记每次接触）」的组合，而非单一字段。
4. 登录 = 邮箱 + 密码（哈希）。
5. 邮件审批 = 前端一个 `email_drafts` 待审 inbox。

以上若有不对，告诉我，我改文档；没问题就可以进下一步（出 schema DDL / API 设计 / 或先搭 docker-compose 骨架）。

---

## 10. Roadmap（MVP 之后）

- **真实发送**：Gmail API / SMTP，以 sales 本人名义发送
- **CASL 合规**：consent 记录、退订链接、发送审计（真发邮件后必需）
- **后台调度**：常驻 worker 按 `cadence_days` 自动跑规则、生成草稿入队
- **多 LLM provider**：在 `LLMClient` 后加适配器，支持非 OpenAI 格式
- **历史数据导入**：从现有 CRM 导出迁移，反哺 schema
- **团队 / 协作**：跨 sales 视图、汇报、线索分配工作流
- **更强 inventory 匹配**：基于偏好向量 / 规则引擎的推荐
