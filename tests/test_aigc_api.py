import pytest

from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, AssetType, ParseStatus, Product
from app.aigc.models import AigcTask, AigcTaskCandidate, AigcTaskStatus


def _make_user(db, role=UserRole.editor):
    user = User(
        email="aigc_api_test@example.com",
        password_hash=hash_password("pw"),
        name="AigcApiTester",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _make_product(db, code="AIGC-API-001"):
    product = Product(product_code=code)
    db.add(product)
    db.flush()
    return product


def _make_flatlay_asset(db):
    asset = Asset(
        original_uri="s3://bucket/flat-api.jpg",
        display_uri="s3://bucket/flat-api-d.jpg",
        thumb_uri="s3://bucket/flat-api-t.jpg",
        filename="flat-api.jpg",
        width=1000,
        height=1200,
        file_size=12345,
        feature_status={},
        asset_type=AssetType.flatlay,
        parse_status=ParseStatus.parsed,
    )
    db.add(asset)
    db.flush()
    return asset


def _make_ref_asset(db):
    asset = Asset(
        original_uri="s3://bucket/ref-api.jpg",
        display_uri="s3://bucket/ref-api-d.jpg",
        thumb_uri="s3://bucket/ref-api-t.jpg",
        filename="ref-api.jpg",
        width=800,
        height=1000,
        file_size=9999,
        feature_status={},
        asset_type=AssetType.advertising,
        parse_status=ParseStatus.parsed,
    )
    db.add(asset)
    db.flush()
    return asset


@pytest.fixture
def editor_token(db):
    user = _make_user(db)
    return create_access_token(str(user.id))


@pytest.fixture
def viewer_token(db):
    user = _make_user(db, role=UserRole.viewer)
    return create_access_token(str(user.id))


def test_create_aigc_task_requires_consent(client, editor_token, db):
    product = _make_product(db)
    asset = _make_flatlay_asset(db)

    resp = client.post(
        "/aigc/tasks",
        json={
            "product_id": str(product.id),
            "flatlay_asset_id": str(asset.id),
            "reference_source": "upload",
            "reference_upload_uri": "s3://bucket/ref.jpg",
            "consent_checked": False,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 422


def test_create_aigc_task_success(client, editor_token, db):
    product = _make_product(db)
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)

    resp = client.post(
        "/aigc/tasks",
        json={
            "product_id": str(product.id),
            "flatlay_asset_id": str(flatlay.id),
            "reference_source": "library",
            "reference_asset_id": str(ref.id),
            "consent_checked": True,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "queued"
    assert data["reference_original_uri"] == "s3://bucket/ref-api.jpg"
    assert data["provider"] == "seedream_ark"


def test_get_aigc_task(client, editor_token, db):
    product = _make_product(db)
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)

    user = User(
        email="aigc_get@example.com",
        password_hash=hash_password("pw"),
        name="GetTester",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=flatlay.id,
        flatlay_original_uri=flatlay.original_uri,
        reference_source="library",
        reference_asset_id=ref.id,
        reference_original_uri=ref.original_uri,
        status=AigcTaskStatus.queued,
        provider="seedream_ark",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=900,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    resp = client.get(
        f"/aigc/tasks/{task.id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(task.id)


def test_list_aigc_tasks(client, editor_token, db):
    resp = client.get(
        "/aigc/tasks",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_approve_task(client, editor_token, db):
    product = _make_product(db, code="APPROVE-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)

    user = User(
        email="approve@example.com",
        password_hash=hash_password("pw"),
        name="ApproveTester",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=flatlay.id,
        flatlay_original_uri=flatlay.original_uri,
        reference_source="library",
        reference_asset_id=ref.id,
        reference_original_uri=ref.original_uri,
        status=AigcTaskStatus.review_pending,
        provider="seedream_ark",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=900,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    candidate = AigcTaskCandidate(
        task_id=task.id,
        seq_no=1,
        image_uri="s3://bucket/cand-1.jpg",
        thumb_uri="s3://bucket/cand-1-t.jpg",
        width=1024,
        height=1536,
        file_size=50000,
    )
    db.add(candidate)
    db.flush()

    resp = client.post(
        f"/aigc/tasks/{task.id}/approve",
        json={
            "selected_candidate_id": str(candidate.id),
            "target_asset_type": "model_set",
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_reject_task(client, editor_token, db):
    product = _make_product(db, code="REJECT-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)

    user = User(
        email="reject@example.com",
        password_hash=hash_password("pw"),
        name="RejectTester",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=flatlay.id,
        flatlay_original_uri=flatlay.original_uri,
        reference_source="library",
        reference_asset_id=ref.id,
        reference_original_uri=ref.original_uri,
        status=AigcTaskStatus.review_pending,
        provider="seedream_ark",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=900,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    resp = client.post(
        f"/aigc/tasks/{task.id}/reject",
        json={"reason": "quality too low"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_providers_endpoint(client, viewer_token):
    resp = client.get(
        "/aigc/providers",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["provider_key"] == "seedream_ark" for p in data)


def test_candidate_feedback(client, editor_token, db):
    product = _make_product(db, code="FEEDBACK-001")
    flatlay = _make_flatlay_asset(db)

    user = User(
        email="feedback@example.com",
        password_hash=hash_password("pw"),
        name="FeedbackTester",
        role=UserRole.editor,
    )
    db.add(user)
    db.flush()

    task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=flatlay.id,
        flatlay_original_uri=flatlay.original_uri,
        reference_source="library",
        reference_asset_id=flatlay.id,
        reference_original_uri=flatlay.original_uri,
        status=AigcTaskStatus.review_pending,
        provider="seedream_ark",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=900,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    candidate = AigcTaskCandidate(
        task_id=task.id,
        seq_no=1,
        image_uri="s3://bucket/cand-fb.jpg",
    )
    db.add(candidate)
    db.flush()

    resp = client.post(
        f"/aigc/candidates/{candidate.id}/feedback",
        json={"score": 4, "comment": "good quality"},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 201
