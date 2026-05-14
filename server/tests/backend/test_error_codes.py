import ast
import json
import re
from pathlib import Path

from apps.backend.app.errors.codes import ErrorCode


def test_all_error_codes_have_zh_translation():
    """Every ErrorCode must have a corresponding key in zh-CN.json."""
    locale_path = Path(__file__).parent.parent.parent / "apps" / "backend" / "app" / "errors" / "locales" / "zh-CN.json"
    messages = json.loads(locale_path.read_text(encoding="utf-8"))

    missing = [code.value for code in ErrorCode if code.value not in messages]
    assert not missing, f"Missing zh-CN translations for: {missing}"


def test_all_error_codes_have_en_translation():
    """Every ErrorCode must have a corresponding key in en-US.json."""
    locale_path = Path(__file__).parent.parent.parent / "apps" / "backend" / "app" / "errors" / "locales" / "en-US.json"
    messages = json.loads(locale_path.read_text(encoding="utf-8"))

    missing = [code.value for code in ErrorCode if code.value not in messages]
    assert not missing, f"Missing en-US translations for: {missing}"


def test_no_bare_http_exception_in_routers():
    """No router or middleware file should raise HTTPException directly.

    Use # noqa: allow-http-exception on a line to exempt it.
    """
    routers_dir = Path(__file__).parent.parent.parent / "apps" / "backend" / "app" / "routers"
    middleware_dir = Path(__file__).parent.parent.parent / "apps" / "backend" / "app" / "middleware"

    violations = []

    for directory in [routers_dir, middleware_dir]:
        for py_file in directory.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            lines = source.splitlines()

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Raise):
                    continue
                exc = node.exc
                if exc is None:
                    continue
                # Match: raise HTTPException(...)
                if isinstance(exc, ast.Call):
                    func = exc.func
                    name = None
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    if name == "HTTPException":
                        line_no = node.lineno - 1  # 0-indexed
                        line_text = lines[line_no] if line_no < len(lines) else ""
                        if "# noqa: allow-http-exception" not in line_text:
                            violations.append(f"{py_file.name}:{node.lineno}")

    assert not violations, (
        "Bare HTTPException raises found (use AppError instead):\n" + "\n".join(violations)
    )


def test_app_error_returns_envelope(client):
    """AppError should return a structured envelope with code and message."""
    response = client.get("/api/v1/assets")
    assert response.status_code == 401
    body = response.json()
    assert "code" in body
    assert "message" in body
    assert "data" in body
    assert body["data"] is None
    assert "request_id" in body


def test_request_id_in_response_header(client):
    """Every response should include X-Request-ID header."""
    response = client.get("/api/v1/assets")
    assert "x-request-id" in {k.lower() for k in response.headers}


def test_request_id_passthrough(client):
    """Client-supplied X-Request-ID should be echoed back."""
    custom_id = "test-request-abc123"
    response = client.get("/api/v1/assets", headers={"X-Request-ID": custom_id})
    assert response.headers.get("x-request-id") == custom_id


def test_validation_error_returns_details(client):
    """422 validation errors should return details array with field-level codes."""
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "details" in body
    assert isinstance(body["details"], list)
    assert len(body["details"]) > 0
    detail = body["details"][0]
    assert "field" in detail
    assert "code" in detail
    assert "msg" in detail


def test_success_response_envelope(client, auth_headers):
    """Success responses should be wrapped in envelope."""
    response = client.get("/api/v1/assets", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "OK"
    assert body["message"] == ""
    assert "data" in body


def test_accept_language_zh(client):
    """zh-CN Accept-Language should return Chinese error messages."""
    response = client.get("/api/v1/assets", headers={"Accept-Language": "zh-CN"})
    body = response.json()
    assert body["message"]


def test_accept_language_en(client):
    """en-US Accept-Language should return English error messages."""
    response = client.get("/api/v1/assets", headers={"Accept-Language": "en-US"})
    body = response.json()
    assert body["message"]
    assert not re.search(r'[\u4e00-\u9fff]', body["message"])
