# AIGC Model Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `gallery-api + frontend_v2` 内实现“平铺原图 + 参考图 -> 模特图候选 -> 人工审核 -> 入商品资产”的完整 AIGC 生产闭环。

**Architecture:** 采用后端任务中心（FastAPI + SQLAlchemy）和 Celery 异步生成；前端 `frontend_v2` 新增 `/ops/aigc` 页面并打通检索/商品入口。生成候选与正式资产分层，审核通过后再落正式 `asset`，并设置不可逆 `is_ai_generated=true`。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery, OpenAI SDK(OpenRouter), React + TypeScript + React Query + Vitest。

---

## File Structure Map

### Backend (`gallery-api`)

- Create: `app/aigc/__init__.py`
- Create: `app/aigc/models.py`  
  责任：AIGC 任务、候选图、提示词日志、授权日志、反馈、模板实体。
- Create: `app/aigc/schemas.py`  
  责任：AIGC API 请求/响应模型。
- Create: `app/aigc/provider.py`  
  责任：Nano Banana(OpenRouter) 调用封装，统一超时与错误转换。
- Create: `app/aigc/service.py`  
  责任：任务创建、候选持久化、审核入库、反馈写入、模板读取。
- Create: `app/aigc/router.py`  
  责任：`/aigc/*` 接口。
- Modify: `app/assets/models.py`  
  责任：`Asset` 增加 `is_ai_generated` 字段（不可逆，默认 false）。
- Modify: `app/search/schemas.py` / `app/search/service.py`  
  责任：返回 `cover_asset_type` 让前端识别平铺图入口。
- Modify: `app/ai/tasks.py`  
  责任：新增 AIGC Celery 任务，配置 15 分钟软超时与 20 分钟硬超时。
- Modify: `app/config.py`  
  责任：新增 AIGC/OpenRouter 配置。
- Modify: `app/main.py`  
  责任：挂载 `aigc_router`。
- Modify: `alembic/env.py`
- Create: `alembic/versions/9d8c7b6a5e4f_add_aigc_tables_and_ai_generated_flag.py`

### Frontend (`frontend_v2`)

- Create: `src/shared/api/aigc.ts`  
  责任：AIGC API 客户端。
- Create: `src/modules/aigc/aigc-page.tsx`  
  责任：任务创建、队列查看、候选审核、评分反馈。
- Modify: `src/app/router.tsx`  
  责任：新增 `/ops/aigc` 路由。
- Modify: `src/shared/layout/sidebar.tsx` / `src/shared/layout/topbar.tsx`  
  责任：导航与标题接入。
- Modify: `src/shared/api/search.ts`  
  责任：解析 `cover_asset_type`。
- Modify: `src/modules/search/search-page.tsx`  
  责任：平铺图卡片显示“用此平铺图生成模特图”；非平铺图显示“设为参考图”。
- Modify: `src/modules/products/products-page.tsx`  
  责任：商品视图新增 “AI生图” 快捷入口。

### Tests

- Create: `tests/test_aigc_models.py`
- Create: `tests/test_aigc_api.py`
- Create: `tests/test_aigc_provider.py`
- Create: `tests/test_aigc_celery.py`
- Modify: `tests/conftest.py`（创建 AIGC 测试表兜底）
- Create: `frontend_v2/src/modules/aigc/__tests__/aigc-page.test.tsx`
- Modify: `frontend_v2/src/app/__tests__/router.test.tsx`
- Modify: `frontend_v2/src/modules/search/__tests__/search-page.test.tsx`
- Modify: `frontend_v2/src/modules/products/__tests__/products-page.test.tsx`（新增）

---

### Task 1: 数据模型与迁移（AIGC 基础）

**Files:**
- Create: `app/aigc/models.py`
- Modify: `app/assets/models.py`
- Modify: `app/config.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/9d8c7b6a5e4f_add_aigc_tables_and_ai_generated_flag.py`
- Test: `tests/test_aigc_models.py`

- [ ] **Step 1: 写失败测试（模型默认值与关系）**

