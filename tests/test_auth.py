import json
import base64
import logging
import pytest
import itsdangerous
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from core.config.settings import get_settings

settings = get_settings()

# follow_redirects=False so we can assert on 303 responses directly
client = TestClient(app, follow_redirects=False)


def make_session_cookie(data: dict) -> str:
    """Create a signed Starlette session cookie with the given session data."""
    signer = itsdangerous.TimestampSigner(settings.SECRET_KEY)
    raw = base64.b64encode(json.dumps(data).encode("utf-8"))
    return signer.sign(raw).decode("utf-8")


FAKE_TOKEN = {"access_token": "fake-token", "token_type": "Bearer"}


# ---------------------------------------------------------------------------
# get_access_token()
# ---------------------------------------------------------------------------

class TestGetAccessToken:
    def test_no_session_redirects_to_login(self):
        """Protected route without a session token redirects to /login_sw."""
        response = client.get("/groups")
        assert response.status_code == 303
        assert response.headers["location"] == "/login_sw"

    def test_splitwise_init_failure_redirects_to_login(self):
        """If Splitwise() raises (e.g. bad credentials), redirect to /login_sw."""
        cookie = make_session_cookie({"access_token": FAKE_TOKEN})
        with patch("api.routes.auth.Splitwise", side_effect=Exception("bad key")):
            response = client.get("/groups", cookies={"session": cookie})
        assert response.status_code == 303
        assert response.headers["location"] == "/login_sw"

    def test_set_token_failure_redirects_to_login(self):
        """If setOAuth2AccessToken raises, redirect to /login_sw."""
        cookie = make_session_cookie({"access_token": FAKE_TOKEN})
        with patch("api.routes.auth.Splitwise") as MockSW:
            mock_obj = MagicMock()
            MockSW.return_value = mock_obj
            mock_obj.setOAuth2AccessToken.side_effect = Exception("token error")
            response = client.get("/groups", cookies={"session": cookie})
        assert response.status_code == 303
        assert response.headers["location"] == "/login_sw"


# ---------------------------------------------------------------------------
# /authorize route
# ---------------------------------------------------------------------------

class TestAuthorizeRoute:
    def test_token_exchange_exception_shows_error(self):
        """`getOAuth2AccessToken` raising an exception renders the error page."""
        cookie = make_session_cookie({"state": "xyz"})
        with patch("api.routes.auth.Splitwise") as MockSW:
            MockSW.return_value.getOAuth2AccessToken.side_effect = Exception("network error")
            response = client.get("/authorize", params={"code": "abc", "state": "xyz"}, cookies={"session": cookie})
        assert response.status_code == 200
        assert "Could not complete authorization" in response.text

    def test_none_token_shows_error(self):
        """`getOAuth2AccessToken` returning None renders the error page."""
        cookie = make_session_cookie({"state": "xyz"})
        with patch("api.routes.auth.Splitwise") as MockSW:
            MockSW.return_value.getOAuth2AccessToken.return_value = None
            response = client.get("/authorize", params={"code": "abc", "state": "xyz"}, cookies={"session": cookie})
        assert response.status_code == 200
        assert "Splitwise denied" in response.text

    def test_state_mismatch_returns_400(self, caplog):
        """State mismatch logs a WARNING and returns 400 — flow must not complete."""
        cookie = make_session_cookie({"state": "correct_state"})
        with patch("api.routes.auth.Splitwise") as MockSW:
            mock_obj = MagicMock()
            MockSW.return_value = mock_obj
            mock_obj.getOAuth2AccessToken.return_value = FAKE_TOKEN
            mock_obj.getCurrentUser.return_value = MagicMock(id=1, first_name="Test")
            with caplog.at_level(logging.WARNING):
                response = client.get(
                    "/authorize",
                    params={"code": "abc", "state": "wrong_state"},
                    cookies={"session": cookie},
                )
        assert response.status_code == 400
        assert any("state mismatch" in r.message.lower() for r in caplog.records)

    def test_successful_auth_renders_success_page(self):
        """Successful OAuth flow renders authorize_success.html."""
        cookie = make_session_cookie({"state": "xyz"})
        with patch("api.routes.auth.Splitwise") as MockSW:
            mock_obj = MagicMock()
            MockSW.return_value = mock_obj
            mock_obj.getOAuth2AccessToken.return_value = FAKE_TOKEN
            mock_obj.getCurrentUser.return_value = MagicMock(id=42, first_name="Test")
            response = client.get("/authorize", params={"code": "abc", "state": "xyz"}, cookies={"session": cookie})
        assert response.status_code == 200
        assert "authorize_success" in response.template.name


# ---------------------------------------------------------------------------
# Full authorization cycle
# ---------------------------------------------------------------------------

class TestFullAuthCycle:
    def test_login_authorize_then_access_protected_route(self):
        """
        Full OAuth cycle:
          1. /login_sw   — state stored in session, redirected to Splitwise
          2. /authorize  — code exchanged for token, token stored in session
          3. /groups     — protected route accessed successfully with the session token
        The TestClient context manager carries the session cookie between steps.
        """
        with TestClient(app, follow_redirects=False) as c:

            # Step 1 — /login_sw
            with patch("api.routes.auth.Splitwise") as MockSW:
                mock_obj = MagicMock()
                MockSW.return_value = mock_obj
                mock_obj.getOAuth2AuthorizeURL.return_value = (
                    "https://secure.splitwise.com/oauth/authorize?state=test_state",
                    "test_state",
                )
                response = c.get("/login_sw")

            assert response.status_code == 307  # redirect to Splitwise
            # Session cookie is now set with state="test_state"

            # Step 2 — /authorize (Splitwise redirects back with code + state)
            with patch("api.routes.auth.Splitwise") as MockSW:
                mock_obj = MagicMock()
                MockSW.return_value = mock_obj
                mock_obj.getOAuth2AccessToken.return_value = FAKE_TOKEN
                mock_obj.getCurrentUser.return_value = MagicMock(id=42, first_name="Test")
                response = c.get("/authorize", params={"code": "auth_code", "state": "test_state"})

            assert response.status_code == 200
            assert "authorize_success" in response.template.name
            # Session cookie now also contains access_token

            # Step 3 — access a protected route using the session token
            with patch("api.routes.auth.Splitwise") as MockSW:
                mock_obj = MagicMock()
                MockSW.return_value = mock_obj
                mock_obj.getGroups.return_value = []
                response = c.get("/groups")

            assert response.status_code == 200


# ---------------------------------------------------------------------------
# /logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_redirects_to_home(self):
        cookie = make_session_cookie({"access_token": FAKE_TOKEN})
        response = client.get("/logout", cookies={"session": cookie})
        assert response.status_code == 307
        assert response.headers["location"] == "/"
