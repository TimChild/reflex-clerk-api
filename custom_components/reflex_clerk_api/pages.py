"""
This provides some example code for adding dedicated sign-in and sign-up pages to your app.
"""

import os

import reflex as rx

import reflex_clerk_api as clerk


def add_sign_in_page(
    app: rx.App, publishable_key: str | None = None, route: str = "/sign-in"
) -> None:
    """
    Adds a sign-in page that is customizable via the Clerk dashboard.
    """
    assert route.startswith("/")
    publishable_key = publishable_key or os.environ["CLERK_PUBLISHABLE_KEY"]

    sign_in_page = clerk.clerk_provider(
        rx.center(
            rx.vstack(
                clerk.sign_in(path=route),
                align="center",
                spacing="7",
            ),
            height="100vh",
        ),
        publishable_key=publishable_key,
    )
    app.add_page(sign_in_page, route=route + "/[[...splat]]")


def add_sign_up_page(
    app: rx.App, publishable_key: str | None = None, route: str = "/sign-up"
) -> None:
    """
    Adds a sign-up page that is customizable via the Clerk dashboard.
    """
    assert route.startswith("/")
    publishable_key = publishable_key or os.environ["CLERK_PUBLISHABLE_KEY"]

    sign_up_page = clerk.clerk_provider(
        rx.center(
            rx.vstack(
                clerk.sign_up(path=route),
                align="center",
                spacing="7",
            ),
            height="100vh",
        ),
        publishable_key=publishable_key,
    )
    app.add_page(sign_up_page, route=route + "/[[...splat]]")