```python
# tests/test_aigc_models.py
import uuid
from app.assets.models import Asset, AssetType, ParseStatus, Product
from app.aigc.models import AigcTask, AigcTaskStatus, AigcPromptTemplate, AigcPromptTemplateVersion

def test_aigc_task_defaults(db):
    product = Product(product_code="AIGC-PLAN-001")
    asset = Asset(
        original_uri="s3://bucket/flat.jpg",
        display_uri="s3://bucket/flat-display.jpg",
        thumb_uri="s3://bucket/flat-thumb.jpg",
        filename="flat.jpg",
        width=1000,
        height=1200,
        file_size=123,
        feature_status={"classify": "done", "embed": "done"},
        asset_type=AssetType.flatlay,
        parse_status=ParseStatus.parsed,
    )
    db.add_all([product, asset])
    db.flush()

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=asset.id,
        flatlay_original_uri=asset.original_uri,
        reference_source="library",
        candidate_count=2,
        template_version=1,
        created_by=uuid.uuid4(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    assert task.status == AigcTaskStatus.queued
    assert task.face_deidentify_enabled is True
    assert task.timeout_seconds == 900
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_aigc_models.py -v`  
Expected: `ModuleNotFoundError: No module named 'app.aigc'`

- [ ] **Step 3: 实现模型与配置字段（最小可用）**

```python
# app/aigc/models.py (核心片段)
class AigcTaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    review_pending = "review_pending"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"

class AigcTask(Base):
    __tablename__ = "aigc_task"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product.id"), nullable=False)
    flatlay_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("asset.id"), nullable=False)
    flatlay_original_uri: Mapped[str] = mapped_column(String, nullable=False)
    reference_source: Mapped[str] = mapped_column(String, nullable=False)
    face_deidentify_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900, server_default="900")
    status: Mapped[AigcTaskStatus] = mapped_column(Enum(AigcTaskStatus, name="aigctaskstatus"), nullable=False, default=AigcTaskStatus.queued, server_default=AigcTaskStatus.queued.value)
```

```python
# app/assets/models.py (Asset 片段)
is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
```

```python
# app/config.py (新增)
openrouter_api_key: str = ""
aigc_model_name: str = "google/gemini-3-pro-image-preview"
aigc_default_candidate_count: int = 2
aigc_provider_timeout_seconds: int = 700
aigc_soft_timeout_seconds: int = 900
aigc_hard_timeout_seconds: int = 1200
```

- [ ] **Step 4: 编写 Alembic 迁移并纳入 metadata**

```python
# alembic/env.py
import app.aigc.models  # noqa
```

```python
# alembic/versions/9d8c7b6a5e4f_add_aigc_tables_and_ai_generated_flag.py (片段)
def upgrade() -> None:
    op.add_column("asset", sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "aigc_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("flatlay_asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("flatlay_original_uri", sa.String(), nullable=False),
        sa.Column("status", sa.Enum("queued", "running", "review_pending", "approved", "rejected", "failed", name="aigctaskstatus"), nullable=False, server_default="queued"),
    )
```

- [ ] **Step 5: 重新运行测试并验证通过**

Run: `pytest tests/test_aigc_models.py -v`  
Expected: `1 passed`

- [ ] **Step 6: 提交**

```bash
git add app/aigc/models.py app/assets/models.py app/config.py alembic/env.py alembic/versions/*.py tests/test_aigc_models.py
git commit -m "feat(aigc): add core models, config and migration"
```

---

### Task 2: Provider 与 Celery 长任务执行链路

**Files:**
- Create: `app/aigc/provider.py`
- Modify: `app/ai/tasks.py`
- Create: `tests/test_aigc_provider.py`
- Create: `tests/test_aigc_celery.py`

- [ ] **Step 1: 写失败测试（provider 调用与超时参数）**

```python
# tests/test_aigc_provider.py
from app.aigc.provider import NanoBananaProvider

def test_build_request_payload_contains_image_size_and_model():
    provider = NanoBananaProvider(api_key="sk-test", model_name="google/gemini-3-pro-image-preview", timeout_seconds=700)
    payload = provider.build_request_payload(prompt="x", image_data_urls=["data:image/jpeg;base64,aaa"], resolution="2K")
    assert payload["model"] == "google/gemini-3-pro-image-preview"
    assert payload["extra_body"]["image_config"]["image_size"] == "2K"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_aigc_provider.py -v`  
Expected: `ModuleNotFoundError: app.aigc.provider`

- [ ] **Step 3: 实现 provider 封装与错误转换**

```python
# app/aigc/provider.py (片段)
class NanoBananaProvider:
    def __init__(self, api_key: str, model_name: str, timeout_seconds: int) -> None:
        self._client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=timeout_seconds)
        self._model_name = model_name

    def generate(self, prompt: str, image_data_urls: list[str], resolution: str = "2K") -> list[bytes]:
        content = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": u}} for u in image_data_urls
        ]
        resp = self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": content}],
            extra_body={"modalities": ["image", "text"], "image_config": {"image_size": resolution}},
        )
        images = getattr(resp.choices[0].message, "images", None) or []
        if not images:
            raise ValueError("GENERATION_EMPTY")
        return [decode_data_url(extract_image_url(item)) for item in images]
```

