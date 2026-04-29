# Gallery API

服饰图库后端服务，负责资产管理、商品关联、标签治理、检索、画册发布，以及 AIGC 任务编排与执行。

## 当前版本

- FastAPI 应用版本：`1.1.0`
- 当前主要分支：`main`
- 最近更新时间：`2026-04-26`
- Swagger UI：`http://127.0.0.1:8000/docs`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

中文接口文档：

- [docs/API接口文档.md](docs/API接口文档.md)

本次封版摘要：

- AIGC 生成与优化链路稳定化
- 资产上传 / 资产商品关联接口补齐
- lookbook section 编辑模型、排序能力与兼容层完善
- Celery 队列与 Ark key 兼容配置补齐
- 商品治理总览 / 问题商品池 / 商品工作台聚合接口上线
- 商品标签摘要补全为可读节点名称
- 商品工作台补充 AIGC 候选摘要与 Lookbook 关联摘要
- taxonomy 管理接口补齐 parent 重挂、清空 parent 和候选提升兼容行为
- 商品治理完整性语义收敛为“平铺图 + 展示图”

## 技术栈

- FastAPI
- PostgreSQL + pgvector
- MinIO / S3 / TOS
- Redis + Celery
- SQLAlchemy + Alembic
- 外部 Embedding / VLM / AIGC Provider

## 主要能力

- 资产上传与对象存储批量导入
- original / display / thumb 三种图片变体管理
- 资产类型识别与资产商品绑定
- taxonomy 标签体系与候选标签审核
- 资产 / 商品双层标签能力
- 文本检索、属性检索、以图搜图
- 商品维度聚合检索
- lookbook 发布、授权与 buyer 访问
- AIGC 任务创建、候选生成、优化任务派生
- 任务进度查询与异步任务执行

## 目录结构

```text
gallery-api/
├── app/
│   ├── aigc/                  # AIGC 路由、schema、service、provider
│   ├── ai/                    # 向量/VLM 客户端
│   ├── assets/                # 资产上传、打标、绑定、重处理
│   ├── auth/                  # 认证与 JWT
│   ├── jobs/                  # 任务进度查询
│   ├── lookbooks/             # 画册、section 编辑、buyer 访问
│   ├── products/              # 商品主数据与商品视图接口
│   ├── search/                # 检索接口
│   ├── taxonomy/              # 标签树与候选标签
│   ├── users/                 # 用户管理
│   ├── celery_app.py          # Celery 配置
│   ├── config.py              # 环境变量配置
│   ├── database.py            # DB session
│   ├── main.py                # FastAPI 入口
│   └── storage.py             # 对象存储抽象
├── alembic/                   # 数据库迁移
├── docs/                      # 接口与运行文档
├── scripts/                   # 管理脚本
└── tests/                     # 测试
```

## 快速开始

### 1. 安装依赖

```bash
conda activate qiaofei
cd gallery-api
pip install -r requirements.txt
```

运行环境建议：

- Python `3.10+`

说明：

- 当前代码已使用 `str | None` 这类 Python 3.10 联合类型语法
- 如果仍用 Python 3.9，`pytest` 可能会在收集阶段直接失败

### 2. 配置环境变量

```bash
cp .env.example .env
```

建议至少确认这些变量：

- `DATABASE_URL`
- `SECRET_KEY`
- `STORAGE_PROVIDER`
- `S3_*` 或 `TOS_*`
- `EMBED_*`
- `VLM_*`
- `ASYNC_MODE`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

和当前版本相关的新兼容点：

- 支持 `VOLC_ARK_API_KEY`
- 也兼容 `ARK_API_KEY`
- Celery 队列默认支持：
  - `celery`
  - `aigc`

### 3. 启动基础设施

```bash
docker compose -f docker-compose.dev.yml up -d
```

默认会启动：

- PostgreSQL：`5432`
- Redis：`6379`
- MinIO API：`9000`
- MinIO Console：`9001`

### 4. 初始化数据库

```bash
alembic upgrade head
```

### 5. 启动 API

```bash
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

### 6. 启动 Celery Worker（可选）

当 `ASYNC_MODE=celery` 时，建议同时启动 worker：

```bash
celery -A app.celery_app.celery_app worker --loglevel=INFO
```

当前会使用以下队列：

- 默认队列：`celery`
- AIGC 队列：`aigc`

## 常用命令

```bash
# 创建管理员
python scripts/create_admin.py --email admin@example.com --name "Admin" --password '<password>'

# 初始化 taxonomy
python scripts/seed_taxonomy.py

# 运行全量测试
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cloth_gallery \
  python -m pytest tests/ -v
