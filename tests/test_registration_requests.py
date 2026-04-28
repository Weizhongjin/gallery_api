from app.auth.models import User, UserRegistrationRequest, UserRole
from app.auth.service import hash_password


def test_register_request_creates_pending_record(client, db):
    response = client.post(
        "/auth/register",
        json={"email": "new-user@example.com", "password": "secret123", "name": "New User"},
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True, "message": "注册申请已提交，等待管理员审核"}

    pending = db.query(UserRegistrationRequest).filter_by(email="new-user@example.com").one()
    assert pending.name == "New User"
    assert pending.password_hash != "secret123"


def test_register_request_rejects_existing_user_email(client, db):
    db.add(
        User(
            email="dup@example.com",
            password_hash=hash_password("pw"),
            name="Dup",
            role=UserRole.viewer,
        )
    )
    db.flush()

    response = client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "secret123", "name": "Dup Again"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "该邮箱已存在正式账号"


def test_register_request_rejects_existing_pending_email(client, db):
    db.add(
        UserRegistrationRequest(
            email="wait@example.com",
            password_hash=hash_password("pw"),
            name="Waiting",
        )
    )
    db.flush()

    response = client.post(
        "/auth/register",
        json={"email": "wait@example.com", "password": "secret123", "name": "Waiting Again"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "该邮箱已有待审核申请"


def test_login_with_pending_registration_request_returns_review_message(client, db):
    db.add(
        UserRegistrationRequest(
            email="pending@example.com",
            password_hash=hash_password("secret123"),
            name="Pending User",
        )
    )
    db.flush()

    response = client.post(
        "/auth/login",
        json={"email": "pending@example.com", "password": "secret123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "账号待审核，暂时不能登录"
