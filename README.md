# Gallery API（定版）

Gallery API 是一个面向服饰图片资产的后端服务，定位为：
- 内部：资产管理与 AI 治理中台（导入、打标、检索、重处理）
- 外部：为精选发布集合（Lookbook）提供受控访问能力

当前技术栈：
- FastAPI
- PostgreSQL + pgvector
- MinIO / S3 / TOS（对象存储）
- Redis + Celery（可选异步）
- VLM + Embedding（HTTP 调用外部模型服务）

## 当前定版信息

- 定版日期：2026-04-12
- API 文档入口：
  - Swagger UI：`http://127.0.0.1:8000/docs`
  - OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`
  - 中文接口文档：[`docs/API接口文档.md`](docs/API接口文档.md)

## 主要能力

- 资产上传与批量导入（支持按对象存储前缀批量 ingestion）
- 图片三种衍生版本管理（original / display / thumb）
- 资产类型识别（`advertising / flatlay / model_set / unknown`）
- 商品主数据（`product`）与资产多对多绑定（`asset_product`）
- 商品统一标签（`product_tag`，由图片标签聚合）
- Taxonomy 多维标签体系（category/style/color/scene/detail）
- AI 自动打标 + 人工打标并存（`source=ai|human`）
- 未命中标签沉淀到 `taxonomy_candidate` 供人工审核提升
- 向量检索（text/image -> pgvector cosine search）
- Lookbook 发布与访问授权（buyer 侧只读访问）
- 任务进度查询（批处理 job）

## 运行规范

- 图片导入运行规范：[`docs/INGESTION_OPERATING_MODEL.md`](docs/INGESTION_OPERATING_MODEL.md)
- 原始数据存放规范：[`docs/RAW_DATA_SPEC.md`](docs/RAW_DATA_SPEC.md)
- unresolved 占位 UID 规范：[`docs/UNRESOLVED_PLACEHOLDER_UID_POLICY.md`](docs/UNRESOLVED_PLACEHOLDER_UID_POLICY.md)

## 目录结构

```text
gallery-api/
├── app/
│   ├── auth/          # 登录、JWT、角色权限
│   ├── users/         # 用户管理
│   ├── assets/        # 资产上传、打标、批处理、重处理
│   ├── taxonomy/      # 标签树与候选标签管理
│   ├── lookbooks/     # 精选集合发布与访问授权
│   ├── search/        # 属性检索与向量检索
│   ├── jobs/          # 批处理任务查询
│   ├── ai/            # VLM/Embedding 客户端与处理逻辑
│   ├── storage.py     # S3/TOS 存储抽象
│   ├── database.py    # SQLAlchemy session
│   └── main.py        # FastAPI 入口
├── alembic/           # 数据库迁移
├── scripts/           # 维护脚本（如 taxonomy seed）
├── tests/             # 测试
└── docker-compose.dev.yml
```

## 快速开始

### 1) 安装依赖

```bash
conda activate qiaofei
cd gallery-api
pip install -r requirements.txt
```

### 2) 配置环境变量

复制并编辑：

```bash
cp .env.example .env
```

最关键项：
- `DATABASE_URL`
- `SECRET_KEY`
- `S3_*` 或 `TOS_*`
- `VLM_*`
- `EMBED_*`
- `ASYNC_MODE`（`background` 或 `celery`）
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`（`ASYNC_MODE=celery` 时）

### 3) 启动基础设施

```bash
docker compose -f docker-compose.dev.yml up -d
```

可选（本地 embedding 服务）：

```bash
docker compose -f docker-compose.dev.yml --profile ai up -d embedding-svc
```

### 4) 初始化数据库

```bash
alembic upgrade head
```

### 5) 启动 API

```bash
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

### 6) 启动 Celery Worker（可选）

当 `ASYNC_MODE=celery` 时，以下接口会把任务投递到 Redis/Celery worker：
- `POST /assets/{asset_id}/process`
- `POST /assets/reprocess`
- `POST /assets/batch-ingest/storage`

启动命令：

```bash
celery -A app.celery_app.celery_app worker --loglevel=INFO
```

## 常用命令

```bash
# 创建管理员
python scripts/create_admin.py --email admin@example.com --name "Admin" --password '<password>'

# 初始化 taxonomy
python scripts/seed_taxonomy.py

# 运行测试
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cloth_gallery \
  python -m pytest tests/ -v
