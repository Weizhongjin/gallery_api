# AIGC 模特图生成功能设计（可插拔模型网关，首发 Seedream）

- 日期：2026-04-19
- 分支：feature/aigc-nano-banana-ideas
- 适用项目：gallery-api + frontend_v2
- 设计目标：在现有运营端中新增可控、可审计、可扩展的 AI 模特图生产能力，首版采用“后端任务中心 + Celery 异步编排”。

## 1. 背景与目标

当前图库系统已具备商品、资产、检索、标签、画册等能力，但缺少“从平铺图快速产出可运营模特图”的生产能力。

首版目标：

1. 支持基于平铺原图 + 参考模特图生成模特图（默认 2 张候选）。
2. 必须人工审核后才可入正式资产并绑定商品。
3. 默认启用人脸去标识化（可手动关闭）。
4. 所有 AI 产物必须有不可删除的 `AI生成` 标识。
5. 形成模板化提示词体系并可运营管理（版本、发布、回滚）。
6. 全链路可追溯（输入、模板版本、模型参数、审核动作）。
7. 模型层实现可插拔解耦，首发接入火山引擎 Seedream，后续可平滑切换其它模型。

## 2. 非目标（V1 不做）

1. 不做“仅平铺图无参考图”的主流程（质量不稳定）。
2. 不做多模型自动路由与成本自动结算的强依赖。
3. 不做二审制（V1 为单人审核）。
4. 不做自动上架（必须人工审核通过）。

> 说明：成本核算模块保留扩展点，但不作为 V1 上线阻塞项。

## 3. 关键业务约束（已确认）

1. 参考图来源：库内广告图 + 用户上传（上传需授权声明勾选留痕）。
2. 生成数量：默认并固定 2 张候选图（首版）。
3. 审核机制：单人审核。
4. 入库策略：审核通过后直接加入对应商品 asset。
5. 来源标识：`AI生成` 标签不可删除。
6. 前端入口：检索结果中平铺图支持“用此平铺图生成模特图”。
7. 输入图片：必须使用原图链路（`original_uri`），禁止以缩略图/展示图参与生成。
8. 长任务超时：AIGC 任务执行超时需大于 10 分钟（建议默认 15 分钟，允许配置到 20 分钟）。
9. 模型能力：首发 provider 为 `seedream_ark`，默认模型 `doubao-seedream-4-5-251128`。

## 4. 总体方案

采用“任务中心式”架构：

1. 前端只负责发起任务、查看状态、执行审核。
2. 后端统一负责编排：参数校验 -> 模板渲染 -> 调用模型网关 -> 候选持久化 -> 审核态流转。
3. Celery 异步执行生图任务，避免请求阻塞与超时。
4. 候选图与正式资产分层，未审核候选不得进入正式 `asset`。

## 4.1 模型网关与可插拔 Provider

1. 新增 `AigcProvider` 抽象接口，统一 `generate()` 入参与返回结构。
2. 通过 `provider_registry` 按 `provider_key` 路由到具体实现，业务层不直接依赖某个 SDK。
3. V1 默认 provider：`seedream_ark`，后续可挂 `openrouter_nano_banana`、`internal_sd` 等实现。
4. 任务表记录 `provider` / `model_name` / `provider_profile`，保证复盘可追溯。
5. 密钥仅从环境变量读取，不允许硬编码到代码、文档和日志。

## 4.2 Seedream（首发）调用约束

> 参数基线参考：`~/Desktop/inbox/火山引擎Seedream虚拟试穿方案.md`（密钥信息仅作本地配置，不进入仓库）。

1. 平台：Volcengine Ark，Base URL 使用 `https://ark.cn-beijing.volces.com/api/v3`。
2. 默认模型：`doubao-seedream-4-5-251128`（保留配置切换到 5.x 的能力）。
3. 输入图顺序固定：`image[0]=参考模特图`，`image[1]=平铺服装图`。
4. 默认分辨率：`2K`，`sequential_image_generation=disabled`，`stream=false`。
5. 首版推荐 `response_format=url` 后回源下载并入库存储，避免上游链接过期影响审核。

## 5. 端到端业务流程

