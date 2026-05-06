def test_ping_returns_ok(client):
    res = client.get("/api/ping")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["schema_version"] >= 1
    assert "now" in body


def test_index_route_resolves(client):
    """Whether the frontend has been built or not, GET / should respond
    with HTML — built index when `backend/static/index.html` exists,
    placeholder otherwise."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"<" in res.data


def test_static_route_does_not_shadow_api(client, app):
    """static_url_path='/' registers /<path:filename> — make sure /api/ping
    still routes to the API, not to a static lookup."""
    res = client.get("/api/ping")
    assert res.status_code == 200
    assert res.is_json


def test_migrations_idempotent(app):
    """Re-running create_app on the same DB shouldn't re-apply migrations."""
    from backend.app import create_app
    db_path = app.config["DATABASE_PATH"]
    app2 = create_app(database_path=db_path)
    with app2.test_client() as c:
        res = c.get("/api/ping")
        assert res.status_code == 200
        assert res.get_json()["schema_version"] == 1
