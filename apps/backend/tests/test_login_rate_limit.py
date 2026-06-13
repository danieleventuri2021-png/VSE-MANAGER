from app.services import auth_service
from app.services.auth_service import (
    LOGIN_MAX_ATTEMPTS,
    check_login_rate_limit,
    register_failed_login,
    reset_login_attempts,
)


def test_allows_attempts_under_threshold():
    key = "1.2.3.4:mario"
    reset_login_attempts(key)
    for _ in range(LOGIN_MAX_ATTEMPTS - 1):
        assert check_login_rate_limit(key) is None
        register_failed_login(key)
    assert check_login_rate_limit(key) is None
    reset_login_attempts(key)


def test_blocks_after_threshold():
    key = "1.2.3.4:luigi"
    reset_login_attempts(key)
    for _ in range(LOGIN_MAX_ATTEMPTS):
        register_failed_login(key)
    wait = check_login_rate_limit(key)
    assert wait is not None and wait > 0
    reset_login_attempts(key)


def test_reset_clears_block():
    key = "1.2.3.4:peach"
    for _ in range(LOGIN_MAX_ATTEMPTS):
        register_failed_login(key)
    assert check_login_rate_limit(key) is not None
    reset_login_attempts(key)
    assert check_login_rate_limit(key) is None


def test_window_expiry_releases_block(monkeypatch):
    key = "1.2.3.4:bowser"
    reset_login_attempts(key)
    base = 1000.0
    monkeypatch.setattr(auth_service.time, "monotonic", lambda: base)
    for _ in range(LOGIN_MAX_ATTEMPTS):
        register_failed_login(key)
    assert check_login_rate_limit(key) is not None
    monkeypatch.setattr(auth_service.time, "monotonic", lambda: base + auth_service.LOGIN_WINDOW_SECONDS + 1)
    assert check_login_rate_limit(key) is None
    reset_login_attempts(key)
