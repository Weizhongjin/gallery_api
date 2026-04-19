# Changelog

## release1.2 - 2026-04-19

### Added
- AIGC 模特图生成完整闭环：
  - 新增 7 张 AIGC 数据表：`aigc_task`、`aigc_task_candidate`、`aigc_prompt_log`、`aigc_authorization_log`、`aigc_candidate_feedback`、`aigc_prompt_template`、`aigc_prompt_template_version`
  - `Asset` 表新增 `is_ai_generated` 不可逆标识（默认 `false`）
  - 可插拔 Provider 架构：`AigcProvider` 协议 + `provider_registry`，首发 `seedream_ark`
  - Celery 异步任务 `celery_aigc_generate`，软超时 900s / 硬超时 1200s
  - API 接口：`POST/GET /aigc/tasks`、审核/驳回、候选评分、供应商列表
  - 审核通过后自动创建 `Asset`（`is_ai_generated=True`）并绑定商品
- 搜索结果新增 `cover_asset_type` 字段，支持前端判断平铺图入口
- 前端 `frontend_v2` 新增 `/ops/aigc` 页面，支持任务列表、候选审核、评分反馈
- 前端检索页平铺图显示"用此平铺图生成模特图"入口
- 前端商品页显示"AI生图"快捷入口

### Changed
- 新增 `volcengine-python-sdk[ark]` 依赖
- 新增配置项：`VOLC_ARK_BASE_URL`、`VOLC_ARK_API_KEY`、`AIGC_DEFAULT_PROVIDER`、`AIGC_MODEL_NAME`、`AIGC_PROVIDER_TIMEOUT_SECONDS`、`AIGC_SOFT_TIMEOUT_SECONDS`、`AIGC_HARD_TIMEOUT_SECONDS`

### Verification
- 后端测试：20 AIGC 相关测试全部通过
- 前端测试：39 passed，build 成功

## release1.1 - 2026-04-18

### Added
- 新增销售数据表与迁移：
  - `sales_order_raw`
  - `product_sales_summary`
- 新增销售同步能力：
  - `POST /products/admin/sales/sync`
  - `scripts/sync_sales_from_budan.py`
- 新增 `BUDAN_DATABASE_URL` 配置项。
- 商品与商品检索返回中新增 `sales_total_qty` 字段。
- 商品列表与商品维度检索新增销量筛选参数：
  - `sales_min`
  - `sales_max`

### Changed
- API 应用版本升级到 `1.1.0`。
- 商品列表排序逻辑中继续保留 `TMPUID-*` 置后策略，并支持按销量排序。

### Verification
- 测试通过：`98 passed`（`pytest -q`，2026-04-18 本地执行）。

## release1.0 - 2026-04-12

### Baseline
- 运营端定版能力：资产管理、标签体系、商品管理、向量检索、Lookbook、任务查询。
