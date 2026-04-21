import uuid

import pytest
from unittest.mock import MagicMock, patch

from app.aigc.schemas import AigcOptimizeCreateIn
from app.auth.models import User, UserRole
from app.auth.service import hash_password, create_access_token
from app.assets.models import Asset, AssetProduct, AssetProductRole, AssetType, ParseStatus, Product
from app.aigc.models import AigcPromptLog, AigcTask, AigcTaskCandidate, AigcTaskStatus
from app.aigc.service import create_aigc_optimization_task, run_aigc_generation


def _make_user(db, role=UserRole.editor):
    user = User(
        email=f"aigc_api_test_{uuid.uuid4()}@example.com",
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


def _bind_asset_product(db, asset_id, product_id, role=AssetProductRole.flatlay_primary):
    db.add(
        AssetProduct(
            asset_id=asset_id,
            product_id=product_id,
            relation_role=role,
            source="test",
        )
    )
    db.flush()


def _make_source_task_with_candidate(
    db,
    *,
    status=AigcTaskStatus.review_pending,
    face_deidentify_enabled=False,
    candidate_count=3,
):
    product = _make_product(db, code=f"OPT-{status.value}")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)
    _bind_asset_product(db, flatlay.id, product.id, AssetProductRole.flatlay_primary)
    user = _make_user(db)

    source_task = AigcTask(
        product_id=product.id,
        flatlay_asset_id=flatlay.id,
        flatlay_original_uri=flatlay.original_uri,
        reference_source="library",
        reference_asset_id=ref.id,
        reference_original_uri=ref.original_uri,
        face_deidentify_enabled=face_deidentify_enabled,
        candidate_count=candidate_count,
        template_version=7,
        status=status,
        provider="seedream_ark",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=321,
        created_by=user.id,
    )
    db.add(source_task)
    db.flush()

    candidate = AigcTaskCandidate(
        task_id=source_task.id,
        seq_no=1,
        image_uri="s3://bucket/opt-source-cand.jpg",
        thumb_uri="s3://bucket/opt-source-cand-thumb.jpg",
        width=1024,
        height=1536,
        file_size=45678,
    )
    db.add(candidate)
    db.flush()

    return user, product, flatlay, source_task, candidate


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
    _bind_asset_product(db, flatlay.id, product.id, AssetProductRole.flatlay_primary)

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


