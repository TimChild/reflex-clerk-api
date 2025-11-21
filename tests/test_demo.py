import logging
import os
import uuid
from pathlib import Path
from typing import Iterator

import clerk_backend_api
import pytest
from clerk_backend_api import Clerk, User
from dotenv import load_dotenv
from playwright.sync_api import Page, expect
from reflex.testing import AppHarness

load_dotenv()

TEST_EMAIL = "ci-test+clerk_test@gmail.com"
TEST_PASSWORD = "test-clerk-password"

PAGE_LOAD_TIMEOUT = 10000 if not os.getenv("CI") else 30000
INTERACTION_TIMEOUT = 2000 if not os.getenv("CI") else 20000


@pytest.fixture(scope="session")
def demo_app():
    app_root = Path(__file__).parent.parent / "clerk_api_demo"
    with AppHarness.create(root=app_root) as harness:
        yield harness


@pytest.fixture(scope="function")
def page(
    request: pytest.FixtureRequest, demo_app: AppHarness, page: Page
) -> Iterator[Page]:
    """Load the demo app main page."""
    page.set_default_timeout(PAGE_LOAD_TIMEOUT)
    assert demo_app.frontend_url is not None
    page.goto(demo_app.frontend_url)
    page.set_default_timeout(INTERACTION_TIMEOUT)
    yield page
    if request.session.testsfailed:
        logging.error("Test failed. Saving screenshot as playwright_test_error.png")
        page.screenshot(path="playwright_test_error.png")


@pytest.fixture()
def clerk_client() -> Iterator[Clerk]:
    """Create clerk backend api client."""
    secret_key = os.environ["CLERK_SECRET_KEY"]
    with clerk_backend_api.Clerk(bearer_auth=secret_key) as client:
        yield client


def test_clerk_client(clerk_client: Clerk):
    """Really basic test that the clerk client is working."""
    # NOTE: Getting a deprecation warning here, but not sure why...
    #  Warning message is not helpful.
    existing = clerk_client.users.list(request={"email_address": [TEST_EMAIL]})
    assert existing is not None


@pytest.fixture
def create_test_user(clerk_client: Clerk) -> User:
    """Creates (or checks already exists) a test clerk user.

    This can then be used to sign in during tests.
    """
    existing = clerk_client.users.list(request={"email_address": [TEST_EMAIL]})
    if existing is not None and len(existing) > 0:
        if len(existing) != 1:
            raise SetupError(
                "Multiple test users found with same email... This should not happen."
            )
        logging.error("Test user already exists.")
        return existing[0]

    logging.error("Creating test user...")
    res = clerk_client.users.create(
        request={
            "external_id": "ext-id-" + uuid.uuid4().hex[:5],
            "first_name": "John",
            "last_name": "Doe",
            "email_address": [
                TEST_EMAIL,
            ],
            "username": "fake_username_" + uuid.uuid4().hex[:5],
            "password": TEST_PASSWORD,
            "skip_password_checks": False,
            "skip_password_requirement": False,
            "public_metadata": {
                "role": "user",
            },
            "private_metadata": {
                "internal_id": "789",
            },
            "unsafe_metadata": {
                "preferences": {
                    "theme": "dark",
                },
            },
            "delete_self_enabled": True,
            "skip_legal_checks": False,
            "create_organization_enabled": True,
            "create_organizations_limit": 134365,
            "created_at": "2023-03-15T07:15:20.902Z",
        }
    )
    assert res is not None
    return res


def test_test_user(create_test_user: User):
    """Check the test user was either created or found correctly."""
    user = create_test_user
    assert user.email_addresses is not None
    assert user.email_addresses[0].email_address == TEST_EMAIL


