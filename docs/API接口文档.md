# Gallery API 接口文档（中文）

更新时间：2026-04-12  
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

### GET `/products/admin/unresolved-assets`
- 说明：查看未解析商品号的资产（运营排查）

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
- `PATCH /lookbooks/{lb_id}`
- `POST /lookbooks/{lb_id}/publish`
- `POST /lookbooks/{lb_id}/items`
- `DELETE /lookbooks/{lb_id}/items/{asset_id}`
- `GET /lookbooks/{lb_id}/items`

### 访问授权
- `POST /lookbooks/{lb_id}/access`
- `DELETE /lookbooks/{lb_id}/access/{user_id}`
- `GET /my/lookbooks`

## 7. 任务（Jobs）

### GET `/jobs/{job_id}`
- 说明：查询异步任务状态与进度。

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
