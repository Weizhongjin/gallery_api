from app.auth.models import User, UserRegistrationRequest, UserRole
from app.auth.service import hash_password, create_access_token


def test_admin_can_approve_registration_request(client, db):
    # Create an admin user for auth
    admin = User(
        email="admin-approve@example.com",
        password_hash=hash_password("pw"),
        name="Admin Approve",
        role=UserRole.admin,
    )
    db.add(admin)
    db.flush()
    admin_token = create_access_token(str(admin.id))

    req = UserRegistrationRequest(
        email="approve@example.com",
        password_hash=hash_password("secret123"),
        name="Approve Me",
    )
    db.add(req)
    db.flush()

    response = client.post(
        f"/users/registration-requests/{req.id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "approve@example.com"
    assert response.json()["role"] == "viewer"
    assert db.query(UserRegistrationRequest).filter_by(email="approve@example.com").first() is None


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


def test_login_with_wrong_password_on_pending_does_not_reveal_existence(client, db):
    db.add(
        UserRegistrationRequest(
            email="pending-secret@example.com",
            password_hash=hash_password("secret123"),
            name="Pending Secret",
        )
    )
    db.flush()

    response = client.post(
        "/auth/login",
        json={"email": "pending-secret@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert "待审核" not in response.json()["detail"]
