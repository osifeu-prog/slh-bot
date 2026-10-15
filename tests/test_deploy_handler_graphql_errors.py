import requests
import pytest

import handlers.deploy_handler as target


def test_logs_client_uses_canonical_railway_graphql_endpoint():
    assert target.RAILWAY_API_URL == "https://backboard.railway.com/graphql/v2"


def test_http_graphql_error_surfaces_sanitized_validation_detail(monkeypatch):
    class Response:
        status_code = 400

        def raise_for_status(self):
            raise requests.HTTPError("400 Client Error: Bad Request")

        def json(self):
            return {
                "errors": [
                    {
                        "message": (
                            "Cannot query field 'deploymentLogs'. "
                            "Bearer railway-secret-value"
                        )
                    }
                ]
            }

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(target.requests, "post", fake_post)

    with pytest.raises(RuntimeError) as exc:
        target._graphql("secret-token", "query { deploymentLogs }", {})

    assert captured["url"] == "https://backboard.railway.com/graphql/v2"
    assert captured["kwargs"]["timeout"] == 20
    assert "RAILWAY_HTTP_400" in str(exc.value)
    assert "Cannot query field" in str(exc.value)
    assert "railway-secret-value" not in str(exc.value)
    assert "secret-token" not in str(exc.value)


def test_http_graphql_error_without_json_body_returns_bounded_status(monkeypatch):
    class Response:
        status_code = 400

        def raise_for_status(self):
            raise requests.HTTPError("400 Client Error: Bad Request")

        def json(self):
            raise ValueError("not JSON")

    monkeypatch.setattr(target.requests, "post", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError, match="^RAILWAY_HTTP_400$"):
        target._graphql("secret-token", "query { x }", {})


def test_graphql_errors_from_success_http_response_are_sanitized(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"errors": [{"message": "Bad token=secret-value"}]}

    monkeypatch.setattr(target.requests, "post", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError) as exc:
        target._graphql("secret-token", "query { x }", {})

    assert "Bad token=[REDACTED]" in str(exc.value)
    assert "secret-value" not in str(exc.value)
    assert "secret-token" not in str(exc.value)