```

## 核心接口（摘要）

### Auth / Users
- `POST /auth/register`
- `POST /auth/login`
- `GET /users`

### Assets
- `POST /assets/upload`
- `POST /assets/batch-ingest/storage`
- `GET /assets`
- `GET /assets/{asset_id}`
- `GET /assets/{asset_id}/products`
- `POST /assets/{asset_id}/products/bind`
- `DELETE /assets/{asset_id}/products/{product_code}`
- `PATCH /assets/{asset_id}/tags`
- `POST /assets/{asset_id}/process`
- `POST /assets/reprocess`

### Products
- `POST /products/upsert`
- `GET /products`
- `GET /products/{product_id}`
- `PATCH /products/{product_id}`
- `GET /products/{product_id}/assets`
- `GET /products/{product_id}/tags`
- `PATCH /products/{product_id}/tags`
- `POST /products/{product_id}/tags/rebuild`
- `GET /products/admin/unresolved-assets`

### Taxonomy
- `GET /taxonomy`
- `POST /taxonomy/nodes`
- `PATCH /taxonomy/nodes/{node_id}`
- `DELETE /taxonomy/nodes/{node_id}`
- `GET /taxonomy/candidates`
- `POST /taxonomy/candidates/{candidate_id}/promote`

### Search
- `GET /search`
- `POST /search/semantic`
- `POST /search/vector`

### Lookbooks
- `POST /lookbooks`
- `POST /lookbooks/{lb_id}/publish`
- `POST /lookbooks/{lb_id}/access`
- `GET /my/lookbooks`

### Jobs
- `GET /jobs/{job_id}`

## 同步/异步调用约定

接口分为两类：

- 同步接口：直接返回业务结果（通常 `200/201`）
- 异步接口：返回任务受理结果（`202 + job_id`），随后轮询 `GET /jobs/{job_id}`

当前异步接口（建议前端统一按 job 处理）：

- `POST /assets/{asset_id}/process`
- `POST /assets/reprocess`
- `POST /assets/batch-ingest/storage`

异步接口返回示例：

```json
{
  "job_id": "9f58e6d6-fdc1-487f-9fdb-2b2ea32934af",
  "stages": ["classify", "embed"]
}
```

`GET /jobs/{job_id}` 返回示例：

```json
{
  "id": "9f58e6d6-fdc1-487f-9fdb-2b2ea32934af",
  "status": "running",
  "stages": ["classify", "embed"],
  "total": 2340,
  "processed": 1200,
  "failed_count": 8,
  "completed": 1208,
  "remaining": 1132,
  "progress_pct": 51.62,
  "elapsed_seconds": 942,
  "throughput_items_per_min": 76.93,
  "eta_seconds": 883
}
```

字段说明：

- `status`: `pending | running | done | failed`
- `completed`: `processed + failed_count`
- `progress_pct`: 进度百分比（0-100）
- `throughput_items_per_min`: 当前平均处理速率（每分钟）
- `eta_seconds`: 预计剩余秒数（无法估算时为 `null`）

## 数据模型（核心表）

- `asset`: 图片主记录与特征状态
- `product`: 商品主记录（价格等业务字段）
- `asset_product`: 资产-商品多对多关系
- `product_tag`: 商品层统一标签（human/aggregated）
- `image_group`: 资产分组
- `taxonomy_node`: 标签树节点
- `taxonomy_candidate`: AI 未命中候选标签
- `asset_tag`: 资产-标签多对多关系
- `asset_embedding`: 向量记录（`vector(768)`）
- `lookbook / lookbook_item / lookbook_access`: 发布集合与授权
- `processing_job`: 批处理任务进度
- `user`: 用户与角色

## 角色与权限

- `admin`: 全量管理
- `editor`: 资产与发布编辑
- `viewer`: 只读查询
- `buyer`: 只读访问授权 lookbook

## 安全说明

- `.env` 不应提交到 Git（仓库已忽略）
- `.env.example` 仅保留占位值，不放真实密钥
- 建议定期轮换模型与存储密钥

## 当前状态说明

该仓库已可支撑：
- 资产导入与治理
- AI 打标与向量检索
- 精选集合（Lookbook）发布与访问控制

后续可按业务需要继续增强：
- 发布版本化（release/snapshot）
- 组织级授权（dealer org）
- 云边增量同步机制
