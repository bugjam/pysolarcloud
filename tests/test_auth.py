"""Tests for iSolarCloud authentication URLs."""

import pytest

from pysolarcloud import Auth, PySolarCloudException, Server


def test_india_auth_url() -> None:
    """India uses its regional web portal and cloud ID."""
    auth = Auth(Server.India, "app-key", "secret", "123", websession=object())

    assert auth.host == "https://gateway.isolarcloud.in"
    assert auth.auth_url("https://example.com/callback") == (
        "https://web3.isolarcloud.in/#/authorized-app?cloudId=9&applicationId=123"
        "&redirectUrl=https%3A%2F%2Fexample.com%2Fcallback"
    )


def test_auth_url_places_state_before_fragment() -> None:
    """State is returned when it is sent before the SPA fragment."""
    auth = Auth(Server.Europe, "app-key", "secret", "123", websession=object())

    assert auth.auth_url("https://example.com/callback", state="flow/123") == (
        "https://web3.isolarcloud.eu?state=flow%2F123#/authorized-app?cloudId=3"
        "&applicationId=123&redirectUrl=https%3A%2F%2Fexample.com%2Fcallback"
    )


def test_auth_url_rejects_unknown_server() -> None:
    """Unknown servers produce a descriptive library error."""
    auth = Auth(
        "https://unknown.example.com",
        "app-key",
        "secret",
        "123",
        websession=object(),
    )

    with pytest.raises(
        PySolarCloudException,
        match="Unsupported iSolarCloud server: https://unknown.example.com",
    ):
        auth.auth_url("https://example.com/callback")
