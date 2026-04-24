# Gallery API 接口文档（中文）

更新时间：2026-04-24
服务地址（本地）：`http://127.0.0.1:8000`

## 1. 认证与用户

### POST `/auth/login`
- 说明：用户登录，返回 JWT。
- 请求体：
```json
{
  "email": "admin@qiaofei.local",
  "password": "Qf123456!"
}
```
- 响应：`{ "access_token": "...", "token_type": "bearer" }`

### GET `/auth/me`
- 说明：获取当前登录用户信息。
- 鉴权：`Bearer Token`

### 用户管理（admin）
- `POST /users`：创建用户
- `GET /users`：用户列表
- `PATCH /users/{user_id}`：更新用户
- `DELETE /users/{user_id}`：停用用户

## 2. 资产（Assets）

### POST `/assets/upload`
- 说明：上传单张图片并创建资产记录。

### POST `/assets/batch-ingest/storage`
- 说明：按对象存储前缀批量导入。
- 返回：`202 + job_id`

### GET `/assets`
- 说明：资产列表（支持按标签、类型、商品码过滤）。
- 常用参数：
  - `tag_ids`（可重复）
  - `asset_type`（`advertising|flatlay|model_set|unknown`）
  - `product_code`
  - `page` / `page_size`

### GET `/assets/{asset_id}`
- 说明：资产详情

### GET `/assets/{asset_id}/file`
- 说明：读取图片文件（`original/display/thumb`）

### PATCH `/assets/{asset_id}/tags`
- 说明：人工增删资产标签（`add/remove`）

### 资产与商品关系
- `GET /assets/{asset_id}/products`：查询关联商品
- `POST /assets/{asset_id}/products/bind`：绑定商品
- `DELETE /assets/{asset_id}/products/{product_code}`：解绑商品

### 重处理
- `POST /assets/{asset_id}/process`：单资产重跑（classify/embed）
- `POST /assets/reprocess`：批量重跑

## 3. 商品（Products）

### POST `/products/upsert`
- 说明：创建/更新商品主数据（按 `product_code`）。

### GET `/products`
- 说明：商品分页查询。
- 常用参数：
  - `q`：商品码/名称模糊搜索
  - `tag_ids`（可重复）：属性筛选（同维度 OR、跨维度 AND）
  - `has_assets`：仅返回至少已绑定 1 张图片资产的商品
  - `page` / `page_size`
- 说明补充：`TMPUID-*` 占位商品默认排序在列表后部。

### GET `/products/{product_id}`
- 说明：商品详情

### PATCH `/products/{product_id}`
- 说明：更新商品基本信息

### GET `/products/{product_id}/assets`
- 说明：该商品关联图片

### 标签相关
- `GET /products/{product_id}/tags`：查看商品标签
- `PATCH /products/{product_id}/tags`：人工维护商品标签
- `POST /products/{product_id}/tags/rebuild`：按关联资产标签重建聚合标签

### GET `/products/governance/summary`
- 说明：商品治理总览指标。
- 响应：`{ total_products, missing_all_assets, missing_flatlay, missing_model, missing_advertising, in_lookbook }`

### GET `/products/governance/items`
- 说明：治理问题商品池，支持按问题类型筛选。
- 参数：`problem`（`all|missing_all_assets|missing_flatlay|missing_model|missing_advertising`）、`q`（商品码/名称搜索）、`page` / `page_size`

### GET `/products/{product_id}/workbench`
- 说明：商品工作台聚合详情，包含基础信息、完整性状态、推荐动作、分组资产、AIGC 摘要、Lookbook 摘要、标签与质量问题列表。

### GET `/products/admin/unresolved-assets`
- 说明：查看未解析商品号的资产（运营排查）

### POST `/products/admin/sales/sync`
- 说明：从 `budan.orders` 同步销售原始数据，并重建商品销量汇总。
- 权限：admin / editor
- 行为：
  - 仅替换 `source = "budan"` 的销售原始记录
  - 保留其他历史手工来源（例如 legacy 表格导入）
  - 同步完成后会全量重建 `product_sales_summary`