1. 运营从商品管理或图片检索进入 AI 生图页。
2. 选择商品、平铺原图、参考图（库内或上传），确认模板与去标识化开关。
3. 提交后创建 `aigc_task`，状态 `queued`。
4. Celery Worker 拉取任务，状态 `running`。
5. 任务完成后生成 2 张候选图，状态置为 `review_pending`。
6. 审核员选择候选并执行通过/驳回。
7. 通过：候选转正式 `asset`，绑定商品并强制打 `AI生成` 标签，任务置 `approved`。
8. 驳回：记录原因，任务置 `rejected`。
9. 失败：任务置 `failed`，保留错误码和重试记录。

状态机：

- `queued -> running -> review_pending -> approved`
- `queued -> running -> review_pending -> rejected`
- `queued -> running -> failed`

## 6. 数据模型设计（新增）

### 6.1 aigc_task

字段建议：

- `id` (UUID, PK)
- `product_id` (FK)
- `flatlay_asset_id` (FK)
- `flatlay_original_uri` (string, 必填)
- `reference_source` (`library|upload`)
- `reference_asset_id` (FK, 可空)
- `reference_original_uri` (string, 可空)
- `reference_upload_uri` (string, 可空)
- `face_deidentify_enabled` (bool, default true)
- `candidate_count` (int, default 2)
- `template_id` (FK)
- `template_version` (int)
- `status` (`queued|running|review_pending|approved|rejected|failed`)
- `provider` (string, e.g. `seedream_ark`)
- `model_name` (string)
- `provider_profile` (string, e.g. `seedream-tryon-v1`)
- `timeout_seconds` (int, default 900)
- `created_by`, `reviewed_by`, `reviewed_at`
- `error_code`, `error_message`
- `created_at`, `updated_at`

### 6.2 aigc_task_candidate

- `id` (UUID, PK)
- `task_id` (FK)
- `seq_no` (int)
- `image_uri` (string)
- `thumb_uri` (string)
- `width`, `height`, `file_size`
- `is_selected` (bool)
- `created_at`

### 6.3 aigc_task_prompt_log

- `id` (UUID, PK)
- `task_id` (FK)
- `template_id`, `template_version`
- `system_prompt`, `user_prompt`, `negative_prompt`
- `request_payload_json`, `response_meta_json`
- `created_at`

### 6.4 aigc_authorization_log

- `id` (UUID, PK)
- `task_id` (FK)
- `uploader_user_id`
- `consent_text_version`
- `consent_checked` (must be true)
- `ip`, `user_agent`
- `created_at`

### 6.5 aigc_candidate_feedback

- `id` (UUID, PK)
- `candidate_id` (FK)
- `score` (1-5)
- `comment`
- `user_id`
- `created_at`

### 6.6 prompt_template / prompt_template_version

- 模板主表：名称、状态（启用/停用）、默认标记、创建人。
- 版本表：模板内容、变量定义、版本号、发布状态、发布时间。

## 7. API 设计（V1）

### 7.1 任务接口

1. `POST /aigc/tasks`
- 功能：创建任务
- 校验：
  - 输入必须可解析到原图 URI
  - 上传参考图必须授权勾选
- 可选：`provider` / `model_name`（未传则走系统默认 Seedream）
- 返回：`task_id`, `status=queued`

2. `GET /aigc/tasks`
- 功能：任务列表（按状态、发起人、时间筛选）

3. `GET /aigc/tasks/{id}`
- 功能：任务详情（候选图、错误、模板版本、审核信息）

4. `POST /aigc/tasks/{id}/retry`
- 功能：失败任务重试（权限控制）

5. `GET /aigc/providers`
- 功能：返回当前可用 provider 与默认模型配置（供前端展示与灰度选择）

### 7.2 审核接口

1. `POST /aigc/tasks/{id}/approve`
- 入参：`selected_candidate_id`, `target_asset_type(model_set|advertising)`
- 行为：正式入库并绑定商品，写入不可删除 `AI生成` 标识

2. `POST /aigc/tasks/{id}/reject`
- 入参：`reason`
- 行为：写入拒绝原因，状态变更为 `rejected`

### 7.3 反馈接口