```

## 关键模块说明

### 1. Assets

提供：

- 上传资产
- 列表查询
- 标签维护
- 资产商品绑定
- 重处理 / 批处理

当前封版新增点：

- `POST /assets/upload` 支持 `asset_type`
- 资产商品关系返回中包含 `product_id`
- `POST /assets/{asset_id}/products/bind` 支持在未显式传 `relation_role` 时，根据 `asset_type` 推导默认关系

### 2. Search

支持：

- 资产维度检索
- 商品维度聚合检索
- 语义检索
- 以图搜图

### 3. Lookbooks

支持：

- 画册创建与发布
- buyer 授权访问
- section-based 编辑接口
- legacy `lookbook_item` 兼容显示
- 封面回退：`resolved_cover_asset_id` 按 cover → section cover → first item asset 降级

当前封版新增点：

- product-driven section editor API
- section 删除 / 补图 / 排序接口
- mutation path 与 `lookbook_id` 一致性校验
- buyer 端 section flatten 兼容输出
- 商品池可用 `has_assets=true` 仅筛出已关联图片商品
- `GET /lookbooks` 列表返回 `resolved_cover_asset_id`，前端无需自行做封面回退

### 4. Product Governance / Workbench

支持：

- 商品素材完整性治理总览
- 问题商品池筛选与搜索
- 商品工作台聚合视图
- workbench 内 AIGC / Lookbook / 标签 / 质量问题摘要

当前封版新增点：

- `GET /products/governance/summary`
- `GET /products/governance/items`
- `GET /products/{product_id}/workbench`
- `problem=in_lookbook` 筛选语义
- 完整性语义由“缺模特图 / 缺广告图”收敛为“缺展示图”，其中展示图 = `model_set + advertising`
- 标签返回补充 `node_name`
- `quality_issues` 不再把 `complete` 当成问题项

### 4. AIGC

支持：

- 创建 AIGC 任务
- 生成候选图
- 基于已有候选继续发起优化任务
- provider 请求兼容当前 Ark SDK 行为

当前封版新增点：

- provider 不再使用 Ark 已废弃的 `n`
- 保留 `candidate_count` 接口兼容层
- 支持基于候选图继续发起自动优化 / 自定义提示词优化

### 5. Taxonomy

支持：

- taxonomy 树查询
- 节点创建、改名、停用
- `parent_id` 重挂与清空，支持树结构调整
- 候选标签审核与提升

当前封版新增点：

- `POST /taxonomy/candidates/{candidate_id}/promote` 兼容无 body 调用
- `PATCH /taxonomy/nodes/{node_id}` 支持显式传 `parent_id: null`，将节点移回顶级
- taxonomy 前端工作台依赖这些接口完成拖拽改层级、移到顶级节点等操作

## 核心接口摘要

### Auth / Users

注册与审核流程：

- `POST /auth/register` — 创建待审核注册申请（非正式账号），密码匹配才返回 403 提示
- `POST /auth/login` — 待审核账号正确密码返回 403 "账号待审核，暂时不能登录"，错误密码返回通用 401
- `GET /users` — 管理员列表所有用户
- `GET /users/registration-requests` — 管理员查看待审核申请
- `POST /users/registration-requests/{id}/approve` — 通过申请，创建正式 `viewer` 用户并删除申请
- `DELETE /users/registration-requests/{id}` — 拒绝并删除申请

管理员安全规则：

- 不允许通过 PATCH role 或 DELETE 移除最后一个管理员
- 不允许通过 PATCH is_active=false 绕过 deactivate 保护
- 不允许管理员自降级或自停用

### Assets

- `POST /assets/upload`
- `GET /assets`
- `GET /assets/{asset_id}`
- `GET /assets/{asset_id}/file`
- `GET /assets/{asset_id}/products`
- `POST /assets/{asset_id}/products/bind`
- `DELETE /assets/{asset_id}/products/{product_code}`
- `PATCH /assets/{asset_id}/tags`
- `POST /assets/{asset_id}/process`
- `POST /assets/reprocess`
- `POST /assets/batch-ingest/storage`

### Products

- `POST /products/upsert`
- `GET /products`
- `GET /products/{product_id}`
- `GET /products/{product_id}/assets`
- `GET /products/{product_id}/tags`
- `PATCH /products/{product_id}/tags`
- `GET /products/governance/summary`
- `GET /products/governance/items`
- `GET /products/{product_id}/workbench`
- `POST /products/admin/sales/sync`

常用筛选补充：

- `GET /products?has_assets=true`
  仅返回至少已绑定 1 张图片资产的商品，适合 lookbook 待选商品池。
- `GET /products/governance/items?problem=in_lookbook`
  仅返回已经进入至少一个 lookbook 的商品。
- `GET /products/{product_id}/workbench`
  返回商品基础信息、完整性状态、推荐动作、分组素材、AIGC 摘要、Lookbook 摘要、标签摘要和质量问题列表。
- `POST /products/admin/sales/sync`
  按 `source=budan` 整体替换销售原始数据，再重建 `product_sales_summary`。

销售同步兼容说明：

- `sales_order_raw.source_order_id` 允许为空，兼容历史手工导入来源。
- 历史来源可以只依赖表内主键 `id` 存活，不强制补伪订单号。
- `budan` 同步不再依赖 `(source, source_order_id)` upsert，而是按来源整体替换，避免 legacy 空值导致冲突。

### Taxonomy

- `GET /taxonomy`
- `POST /taxonomy/nodes`
- `PATCH /taxonomy/nodes/{node_id}`
- `DELETE /taxonomy/nodes/{node_id}`
- `GET /taxonomy/candidates`
- `POST /taxonomy/candidates/{candidate_id}/promote`

接口语义补充：

- `PATCH /taxonomy/nodes/{node_id}`
  - `{"parent_id": "<uuid>"}`：挂到指定父节点下
  - `{"parent_id": null}`：移回当前维度顶级
- `POST /taxonomy/candidates/{candidate_id}/promote`
  - 无 body：提升为顶级节点
  - `{"parent_id": "<uuid>"}`：提升到指定父节点下

### Search

- `GET /search`
- `POST /search/semantic`
- `POST /search/vector`
- `GET /search/products`
- `POST /search/products/semantic`
- `POST /search/products/vector`

### Lookbooks

- `POST /lookbooks`
- `PATCH /lookbooks/{lb_id}`
- `GET /lookbooks`
- `POST /lookbooks/{lb_id}/publish`
- `DELETE /lookbooks/{lb_id}/unpublish`
- `GET /lookbooks/{lb_id}/access`
- `POST /lookbooks/{lb_id}/access`
- `DELETE /lookbooks/{lb_id}/access/{user_id}`
- `GET /lookbooks/{lb_id}/sections`
- `POST /lookbooks/{lb_id}/sections/products`
- `PATCH /lookbooks/{lb_id}/sections/reorder`
- `POST /lookbooks/{lb_id}/sections/{section_id}/items`
- `DELETE /lookbooks/{lb_id}/sections/{section_id}`
- `DELETE /lookbooks/{lb_id}/sections/{section_id}/items/{asset_id}`
- `GET /my/lookbooks`
- `GET /my/lookbooks/{lb_id}/items`

编辑器行为补充：

- `GET /lookbooks/{lb_id}/sections`
  会把未迁移的 legacy `lookbook_item` 自动包装成 synthetic legacy section 返回给前端编辑器。
- `PATCH /lookbooks/{lb_id}/sections/reorder`
  只重排真实商品 section，不包含 legacy synthetic section。

### AIGC

- `POST /aigc/tasks`
- `GET /aigc/tasks`
- `GET /aigc/tasks/{task_id}`
- `POST /aigc/tasks/{task_id}/approve`
- `POST /aigc/tasks/{task_id}/reject`
- `POST /aigc/candidates/{candidate_id}/optimize`
- `POST /aigc/candidates/{candidate_id}/feedback`
- `GET /aigc/candidates/{candidate_id}/file`
- `GET /aigc/providers`

优化链路补充：

- `POST /aigc/candidates/{candidate_id}/optimize`
  支持两种模式：
  - `mode=auto`：自动增强服装纹理、人物细节和配饰合理性
  - `mode=custom`：追加用户自定义提示词继续优化

### Jobs

- `GET /jobs/{job_id}`

## 测试建议

常用回归组合：

```bash
conda run -n qiaofei pytest tests/test_aigc_provider.py tests/test_assets.py tests/test_lookbooks.py -q
conda run -n qiaofei pytest tests/test_aigc_api.py tests/test_aigc_celery.py -q
```

## 相关文档

- [API接口文档](docs/API接口文档.md)
- [INGESTION_OPERATING_MODEL](docs/INGESTION_OPERATING_MODEL.md)
- [RAW_DATA_SPEC](docs/RAW_DATA_SPEC.md)
- [UNRESOLVED_PLACEHOLDER_UID_POLICY](docs/UNRESOLVED_PLACEHOLDER_UID_POLICY.md)
- [release1.2 PR 摘要](docs/PR_RELEASE_1.2.md)

## 常见问题

### 1. `/assets/upload` 返回失败

优先检查：

1. 对象存储是否可写
2. `STORAGE_PROVIDER` 配置是否正确
3. 上传文件是否为可处理图片

### 2. 前端能打开但 API 都失败

请确认：

1. API 已运行在 `127.0.0.1:8000`
2. 前端开发代理已生效
3. 登录 token 仍有效

### 3. AIGC 任务创建时报 provider 参数错误

当前版本已经兼容 Ark SDK 不接受 `n` 的行为。如果仍失败，请优先检查：

1. `VOLC_ARK_API_KEY` / `ARK_API_KEY`
2. provider base URL
3. worker / API 是否使用了相同配置

### 4. Lookbook legacy 内容为什么是兼容显示而不是直接迁移

当前 `release1.2` 采用的是稳定优先策略：

- 先保证新 editor 可见 legacy 内容
- 避免编辑器展示会失败的操作
- 真正的数据迁移可以后续再补专门脚本或迁移流程