def test_render(page: Page):
    """Check that the demo renders correctly.

    I.e. Check components are visible.
    """
    page.pause()
    expect(page.get_by_role("heading", name="reflex-clerk-api demo")).to_contain_text(
        "reflex-clerk-api demo"
    )
    expect(page.get_by_role("heading", name="Getting Started")).to_contain_text(
        "Getting Started"
    )

    expect(page.get_by_test_id("clerkstate_variables_and_methods")).to_be_visible()
    expect(page.get_by_test_id("clerk_loaded_and_signed_in_out_areas")).to_be_visible()
    expect(page.get_by_test_id("better_on_load_handling")).to_be_visible()
    expect(page.get_by_test_id("on_auth_change_callbacks")).to_be_visible()
    expect(page.get_by_test_id("clerkuser_info")).to_be_visible()
    expect(page.get_by_test_id("sign-in_and_sign-up_pages")).to_be_visible()
    expect(page.get_by_test_id("user_profile_management")).to_be_visible()


def test_sign_up(page: Page):
    """Check sign-up button takes you to a sign-up form.

    Note: Can't actually test signing up in headless mode because of bot detection.
    """
    page.pause()
    page.get_by_role("button", name="Sign up").click()
    expect(page.get_by_role("heading")).to_contain_text("Create your account")


class SetupError(Exception):
    """Error raised when the test setup is incorrect."""


@pytest.mark.usefixtures("create_test_user")
def test_sign_in(page: Page):
    """Check sign-in button takes you to a sign-in form.

    Note: Can't actually test signing in in headless mode because of bot detection.
    """

    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("heading")).to_contain_text("Sign in to")
    page.get_by_role("textbox", name="Email address").click()
    page.get_by_role("textbox", name="Email address").fill(TEST_EMAIL)
    page.pause()
    page.get_by_role("button", name="Continue", exact=True).click()
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(TEST_PASSWORD)
    page.get_by_role("button", name="Continue", exact=True).click()
    expect(page.get_by_test_id("sign_out")).not_to_be_visible()

    page.pause()


@pytest.fixture
def sign_in(page: Page, create_test_user: User) -> User:
    """Sign in the test user."""
    assert create_test_user.email_addresses is not None
    assert create_test_user.email_addresses[0].email_address == TEST_EMAIL
    page.get_by_role("button", name="Sign in").click()
    page.get_by_role("textbox", name="Email address").click()
    page.get_by_role("textbox", name="Email address").fill(TEST_EMAIL)
    page.get_by_role("button", name="Continue", exact=True).click()
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(TEST_PASSWORD)
    page.get_by_role("button", name="Continue", exact=True).click()
    # Wait until we are back at the demo page signed in
    expect(page.get_by_test_id("sign_out")).not_to_be_visible()

    return create_test_user


@pytest.mark.usefixtures("sign_in")
def test_sign_out(page: Page):
    """Check sign-out button signs out the user."""
    page.get_by_role("button", name="Sign out").click()
    expect(page.get_by_test_id("sign_in")).to_be_visible()
    expect(page.get_by_test_id("sign_up")).to_be_visible()
    expect(page.get_by_test_id("sign_out")).not_to_be_visible()


def test_signed_in_state(page: Page, sign_in: User):
    """Check a signed-in user sees expected state of app."""
    assert sign_in.id is not None
    page.get_by_test_id("clerkstate_variables_and_methods").hover()
    page.pause()
    expect(page.get_by_test_id("is_hydrated")).to_contain_text("true")
    expect(page.get_by_test_id("auth_checked")).to_contain_text("true")
    expect(page.get_by_test_id("is_signed_in")).to_contain_text("true")
    expect(page.get_by_test_id("user_id")).to_contain_text(sign_in.id)

    page.get_by_test_id("clerk_loaded_and_signed_in_out_areas").hover()
    page.pause()
    expect(page.get_by_test_id("you_are_signed_in")).to_contain_text(
        "You are signed in."
    )
    expect(page.get_by_test_id("you_are_signed_in")).to_be_visible()
    expect(page.get_by_test_id("you_are_signed_out")).not_to_be_visible()

    page.get_by_test_id("better_on_load_handling").hover()
    page.pause()
    expect(page.get_by_test_id("info_from_load")).to_contain_text(
        "clerkstate.auth_checked: True"
    )
