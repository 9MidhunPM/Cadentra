"""Production socket/header trust and actual identity limiter regression coverage."""

from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
from app.core import auth
from app.core.config import Settings
from app.db.session import get_session
from app.modules.identity import router as identity
from app.modules.identity.rate_limit import reset_rate_limits


@pytest.fixture(autouse=True)
def clear_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def application(monkeypatch):
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_origin="https://cadentra.example",
        allowed_origins=("https://cadentra.example",),
        session_cookie_secure=True,
        trusted_web_proxy_ips=("172.31.250.2", "fd00::2"),
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    app = main.create_app()
    # Health DB behavior is outside these middleware tests: this adapter only
    # lets accepted readiness requests reach the existing health handler.
    app.dependency_overrides[get_session] = lambda: SimpleNamespace(
        execute=lambda statement: None, scalar=lambda statement: "test-migration"
    )

    @app.get("/test/client")
    def client_address(request: Request):
        return {"client_ip": request.state.client_ip}

    @app.post("/test/public")
    def public_write(request: Request, account: str = ""):
        identity.public_write(request, "proxy-test", account)
        return {"accepted": True}

    return app


def headers(address="203.0.113.9"):
    return {"Origin": "https://cadentra.example", "X-Cadentra-Client-IP": address}


@pytest.mark.parametrize(
    "peer,address", [("172.31.250.2", "203.0.113.9"), ("fd00::2", "2001:db8::123")]
)
def test_trusted_socket_and_canonical_ipv4_ipv6(application, peer, address):
    with TestClient(application, client=(peer, 1234)) as client:
        response = client.get("/test/client", headers=headers(address))
    assert response.status_code == 200
    assert response.json()["client_ip"] == address


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "junk",
        "203.0.113.1, 203.0.113.2",
        " 203.0.113.1",
        "203.0.113.1 ",
        "203.0.113.0/24",
        "2001:DB8::1",
        "fe80::1%eth0",
        "203.000.113.1",
    ],
)
def test_missing_invalid_or_noncanonical_header_rejected(application, value):
    request_headers = {} if value is None else {"X-Cadentra-Client-IP": value}
    with TestClient(application, client=("172.31.250.2", 1234)) as client:
        response = client.get("/test/client", headers=request_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNTRUSTED_PROXY"
    assert response.json()["error"]["fields"] == {}
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
    assert "172.31.250.2" not in response.text
    if value:
        assert value not in response.text


def test_duplicate_private_header_is_rejected(application):
    with TestClient(application, client=("172.31.250.2", 1234)) as client:
        response = client.get(
            "/test/client",
            headers=[
                ("X-Cadentra-Client-IP", "203.0.113.1"),
                ("x-cadentra-client-ip", "203.0.113.2"),
            ],
        )
    assert response.status_code == 403


@pytest.mark.parametrize("peer", ["203.0.113.2", "172.31.250.3", "127.0.0.1", "::1"])
def test_untrusted_socket_cannot_forge_forwarding_headers(application, peer):
    with TestClient(application, client=(peer, 1234)) as client:
        response = client.post(
            "/test/public",
            headers={
                **headers(),
                "X-Forwarded-For": "172.31.250.2",
                "Forwarded": "for=172.31.250.2",
            },
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNTRUSTED_PROXY"


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_only_loopback_readiness_methods_bypass_proxy_header(application, peer, method):
    with TestClient(application, client=(peer, 1234)) as client:
        assert client.request(method, "/api/v1/health").status_code == 200
        assert client.get("/test/client").status_code == 403
        assert client.post("/api/v1/health").status_code == 403


def test_untrusted_nonloopback_cannot_access_readiness(application):
    with TestClient(application, client=("172.31.250.3", 1234)) as client:
        assert client.get("/api/v1/health").status_code == 403


def test_client_ip_quota_is_separate_behind_same_proxy(application):
    with TestClient(application, client=("172.31.250.2", 1234)) as client:
        for _ in range(30):
            assert (
                client.post("/test/public", headers=headers("203.0.113.1")).status_code
                == 200
            )
        assert (
            client.post("/test/public", headers=headers("203.0.113.1")).status_code
            == 429
        )
        assert (
            client.post("/test/public", headers=headers("203.0.113.2")).status_code
            == 200
        )


def test_account_quota_still_shared_across_client_ips(application):
    with TestClient(application, client=("172.31.250.2", 1234)) as client:
        for address in ("203.0.113.1", "203.0.113.2"):
            for _ in range(5):
                assert (
                    client.post(
                        "/test/public?account=target@example.com",
                        headers=headers(address),
                    ).status_code
                    == 200
                )
        assert (
            client.post(
                "/test/public?account=target@example.com",
                headers=headers("203.0.113.3"),
            ).status_code
            == 429
        )
        assert (
            client.post(
                "/test/public?account=other@example.com", headers=headers("203.0.113.3")
            ).status_code
            == 200
        )


def test_origin_check_still_applies_after_proxy_verification(application):
    with TestClient(application, client=("172.31.250.2", 1234)) as client:
        response = client.post(
            "/test/public", headers={"X-Cadentra-Client-IP": "203.0.113.1"}
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ORIGIN"


@pytest.mark.parametrize(
    "proxies",
    [(), ("*",), ("172.31.250.0/24",), ("proxy.internal",), ("fe80::1%eth0",), ("",)],
)
def test_production_settings_require_explicit_ip_literals(proxies):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_origin="https://cadentra.example",
            allowed_origins=("https://cadentra.example",),
            session_cookie_secure=True,
            trusted_web_proxy_ips=proxies,
        )


def test_nonproduction_ignores_forwarding_header_and_retains_socket(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))
    app = main.create_app()

    @app.get("/test/client")
    def address(request: Request):
        return {"client_ip": request.state.client_ip}

    with TestClient(app, client=("198.51.100.7", 1234)) as client:
        response = client.get("/test/client", headers=headers("203.0.113.1"))
    assert response.json()["client_ip"] == "198.51.100.7"
