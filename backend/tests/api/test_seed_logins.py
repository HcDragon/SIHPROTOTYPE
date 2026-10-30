from app.seed.data import DEMO_USERS
from app.seed.service import seed_demo_data


def test_seeded_users_log_in_with_demo_password(client, db_session, settings):
    seed_demo_data(db_session, settings)
    db_session.commit()
    for demo in DEMO_USERS:
        response = client.post(
            "/api/v1/auth/login", json={"email": demo.email, "password": settings.demo_password}
        )
        expected = 200 if demo.is_active else 401
        assert response.status_code == expected, demo.email
        if demo.is_active:
            token = response.json()["access_token"]
            me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.json()["role"] == demo.role.value