- 兼容规则：
  - `sales_order_raw.source_order_id` 允许为空，兼容历史销售来源
  - 历史来源不强制补伪订单号，内部主键 `id` 仍可作为表内唯一标识

## 4. 分类与标签（Taxonomy）

### GET `/taxonomy`
- 说明：获取标签节点列表

### POST `/taxonomy/nodes`（admin）
- 说明：新增节点

### PATCH `/taxonomy/nodes/{node_id}`（admin）
- 说明：修改节点

### DELETE `/taxonomy/nodes/{node_id}`（admin）
- 说明：停用节点

### 候选标签
- `GET /taxonomy/candidates`（admin）：未审核候选
- `POST /taxonomy/candidates/{candidate_id}/promote`（admin）：提升为正式节点
- `DELETE /taxonomy/candidates/{candidate_id}`（admin）：丢弃候选

## 5. 检索（Search）

### GET `/search`
- 说明：属性检索（标签过滤）

### POST `/search/semantic`
- 说明：文本语义检索

### POST `/search/vector`
- 说明：以图搜图（上传图片）
- 说明补充：DashScope 模式下使用图片字节直传，避免本地私网 URL 不可达导致 500。

## 6. 画册（Lookbooks）

### 管理端
- `POST /lookbooks`
- `GET /lookbooks`
- `PATCH /lookbooks/{lb_id}`
- `POST /lookbooks/{lb_id}/publish`
- `DELETE /lookbooks/{lb_id}/unpublish`
- `POST /lookbooks/{lb_id}/items`
- `DELETE /lookbooks/{lb_id}/items/{asset_id}`
- `GET /lookbooks/{lb_id}/items`

### Section 编辑
- `GET /lookbooks/{lb_id}/sections`
- `POST /lookbooks/{lb_id}/sections/products`
- `PATCH /lookbooks/{lb_id}/sections/reorder`
- `POST /lookbooks/{lb_id}/sections/{section_id}/items`
- `DELETE /lookbooks/{lb_id}/sections/{section_id}`
- `DELETE /lookbooks/{lb_id}/sections/{section_id}/items/{asset_id}`

### GET `/lookbooks/{lb_id}/sections`
- 说明：返回编辑器所需的 section 结构。
- 兼容逻辑：
  - 已迁移的新数据以真实 `lookbook_product_section` 返回
  - 未迁移的 legacy `lookbook_item` 会被包装成 synthetic legacy section 一并返回
- 使用建议：
  - 前端应把 `product_id = null` 的 section 视为只读兼容分区

### POST `/lookbooks/{lb_id}/sections/products`
- 说明：按商品创建 section，并自动补入推荐图片。
- 权限：admin / editor
- 行为：
  - 同一商品在同一画册中不允许重复创建 section
  - 若商品没有关联图片，返回 `422`

### PATCH `/lookbooks/{lb_id}/sections/reorder`
- 说明：保存商品 section 的拖拽排序结果。
- 权限：admin / editor
- 请求体：
  ```json
  {
    "section_ids": ["uuid-1", "uuid-2", "uuid-3"]
  }
  ```
- 约束：
  - 必须包含当前画册下全部真实商品 section
  - 不允许缺失、重复或跨画册 section id
  - legacy synthetic section 不参与该接口

### POST `/lookbooks/{lb_id}/sections/{section_id}/items`
- 说明：向某个商品 section 追加图片。
- 权限：admin / editor
- 请求体：
  ```json
  {
    "asset_ids": ["uuid-1", "uuid-2"]
  }
  ```

### DELETE `/lookbooks/{lb_id}/sections/{section_id}`
- 说明：删除整个商品 section。
- 权限：admin / editor

### DELETE `/lookbooks/{lb_id}/sections/{section_id}/items/{asset_id}`
- 说明：删除 section 内某一张图，并自动维护 cover。
- 权限：admin / editor

### 访问授权
- `POST /lookbooks/{lb_id}/access`
- `DELETE /lookbooks/{lb_id}/access/{user_id}`
- `GET /lookbooks/{lb_id}/access`
- `GET /my/lookbooks`