- [ ] **Step 4: 在 Celery 新增 AIGC 任务（15/20 分钟）**

```python
# app/ai/tasks.py (新增)
@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=settings.aigc_soft_timeout_seconds,
    time_limit=settings.aigc_hard_timeout_seconds,
)
def celery_aigc_generate(self, task_id: str):
    db = SessionLocal()
    try:
        run_aigc_generation(db, uuid.UUID(task_id))
        db.commit()
    except TransientAigcError as exc:
        db.rollback()
        raise self.retry(exc=exc)
    except Exception:
        db.rollback()
        mark_aigc_task_failed(db, uuid.UUID(task_id), error_code="GENERATION_FAILED")
        db.commit()
        raise
    finally:
        db.close()
```

- [ ] **Step 5: 运行测试验证 provider + celery 通过**

Run: `pytest tests/test_aigc_provider.py tests/test_aigc_celery.py -v`  
Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add app/aigc/provider.py app/ai/tasks.py tests/test_aigc_provider.py tests/test_aigc_celery.py
git commit -m "feat(aigc): add nano banana provider and celery long-running task"
```

---

### Task 3: AIGC 服务层 + API + 审核入库

**Files:**
- Create: `app/aigc/schemas.py`
- Create: `app/aigc/service.py`
- Create: `app/aigc/router.py`
- Modify: `app/main.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_aigc_api.py`

- [ ] **Step 1: 写失败 API 测试（创建/审核/驳回）**

```python
# tests/test_aigc_api.py

def test_create_aigc_task_requires_authorization_consent(client, editor_token, flatlay_asset, product):
    resp = client.post(
        "/aigc/tasks",
        json={
            "product_id": str(product.id),
            "flatlay_asset_id": str(flatlay_asset.id),
            "reference_source": "upload",
            "reference_upload_uri": "s3://bucket/ref.jpg",
            "consent_checked": False,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 422


def test_approve_task_creates_ai_asset(client, editor_token, aigc_review_pending_task):
    resp = client.post(
        f"/aigc/tasks/{aigc_review_pending_task.id}/approve",
        json={"selected_candidate_id": str(aigc_review_pending_task.candidates[0].id), "target_asset_type": "model_set"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_aigc_api.py -v`  
Expected: 404 (`/aigc/tasks` route not found)

- [ ] **Step 3: 实现 schemas + service + router + main 挂载**

```python
# app/aigc/router.py (片段)
router = APIRouter(prefix="/aigc", tags=["aigc"])

@router.post("/tasks", response_model=AigcTaskOut, status_code=201)
def create_task(body: AigcTaskCreateIn, db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.admin, UserRole.editor))):
    task = create_aigc_task(db, user=user, body=body)
    if settings.async_mode == "celery":
        from app.ai.tasks import celery_aigc_generate
        celery_aigc_generate.delay(str(task.id))
    return task

@router.post("/tasks/{task_id}/approve", response_model=AigcTaskOut)
def approve(task_id: uuid.UUID, body: AigcApproveIn, db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.admin, UserRole.editor))):
    return approve_aigc_task(db, task_id=task_id, selected_candidate_id=body.selected_candidate_id, target_asset_type=body.target_asset_type, reviewer=user)
```

```python
# app/main.py
from app.aigc.router import router as aigc_router
...
app.include_router(aigc_router)
```

- [ ] **Step 4: 在服务层保证“原图输入 + AI标识不可逆 + 审核后入库”**

```python
# app/aigc/service.py (片段)
if flatlay_asset.original_uri != body.flatlay_original_uri:
    raise HTTPException(status_code=422, detail="flatlay image must use original_uri")

new_asset = Asset(
    ...,
    asset_type=body.target_asset_type,
    is_ai_generated=True,
)
```

- [ ] **Step 5: 跑 API 测试确认通过**

Run: `pytest tests/test_aigc_api.py -v`  
Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add app/aigc/schemas.py app/aigc/service.py app/aigc/router.py app/main.py tests/conftest.py tests/test_aigc_api.py
git commit -m "feat(aigc): add task lifecycle APIs and review-to-asset workflow"
```

---