def test_create_aigc_task_persists_and_appears_in_list(client, editor_token, db):
    product = _make_product(db, code="PERSIST-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)
    _bind_asset_product(db, flatlay.id, product.id, AssetProductRole.flatlay_primary)

    create_resp = client.post(
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
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    list_resp = client.get(
        "/aigc/tasks",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert list_resp.status_code == 200
    ids = {x["id"] for x in list_resp.json()}
    assert task_id in ids


def test_create_aigc_task_rejects_mismatched_product_for_flatlay(client, editor_token, db):
    linked_product = _make_product(db, code="LINKED-001")
    another_product = _make_product(db, code="OTHER-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)
    _bind_asset_product(db, flatlay.id, linked_product.id, AssetProductRole.flatlay_primary)

    resp = client.post(
        "/aigc/tasks",
        json={
            "product_id": str(another_product.id),
            "flatlay_asset_id": str(flatlay.id),
            "reference_source": "library",
            "reference_asset_id": str(ref.id),
            "consent_checked": True,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 422
    assert "must match flatlay-linked product" in resp.json()["detail"]


def test_optimize_candidate_creates_queued_task_with_lineage(client, editor_token, db):
    _, _, flatlay, source_task, candidate = _make_source_task_with_candidate(db)

    with patch("app.aigc.router._enqueue_aigc_generation") as mock_enqueue:
        resp = client.post(
            f"/aigc/candidates/{candidate.id}/optimize",
            json={},
            headers={"Authorization": f"Bearer {editor_token}"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "queued"
    assert data["workflow_type"] == "optimize_auto"
    assert data["source_task_id"] == str(source_task.id)
    assert data["source_candidate_id"] == str(candidate.id)
    assert data["reference_upload_uri"] == candidate.image_uri
    assert data["flatlay_asset_id"] == str(flatlay.id)
    mock_enqueue.assert_called_once()


def test_optimize_candidate_custom_requires_non_empty_prompt(client, editor_token, db):
    _, _, _, _, candidate = _make_source_task_with_candidate(db)

    resp = client.post(
        f"/aigc/candidates/{candidate.id}/optimize",
        json={"mode": "custom", "custom_prompt": "   "},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert resp.status_code == 422


def test_create_aigc_optimization_task_inherits_source_context(db):
    editor = _make_user(db)
    _, product, flatlay, source_task, candidate = _make_source_task_with_candidate(
        db,
        face_deidentify_enabled=False,
    )

    task = create_aigc_optimization_task(
        db,
        candidate_id=candidate.id,
        user=editor,
        body=AigcOptimizeCreateIn(candidate_count=2),
    )

    assert task.product_id == product.id
    assert task.flatlay_asset_id == flatlay.id
    assert task.flatlay_original_uri == source_task.flatlay_original_uri
    assert task.reference_source == "upload"
    assert task.reference_upload_uri == candidate.image_uri
    assert task.face_deidentify_enabled is False
    assert task.candidate_count == 2
    assert task.provider == source_task.provider
    assert task.model_name == source_task.model_name
    assert task.timeout_seconds == source_task.timeout_seconds
    assert task.template_version == source_task.template_version
    assert task.workflow_type == "optimize_auto"
    assert task.source_task_id == source_task.id
    assert task.source_candidate_id == candidate.id


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


def test_get_aigc_task_includes_candidates(client, editor_token, db):
    product = _make_product(db, code="GET-CANDS-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)

    user = User(
        email="aigc_get_candidates@example.com",
        password_hash=hash_password("pw"),
        name="GetCandidatesTester",
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
        image_uri="s3://bucket/cand-get.jpg",
        thumb_uri="s3://bucket/cand-get-thumb.jpg",
        width=1024,
        height=1536,
        file_size=50000,
    )
    db.add(candidate)
    db.flush()

    resp = client.get(
        f"/aigc/tasks/{task.id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["id"] == str(candidate.id)


def test_get_aigc_task_without_candidates_marks_failed(client, editor_token, db):
    product = _make_product(db, code="GET-EMPTY-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)

    user = User(
        email="aigc_get_empty@example.com",
        password_hash=hash_password("pw"),
        name="GetEmptyTester",
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

    resp = client.get(
        f"/aigc/tasks/{task.id}",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error_code"] == "EMPTY_GENERATION_RESULT"
    assert data["candidates"] == []


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


def test_get_candidate_file_proxy(client, editor_token, db):
    product = _make_product(db, code="FILE-001")
    flatlay = _make_flatlay_asset(db)

    creator = User(
        email="aigc_file_creator@example.com",
        password_hash=hash_password("pw"),
        name="FileCreator",
        role=UserRole.editor,
    )
    db.add(creator)
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
        created_by=creator.id,
    )
    db.add(task)
    db.flush()

    candidate = AigcTaskCandidate(
        task_id=task.id,
        seq_no=1,
        image_uri="s3://bucket/cand-file.jpg",
        thumb_uri="s3://bucket/cand-file-thumb.jpg",
    )
    db.add(candidate)
    db.flush()

    mock_storage = MagicMock()
    mock_storage.get_object.return_value = b"candidate-bytes"

    with patch("app.aigc.router.get_storage", return_value=mock_storage):
        resp = client.get(
            f"/aigc/candidates/{candidate.id}/file",
            params={"kind": "thumb", "access_token": editor_token},
        )

    assert resp.status_code == 200
    assert resp.content == b"candidate-bytes"
    mock_storage.get_object.assert_called_once()


def test_run_aigc_generation_optimize_auto_prompt_contains_quality_keywords(db):
    editor = _make_user(db)
    _, _, _, _, candidate = _make_source_task_with_candidate(db)
    task = create_aigc_optimization_task(
        db,
        candidate_id=candidate.id,
        user=editor,
        body=AigcOptimizeCreateIn(),
    )

    mock_storage = MagicMock()
    mock_storage.get_object.return_value = b"\xff\xd8fake-image-bytes"
    mock_storage.upload.side_effect = lambda key, *_args, **_kwargs: f"s3://bucket/{key}"
    mock_provider = MagicMock()
    mock_provider.build_request_payload.return_value = {"model": "x", "n": 1}
    mock_provider.generate.return_value = [b"img-1"]

    with patch("app.aigc.service.get_storage", return_value=mock_storage), patch(
        "app.aigc.provider_registry.get_provider", return_value=mock_provider
    ):
        run_aigc_generation(db, task.id)

    prompt = mock_provider.generate.call_args.kwargs["prompt"]
    for keyword in ["服装纹理", "脸部", "手部", "鞋子", "配饰"]:
        assert keyword in prompt

    prompt_log = db.query(AigcPromptLog).filter(AigcPromptLog.task_id == task.id).one()
    assert "服装纹理" in prompt_log.user_prompt


def test_run_aigc_generation_optimize_custom_prompt_contains_user_prompt(db):
    editor = _make_user(db)
    _, _, _, _, candidate = _make_source_task_with_candidate(db)
    task = create_aigc_optimization_task(
        db,
        candidate_id=candidate.id,
        user=editor,
        body=AigcOptimizeCreateIn(mode="custom", custom_prompt="加强高级感光影，并修复领口褶皱"),
    )

    mock_storage = MagicMock()
    mock_storage.get_object.return_value = b"\xff\xd8fake-image-bytes"
    mock_storage.upload.side_effect = lambda key, *_args, **_kwargs: f"s3://bucket/{key}"
    mock_provider = MagicMock()
    mock_provider.build_request_payload.return_value = {"model": "x", "n": 1}
    mock_provider.generate.return_value = [b"img-1"]

    with patch("app.aigc.service.get_storage", return_value=mock_storage), patch(
        "app.aigc.provider_registry.get_provider", return_value=mock_provider
    ):
        run_aigc_generation(db, task.id)

    prompt = mock_provider.generate.call_args.kwargs["prompt"]
    assert "加强高级感光影，并修复领口褶皱" in prompt
    assert "服装纹理" in prompt

    prompt_log = db.query(AigcPromptLog).filter(AigcPromptLog.task_id == task.id).one()
    assert "加强高级感光影，并修复领口褶皱" in prompt_log.user_prompt


def test_run_aigc_generation_empty_result_marks_failed(db):
    product = _make_product(db, code="EMPTY-IMG-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)
    _bind_asset_product(db, flatlay.id, product.id, AssetProductRole.flatlay_primary)

    user = User(
        email="empty_result@example.com",
        password_hash=hash_password("pw"),
        name="EmptyResultTester",
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

    mock_storage = MagicMock()
    mock_storage.get_object.return_value = b"\xff\xd8fake-image-bytes"
    mock_provider = MagicMock()
    mock_provider.generate.return_value = []

    with patch("app.aigc.service.get_storage", return_value=mock_storage), patch(
        "app.aigc.provider_registry.get_provider", return_value=mock_provider
    ):
        run_aigc_generation(db, task.id)

    db.flush()
    db.refresh(task)
    assert task.status == AigcTaskStatus.failed
    assert task.error_code == "EMPTY_GENERATION_RESULT"
    prompt_log = db.query(AigcPromptLog).filter(AigcPromptLog.task_id == task.id).one()
    assert prompt_log.request_payload_json["target_candidate_count"] == 2
    assert prompt_log.response_meta_json["error_code"] == "EMPTY_GENERATION_RESULT"
    assert prompt_log.response_meta_json["generated_candidate_count"] == 0


def test_run_aigc_generation_topups_to_candidate_count_and_logs_audit(db):
    product = _make_product(db, code="TOPUP-001")
    flatlay = _make_flatlay_asset(db)
    ref = _make_ref_asset(db)
    _bind_asset_product(db, flatlay.id, product.id, AssetProductRole.flatlay_primary)

    user = User(
        email="topup_result@example.com",
        password_hash=hash_password("pw"),
        name="TopupResultTester",
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
        candidate_count=3,
        status=AigcTaskStatus.queued,
        provider="seedream_ark",
        model_name="doubao-seedream-4-5-251128",
        timeout_seconds=900,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    mock_storage = MagicMock()
    mock_storage.get_object.return_value = b"\xff\xd8fake-image-bytes"
    mock_storage.upload.side_effect = lambda key, *_args, **_kwargs: f"s3://bucket/{key}"
    mock_provider = MagicMock()
    mock_provider.build_request_payload.return_value = {"model": "x", "n": 3}
    mock_provider.generate.side_effect = [[b"img-1"], [b"img-2", b"img-3"]]

    with patch("app.aigc.service.get_storage", return_value=mock_storage), patch(
        "app.aigc.provider_registry.get_provider", return_value=mock_provider
    ):
        run_aigc_generation(db, task.id)

    db.flush()
    db.refresh(task)
    assert task.status == AigcTaskStatus.review_pending

    candidates = (
        db.query(AigcTaskCandidate)
        .filter(AigcTaskCandidate.task_id == task.id)
        .order_by(AigcTaskCandidate.seq_no.asc())
        .all()
    )
    assert len(candidates) == 3
    assert [c.seq_no for c in candidates] == [1, 2, 3]

    assert mock_provider.generate.call_count == 2
    assert mock_provider.generate.call_args_list[0].kwargs["candidate_count"] == 3
    assert mock_provider.generate.call_args_list[1].kwargs["candidate_count"] == 2

    prompt_log = db.query(AigcPromptLog).filter(AigcPromptLog.task_id == task.id).one()
    assert prompt_log.request_payload_json["target_candidate_count"] == 3
    assert prompt_log.response_meta_json["generated_candidate_count"] == 3
    assert len(prompt_log.response_meta_json["attempts"]) == 2