### GET `/my/lookbooks/{lb_id}/items`
- 说明：buyer 端读取画册平铺输出。
- 行为：
  - 自动合并 section 图片与 legacy `lookbook_item`
  - 返回全局递增 `sort_order`

## 7. 任务（Jobs）

### GET `/jobs/{job_id}`
- 说明：查询异步任务状态与进度。

---

## 8. AIGC 模特图生成（AIGC）

AIGC 模块支持"平铺原图 + 参考图 → 模特图候选 → 人工审核 → 入商品资产"的完整生产闭环。

### 任务状态机

```
queued → running → review_pending → approved
                              └→ rejected
       → failed
```

### POST `/aigc/tasks`
- 说明：创建 AIGC 生成任务。
- 权限：admin / editor
- 请求体：
  ```json
  {
    "product_id": "uuid",
    "flatlay_asset_id": "uuid",
    "reference_source": "library|upload",
    "reference_asset_id": "uuid (library 时必填)",
    "reference_upload_uri": "s3://... (upload 时必填)",
    "consent_checked": true,
    "face_deidentify_enabled": true,
    "candidate_count": 2
  }
  ```
- `consent_checked` 必须为 `true`，否则返回 422。
- 说明补充：
  - `candidate_count` 仍可传入，但 provider 侧已兼容不再直接透传已废弃的 `n` 参数

### GET `/aigc/tasks`
- 说明：列出 AIGC 任务（支持按状态和商品筛选）。
- 权限：admin / editor / viewer
- 参数：`status`, `product_id`, `limit`, `offset`

### GET `/aigc/tasks/{task_id}`
- 说明：获取单个任务详情（含候选列表）。
- 权限：admin / editor / viewer

### POST `/aigc/tasks/{task_id}/approve`
- 说明：审核通过，选中候选入库为正式资产。
- 权限：admin / editor
- 请求体：
  ```json
  {
    "selected_candidate_id": "uuid",
    "target_asset_type": "model_set"
  }
  ```
- 通过后自动创建 `Asset`（`is_ai_generated=True`）并绑定商品。

### POST `/aigc/tasks/{task_id}/reject`
- 说明：驳回任务。
- 权限：admin / editor
- 请求体：`{ "reason": "质量不达标" }`

### POST `/aigc/candidates/{candidate_id}/optimize`
- 说明：基于已有候选图继续发起优化任务。
- 权限：admin / editor
- 请求体：
  ```json
  {
    "mode": "auto",
    "custom_prompt": null
  }
  ```
  或
  ```json
  {
    "mode": "custom",
    "custom_prompt": "增强面部真实感，修复手部和鞋子细节"
  }
  ```
- 行为：
  - `mode=auto`：自动拼接系统增强提示词，侧重服装纹理、面部、手部、鞋履、配饰合理性
  - `mode=custom`：在优化链路中叠加用户自定义提示词
  - 会保留优化 lineage，优化任务与来源 candidate / 来源 task 可追溯

### POST `/aigc/candidates/{candidate_id}/feedback`
- 说明：对候选图评分/评论。
- 权限：admin / editor
- 请求体：`{ "score": 1-5, "comment": "..." }`

### GET `/aigc/candidates/{candidate_id}/file`
- 说明：读取候选图缩略图或原图。
- 权限：admin / editor / viewer（支持 query token）
- 参数：
  - `kind=thumb|original`

### GET `/aigc/providers`
- 说明：列出可用的 AIGC 供应商。
- 权限：admin / editor / viewer

### 超时配置
- Celery 软超时：`AIGC_SOFT_TIMEOUT_SECONDS`（默认 900s / 15 分钟）
- Celery 硬超时：`AIGC_HARD_TIMEOUT_SECONDS`（默认 1200s / 20 分钟）

---

## 鉴权说明

- 除健康检查外，绝大多数接口需要 `Authorization: Bearer <token>`。
- Token 获取方式：`POST /auth/login`。
- 角色：
  - `admin`：全量管理
  - `editor`：运营编辑
  - `viewer`：只读

## 错误码约定

- `400`：参数错误
- `401`：未登录或凭证失效
- `403`：角色权限不足
- `404`：资源不存在
- `409`：冲突（如重复）
- `500`：服务内部错误