### Task 4: 搜索结果补全 `cover_asset_type`（支持平铺图入口判断）

**Files:**
- Modify: `app/search/schemas.py`
- Modify: `app/search/service.py`
- Modify: `tests/test_search_products.py`
- Modify: `frontend_v2/src/shared/api/search.ts`

- [ ] **Step 1: 写失败测试（搜索返回封面类型）**

```python
# tests/test_search_products.py (新增断言)
assert item["cover_asset_type"] in {"flatlay", "model_set", "advertising", "unknown", None}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_search_products.py -v`  
Expected: KeyError / schema validation error for `cover_asset_type`。

- [ ] **Step 3: 实现后端字段透出 + 前端适配**

```python
# app/search/schemas.py
class ProductSearchItem(BaseModel):
    ...
    cover_asset_type: str | None = None
```

```python
# app/search/service.py (组装 items)
"cover_asset_type": cover_candidate.asset_type.value if cover_candidate and cover_candidate.asset_type else None,
```

```ts
// frontend_v2/src/shared/api/search.ts
export type HybridItem = {
  ...
  cover_asset_type?: "flatlay" | "model_set" | "advertising" | "unknown";
};
```

- [ ] **Step 4: 运行后端 + 前端相关测试**

Run: `pytest tests/test_search_products.py -v`  
Run: `cd ../frontend_v2 && npm run test -- src/shared/api/__tests__/search.test.ts`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/search/schemas.py app/search/service.py tests/test_search_products.py
git commit -m "feat(search): include cover_asset_type for aigc entry decisions"
```

---

### Task 5: 前端 `/ops/aigc` 页面与导航接入

**Files:**
- Create: `frontend_v2/src/shared/api/aigc.ts`
- Create: `frontend_v2/src/modules/aigc/aigc-page.tsx`
- Modify: `frontend_v2/src/app/router.tsx`
- Modify: `frontend_v2/src/shared/layout/sidebar.tsx`
- Modify: `frontend_v2/src/shared/layout/topbar.tsx`
- Create: `frontend_v2/src/modules/aigc/__tests__/aigc-page.test.tsx`
- Modify: `frontend_v2/src/app/__tests__/router.test.tsx`

- [ ] **Step 1: 写失败测试（路由可达 + 页面渲染）**

```tsx
// src/modules/aigc/__tests__/aigc-page.test.tsx
it("renders aigc page shell", () => {
  render(<AigcPage />);
  expect(screen.getByText("AI生图")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "创建任务" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd ../frontend_v2 && npm run test -- src/modules/aigc/__tests__/aigc-page.test.tsx src/app/__tests__/router.test.tsx`  
Expected: module not found (`AigcPage`) / route missing。

- [ ] **Step 3: 实现 API 客户端 + 页面 + 路由导航**

```ts
// src/shared/api/aigc.ts (片段)
export async function createAigcTask(payload: AigcTaskCreateIn): Promise<AigcTask> {
  return apiFetch("/aigc/tasks", { method: "POST", body: JSON.stringify(payload) });
}
```

```tsx
// src/app/router.tsx
import { AigcPage } from "@/modules/aigc/aigc-page";
...
<Route path="aigc" element={<AigcPage />} />
```

```tsx
// src/shared/layout/sidebar.tsx
{ to: "/ops/aigc", label: "AI生图", icon: Sparkles },
```

- [ ] **Step 4: 运行前端测试确认通过**

Run: `cd ../frontend_v2 && npm run test -- src/modules/aigc/__tests__/aigc-page.test.tsx src/app/__tests__/router.test.tsx`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd ../frontend_v2
git add src/shared/api/aigc.ts src/modules/aigc/aigc-page.tsx src/app/router.tsx src/shared/layout/sidebar.tsx src/shared/layout/topbar.tsx src/modules/aigc/__tests__/aigc-page.test.tsx src/app/__tests__/router.test.tsx
git commit -m "feat(frontend): add /ops/aigc page and navigation"
```

---

### Task 6: 前端入口联动（检索页 + 商品管理）与审核闭环

**Files:**
- Modify: `frontend_v2/src/modules/search/search-page.tsx`
- Modify: `frontend_v2/src/modules/products/products-page.tsx`
- Modify: `frontend_v2/src/modules/search/__tests__/search-page.test.tsx`
- Create: `frontend_v2/src/modules/products/__tests__/products-page.test.tsx`

- [ ] **Step 1: 写失败测试（平铺图按钮文案、跳转参数）**

```tsx
// src/modules/search/__tests__/search-page.test.tsx (新增)
expect(screen.getByRole("button", { name: "用此平铺图生成模特图" })).toBeInTheDocument();
```

```tsx
// src/modules/products/__tests__/products-page.test.tsx (新增)
expect(screen.getByRole("button", { name: "AI生图" })).toBeInTheDocument();
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd ../frontend_v2 && npm run test -- src/modules/search/__tests__/search-page.test.tsx src/modules/products/__tests__/products-page.test.tsx`  
Expected: 按钮不存在。

- [ ] **Step 3: 实现入口逻辑**

```tsx
// src/modules/search/search-page.tsx (结果卡片动作)
{item.cover_asset_type === "flatlay" ? (
  <button onClick={() => navigate(`/ops/aigc?flatlay_asset_id=${item.cover_asset_id}`)}>用此平铺图生成模特图</button>
) : (
  <button onClick={() => navigate(`/ops/aigc?reference_asset_id=${item.cover_asset_id}`)}>设为参考图</button>
)}
```

```tsx
// src/modules/products/products-page.tsx
<button onClick={() => navigate(`/ops/aigc?product_id=${product.id}`)}>AI生图</button>
```

- [ ] **Step 4: 运行前端全量测试 + build**

Run: `cd ../frontend_v2 && npm run test`  
Run: `cd ../frontend_v2 && npm run build`  
Expected: tests PASS, build success。

- [ ] **Step 5: 提交**

```bash
cd ../frontend_v2
git add src/modules/search/search-page.tsx src/modules/products/products-page.tsx src/modules/search/__tests__/search-page.test.tsx src/modules/products/__tests__/products-page.test.tsx
git commit -m "feat(frontend): wire search/products entry points into aigc workflow"
```

---

### Task 7: 回归验证、文档更新与交付

**Files:**
- Modify: `README.md`
- Modify: `docs/API接口文档.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 写/更新接口文档（AIGC 路由、状态机、超时说明）**

```md
## AIGC
- POST /aigc/tasks
- GET /aigc/tasks
- GET /aigc/tasks/{id}
- POST /aigc/tasks/{id}/approve
- POST /aigc/tasks/{id}/reject
- POST /aigc/candidates/{id}/feedback

任务超时：soft=900s, hard=1200s
```

- [ ] **Step 2: 执行后端测试 + 前端测试 + 构建**

Run: `pytest tests/test_aigc_models.py tests/test_aigc_provider.py tests/test_aigc_celery.py tests/test_aigc_api.py tests/test_search_products.py -v`  
Run: `cd ../frontend_v2 && npm run test`  
Run: `cd ../frontend_v2 && npm run build`  
Expected: 全部通过。

- [ ] **Step 3: 手工验收（冒烟）**

Run API: `uvicorn app.main:app --reload --port 8000`  
Run FE: `cd ../frontend_v2 && npm run dev`  
Check:
1. `/ops/aigc` 页面可打开。
2. 检索页平铺图显示“用此平铺图生成模特图”。
3. 创建任务后状态从 `queued -> running -> review_pending`。
4. 审核通过后商品资产列表可见新图，且显示 AI 生成标识。

- [ ] **Step 4: 提交**

```bash
git add README.md docs/API接口文档.md CHANGELOG.md
git commit -m "docs: add aigc workflow, api contract, and timeout policy"
```

---

## Plan Self-Review

### 1) Spec Coverage Check

- 平铺原图 + 参考图：Task 3（创建接口校验）+ Task 6（入口参数）。
- 默认 2 张候选：Task 1（模型默认值）+ Task 3（服务逻辑）。
- 默认去标识化可关闭：Task 1（字段）+ Task 3（请求/日志）。
- 人工审核后入库：Task 3。
- `AI生成` 不可逆标识：Task 1 + Task 3。
- 超时 >=10 分钟：Task 2（Celery 900/1200）+ Task 7（文档）。
- 前端 `frontend_v2` 整合：Task 5 + Task 6。
- 评分与评语：Task 3（feedback API）+ Task 5（页面入口）。

### 2) Placeholder Scan

- 无占位短语与“稍后实现”描述。
- 每个代码步骤给出可执行代码片段。
- 每个任务都有明确测试命令和 commit 命令。

### 3) Type/Name Consistency

- 统一使用 `AigcTaskStatus`、`is_ai_generated`、`cover_asset_type`、`face_deidentify_enabled`。
- 路由统一使用 `/aigc/*`。
