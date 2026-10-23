from api.schemas import ConfigView

TOP_LEVEL_KEYS = {
    "app",
    "window_weeks",
    "max_themes",
    "taxonomy",
    "ranking",
    "pulse",
    "models",
    "batch_size",
    "draft_to",
    "doc_url",
}


def test_config_is_allow_list(client, settings, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "sk-test-secret")
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == TOP_LEVEL_KEYS == set(ConfigView.model_fields)
    assert set(body["app"]) == {"play_package", "play_lang", "play_country"}
    assert set(body["pulse"]) == {"max_words", "min_reviews", "min_words", "max_analysed"}
    assert set(body["models"]) == {"theme_assign", "compose", "judge"}
    assert set(body["ranking"]) == {"weights", "recency_window_weeks"}

    text = response.text
    assert "server_dir" not in text
    assert "mcp-server-4" not in text
    assert str(settings.config.mcp.server_dir) not in text
    assert "GROQ" not in text
    assert "sk-test-secret" not in text

    assert body["doc_url"].endswith("/edit")
    assert body["doc_url"] == (
        f"https://docs.google.com/document/d/{settings.config.mcp.document_id}/edit"
    )
    assert body["ranking"]["weights"] == {"volume": 0.5, "recency": 0.2, "severity": 0.3}
    assert body["batch_size"] == 40
    assert body["models"]["theme_assign"] == settings.config.models["theme_assign"]


def test_doc_url_is_null_without_document_id(settings):
    from dataclasses import replace

    from api.routes import build_config_view

    mcp = replace(settings.config.mcp, document_id=None)
    view = build_config_view(replace(settings, config=replace(settings.config, mcp=mcp)))
    assert view.doc_url is None


def test_cors_allows_only_vite_origins(client):
    def preflight(origin):
        return client.options(
            "/api/config",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        assert preflight(origin).headers["access-control-allow-origin"] == origin
    assert "access-control-allow-origin" not in preflight("http://evil.example").headers