1. `POST /aigc/candidates/{candidate_id}/feedback`
- 入参：`score`, `comment`
- 用途：后续模板优化与效果评估

### 7.4 模板管理接口（管理员）

1. `GET /aigc/prompt-templates`
2. `POST /aigc/prompt-templates`
3. `POST /aigc/prompt-templates/{id}/publish`
4. `POST /aigc/prompt-templates/{id}/rollback`

## 8. Celery 编排与超时策略

### 8.1 队列与并发

- 队列名：`aigc_generate`
- 并发：`4`

### 8.2 执行步骤

1. `prepare_inputs`（拉取原图、校验权限）
2. `render_prompt_template`（模板渲染）
3. `call_model_provider`（调用 provider 适配器，V1=Seedream）
4. `store_candidates`（保存候选图）
5. `mark_review_pending`（任务转审核态）

### 8.3 超时与重试

- 任务软超时：`900s`（15 分钟，满足“至少 10 分钟以上”）
- 任务硬超时：`1200s`（20 分钟）
- Provider HTTP 超时：建议 `700s+`，确保长生成请求不中断
- 重试策略：仅对 `429/timeout/5xx` 指数退避，最多 2 次
- 幂等：同一 `task_id` 重入不重复产出候选

## 9. frontend_v2 整合设计

### 9.1 路由与导航

- 新增路由：`/ops/aigc`
- 新增侧栏菜单：`AI生图`
- 新增 Topbar 标题映射：`AI生图`

### 9.2 关键入口

1. 商品管理：商品行/卡新增“AI生图”动作，自动带入 `product_id`。
2. 图片检索：
- 若当前资产是 `flatlay`，显示按钮：`用此平铺图生成模特图`。
- 若非 `flatlay`，显示动作：`设为参考图`。

### 9.3 AI 生图页面结构

1. 任务创建区：商品、平铺原图、参考图、模板、去标识化、提交。
2. 任务队列区：状态筛选、失败重试、任务详情。
3. 候选审核区：2 张候选图、评分/评语、通过/驳回。
4. 模板入口：管理员可进入模板管理页（独立子页或抽屉）。

## 10. 权限与合规

1. 创建任务：登录用户可用。
2. 审核任务：运营角色可用。
3. 模板管理：管理员可用。
4. 上传参考图：必须授权声明勾选，否则禁止创建任务。
5. 面部去标识化：默认开启，可手动关闭，开关状态入审计。
6. `AI生成` 标识：不可删除。

## 11. 可观测性与审计

1. 日志维度：任务 ID、请求 ID、耗时、重试次数、错误码。
2. 审计事件：创建、重试、审核通过、审核驳回、模板发布。
3. 查询能力：按任务 ID 可完整回放输入、模板版本、输出、审核动作。

## 12. 测试与验收

### 12.1 测试

1. 单测：状态机、校验逻辑、审核逻辑、不可删除标识。
2. 集成：创建任务 -> Celery -> 审核 -> 入库绑定商品。
3. 异常：超时、限流、provider 失败、重复提交幂等。
4. 前端联调：检索平铺图入口、预填、审核回写展示。

### 12.2 验收标准（DoD）

1. 检索页平铺图可一键发起“用此平铺图生成模特图”。
2. 支持库内和上传参考图，上传必须授权勾选。
3. 默认生成 2 张候选并进入审核。
4. 审核通过后直接进入商品资产可见。
5. `AI生成` 标识存在且不可删除。
6. 任务执行支持 10 分钟以上长超时。
7. 失败任务可重试且可查看原因。

## 13. 里程碑

1. M1（后端框架）：数据表、API、Celery 状态机、审计。
2. M2（前端整合）：新增 `/ops/aigc`、检索/商品入口、审核闭环。
3. M3（模板运营）：模板版本发布/回滚、评分反馈回流。
4. M4（优化预留）：成本核算与模型路由能力。

## 14. 风险与缓解

1. 质量不稳定：模板版本化 + 评分反馈闭环。
2. 长任务失败：15/20 分钟双层超时 + 限定重试。
3. 合规风险：授权留痕 + 默认去标识化 + 人工审核。
4. 运维风险：候选与正式资产分层，防止未审核数据污染。
