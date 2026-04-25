import asyncio

import authlib.jose.errors as jose_errors


def test_set_clerk_session_expired_token_clears(monkeypatch):
    """Expired tokens should not crash the handler; they should clear session."""
    # Import inside the test so the module is importable in different test layouts.
    # We need the actual module object (not just ClerkState) to monkeypatch jwt.decode
    # where it's used. importlib is required because reflex_clerk_api.clerk_provider
    # resolves to the function via __init__.py re-exports.
    import importlib

    clerk_provider_module = importlib.import_module("reflex_clerk_api.clerk_provider")
    from reflex_clerk_api.clerk_provider import ClerkState

    # Instantiate state in a framework-safe way for tests.
    state = ClerkState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]

    async def fake_get_jwk_keys(self):
        return {}

    monkeypatch.setattr(ClerkState, "_get_jwk_keys", fake_get_jwk_keys, raising=True)

    validate_calls: dict[str, object] = {}

    class FakeClaims:
        def validate(self, leeway=None):
            validate_calls["leeway"] = leeway
            raise jose_errors.ExpiredTokenError()

    monkeypatch.setattr(
        clerk_provider_module.jwt,
        "decode",
        lambda *args, **kwargs: FakeClaims(),
        raising=True,
    )

    result = asyncio.run(
        ClerkState.set_clerk_session.fn(state, token="fake")  # pyright: ignore[reportAttributeAccessIssue]
    )
    assert validate_calls["leeway"] == 60
    assert result == ClerkState.clear_clerk_session


def test_clerk_session_synchronizer_js_contains_reconnect_safe_deps_and_skipcache():
    """String-based regression test for the generated JS."""
    from reflex_clerk_api.clerk_provider import ClerkSessionSynchronizer

    js = ClerkSessionSynchronizer.create().add_custom_code()[0]
    assert "[isLoaded, isSignedIn, addEvents, getToken]" in js
    assert "skipCache: true" in js
