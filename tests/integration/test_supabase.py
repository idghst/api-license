import os

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration

_SKIP_MESSAGE = "Supabase integration credentials are not set"


@pytest.fixture(scope="module")
def live_settings() -> tuple[Settings, str]:
    url = os.getenv("SUPABASE_URL")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    access_token = os.getenv("SUPABASE_TEST_ACCESS_TOKEN")
    if not all((url, publishable_key, access_token)) or (
        url == "https://test.supabase.co" and publishable_key == "sb_publishable_test"
    ):
        pytest.skip(_SKIP_MESSAGE)

    return (
        Settings(
            SUPABASE_URL=url,
            SUPABASE_PUBLISHABLE_KEY=SecretStr(publishable_key),
        ),
        access_token,
    )


def test_auth_health_endpoint_is_available(live_settings: tuple[Settings, str]) -> None:
    settings, _ = live_settings

    response = httpx.get(
        f"{str(settings.SUPABASE_URL).rstrip('/')}/auth/v1/health",
        headers={"apikey": settings.SUPABASE_PUBLISHABLE_KEY.get_secret_value()},
        timeout=settings.SUPABASE_TIMEOUT_SECONDS,
    )

    assert 200 <= response.status_code < 300


def test_me_accepts_a_real_access_token(live_settings: tuple[Settings, str]) -> None:
    settings, access_token = live_settings

    response = TestClient(create_app(settings)).get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"]


def test_license_schema_is_exposed_to_data_api(
    live_settings: tuple[Settings, str],
) -> None:
    settings, access_token = live_settings

    response = httpx.get(
        f"{str(settings.SUPABASE_URL).rstrip('/')}/rest/v1/",
        headers={
            "apikey": settings.SUPABASE_PUBLISHABLE_KEY.get_secret_value(),
            "Authorization": f"Bearer {access_token}",
            "Accept-Profile": "license",
        },
        timeout=settings.SUPABASE_TIMEOUT_SECONDS,
    )

    assert 200 <= response.status_code < 300, response.text
