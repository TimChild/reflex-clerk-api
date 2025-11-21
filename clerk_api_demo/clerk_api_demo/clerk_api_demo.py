"""Welcome to Reflex! This file showcases the custom component in a basic app."""

import logging
import os
from textwrap import dedent

import reflex as rx
import reflex_clerk_api as clerk
from dotenv import load_dotenv
from reflex.event import EventType
from rxconfig import config

# Set up debug logging with a console handler
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
# Just a very quick check to see which loggers are actually active in the console
logging.debug("Logging DEBUG")
logging.info("Logging INFO")
logging.warning("Logging WARNING")


load_dotenv()

filename = f"{config.app_name}/{config.app_name}.py"


class State(rx.State):
    """The app state."""

    # Store information that is populated during an on_load event within clerk.on_load wrapper.
    info_from_load: str = "Not loaded yet."
    # Same as above but without the clerk.on_load wrapper.
    info_from_load_without_wrapper: str = "Not loaded yet."
    # Store information whenever the user logs in or out.
    last_auth_change: str = "No changes yet."

    @rx.event
    async def do_something_on_load(self) -> EventType:
        """Example of a handler that should run on_load, but *after* the ClerkState is updated.

        E.g., The handler needs to know whether the user is logged in or not.
        """
        clerk_state = await self.get_state(clerk.ClerkState)
        self.info_from_load = f"""\
        State.is_hydrated: {self.is_hydrated}
        clerkstate.auth_checked: {clerk_state.auth_checked}
        ClerkState.is_signed_in: {clerk_state.is_signed_in}
        """
        return rx.toast.info("On load event has finished")

    @rx.event
    async def do_something_on_load_without_wrapper(self) -> None:
        clerk_state = await self.get_state(clerk.ClerkState)
        self.info_from_load_without_wrapper = f"""\
        State.is_hydrated: {self.is_hydrated}
        clerkstate.auth_checked: {clerk_state.auth_checked}
        ClerkState.is_signed_in: {clerk_state.is_signed_in}
        """

    @rx.event
    async def do_something_on_log_in_or_out(self) -> EventType | None:
        """Demo handler that should run on user login or logout.

        To make this run it is registered via
        `clerk.register_on_auth_change_handler(State.do_something_on_log_in_or_out)`
        """
        clerk_state = await self.get_state(clerk.ClerkState)
        old_val = self.last_auth_change
        first_load = old_val == "No changes yet."
        new_val = "User signed in" if clerk_state.is_signed_in else "User signed out"
        self.last_auth_change = new_val
        if not first_load and not old_val == new_val:
            return rx.toast.info(new_val, position="top-center")
        return None


def demo_page_header_and_description() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("reflex-clerk-api demo", size="9"),
            rx.text(clerk.__version__),
            align="baseline",
        ),
        rx.heading(
            "Custom",
            rx.link(rx.code("reflex"), href="https://reflex.dev"),
            "components that wrap Clerk react components (",
            rx.link(
                rx.code("@clerk/clerk-react"),
                href="https://www.npmjs.com/package/@clerk/clerk-react",
            ),
            ") and interact with the Clerk backend API.",
            size="4",
        ),
        rx.heading(
            "See the ",
            rx.link(
                "overview of Clerk components",
                href="https://clerk.com/docs/components/overview",
            ),
            " for more info on the wrapped components.",
            size="5",
        ),
        rx.divider(),
        rx.text(
            "Note: This is intended to be roughly a drop-in replacement of the ",
            rx.code("kroo/reflex-clerk"),
            " package that is no longer maintained.",
        ),
        rx.heading(
            "In addition to wrapping the basic components (and in comparison to Kroo's implementation), this additionally:",
            size="5",
        ),
        rx.unordered_list(
            rx.list_item(
                "uses Clerk's maintained python backend api (",
                rx.link(
                    "clerk-backend-api",
                    href="https://pypi.org/project/clerk-backend-api/",
                ),
                ")",
            ),
            rx.list_item(
                "is fully asynchronous, using ",
                rx.code("async/await"),
                " for all requests to the Clerk backend",
            ),
            rx.list_item("supports reflex 0.8.x"),
            rx.list_item(
                "adds a helper for handling ",
                rx.code("on_load"),
                " events that require knowledge of user authentication status. (i.e. ensuring the ClerkState is updated first)",
            ),
            rx.list_item(
                "adds a way to register event handlers to be called on authentication changes (login/logout)"
            ),
            rx.list_item("Checks JWT tokens are actually valid (not expired etc.)"),
        ),
        rx.accordion.root(
            rx.accordion.item(
                header="Migration notes",
                content=migration_notes(),
            ),
            variant="soft",
            collapsible=True,
        ),
    )


copy_button = rx.button(
    rx.icon("copy"),
    variant="soft",
    position="absolute",
    top="8px",
    right="0",
)


def getting_started() -> rx.Component:
    return rx.vstack(
        rx.heading("Getting Started", size="6"),
        rx.text("Install with pip: "),
        rx.code_block(
            "pip install reflex-clerk-api",
            language="bash",
            can_copy=True,
            copy_button=copy_button,
        ),
        rx.text("Or with a package manager (uv/poetry):"),
        rx.code_block(
            "uv add reflex-clerk-api",
            language="bash",
            can_copy=True,
            copy_button=copy_button,
        ),
        rx.heading(
            "Import the package",
            size="5",
        ),
        rx.code_block(
            "import reflex_clerk_api as clerk",
            language="python",
            can_copy=True,
            copy_button=copy_button,
        ),
        rx.accordion.root(
            rx.accordion.item(
                header="Minimal example",
                content=rx.code_block(
                    dedent("""\
                import reflex_clerk_api as clerk

                def index() -> rx.Component:
                    return clerk.clerk_provider(
                        clerk.clerk_loaded(
                            clerk.signed_in(
                                clerk.sign_on(
                                    rx.button("Sign out"),
                                ),
                            ),
                            clerk.signed_out(
                                rx.button("Sign in"),
                            ),
                        ),
                        publishable_key=os.environ["CLERK_PUBLISHABLE_KEY"],
                        secret_key=os.environ["CLERK_SECRET_KEY"],
                        register_user_state=True,
                    )
                """),
                    language="python",
                ),
            ),
            collapsible=True,
            variant="soft",
        ),
    )


def migration_notes() -> rx.Component:
    return rx.vstack(
        rx.unordered_list(
            rx.list_item(
                "update your import to be from `reflex_clerk_api` instead of `reflex_clerk`"
            ),
            rx.list_item(
                rx.markdown(
                    "use `clerk.add_sign_in_page(...)` and `clerk.add_sign_up_page(...)` instead of `clerk.install_pages(...)`"
                )
            ),
            rx.list_item(
                rx.markdown(
                    "wrap `on_load` events with `clerk.on_load(<on_load_events>)` to ensure the ClerkState is updated before other on_load events (i.e. is_signed_in will be accurate)"
                )
            ),
            rx.list_item(
                rx.markdown(
                    "use `await clerk.get_user(self)` inside event handlers instead of `clerk_state.user` to explicitly retrieve user information when desired"
                )
            ),
            rx.list_item(
                "Note that you can use the `clerk_backend_api` directly if desired (it is a dependency of this plugin anyway)"
            ),
        ),
    )


def data_list_item(label: str, value: rx.Component | str) -> rx.Component:
    return rx.data_list.item(
        rx.data_list.label(label),
        rx.data_list.value(value),
    )


close_icon = rx.icon(
    "x",
    position="absolute",
    top="8px",
    right="8px",
    background_color=rx.color("tomato", 6),
    _hover=dict(background_color=rx.color("tomato", 7)),
    padding="2px",
    border_radius="5px",
    z_index="5",
)


def demo_card(
    heading: str, description: str | rx.Component, demo: rx.Component
) -> rx.Component:
    card = rx.card(
        rx.vstack(
            rx.heading(heading, size="5"),
            rx.text(description) if isinstance(description, str) else description,
        ),
        max_width="30em",
        _hover=dict(background=rx.color("gray", 4)),
        height="100%",
    )

    content_popover_desktop = rx.hover_card.root(
        rx.hover_card.trigger(
            card,
            data_testid=heading.lower().replace(" ", "_").replace("/", "_"),
        ),
        rx.hover_card.content(
            demo,
            avoid_collisions=True,
        ),
    )
    content_popover_mobile = rx.popover.root(
        rx.popover.trigger(
            card,
        ),
        rx.popover.content(
            rx.popover.close(
                close_icon,
            ),
            demo,
        ),
    )
    return rx.fragment(
        rx.desktop_only(content_popover_desktop),
        rx.mobile_and_tablet(content_popover_mobile),
    )


def current_clerk_state_values() -> rx.Component:
    demo = rx.vstack(
        rx.text("State variables:"),
        rx.data_list.root(
            data_list_item(
                "State.is_hydrated",
                rx.text(State.is_hydrated, data_testid="is_hydrated"),
            ),
            data_list_item(
                "ClerkState.auth_checked",
                rx.text(clerk.ClerkState.auth_checked, data_testid="auth_checked"),
            ),
            data_list_item(
                "ClerkState.is_logged_in",
                rx.text(clerk.ClerkState.is_signed_in, data_testid="is_signed_in"),
            ),
            data_list_item(
                "ClerkState.user_id",
                rx.text(clerk.ClerkState.user_id, data_testid="user_id"),
            ),
        ),
        rx.divider(),
        rx.text("State methods:"),
        rx.unordered_list(
            rx.list_item(
                rx.code("ClerkState.register_dependent_handler(handler)"),
                " -- Classmethod to register a handler to be called after the ClerkState is updated",
            ),
            rx.list_item(
                rx.code("ClerkState.set_auth_wait_timeout_seconds(seconds)"),
                " -- Set the timeout for waiting for the auth check to complete",
            ),
            rx.list_item(
                rx.code("ClerkState.set_claims_options(claims_options)"),
                " -- Set JWT claims options",
            ),
            rx.list_item(
                rx.code("clerk_state.client"),
                " -- Property to access the clerk_backend_api client",
            ),
        ),
    )
    return demo_card(
        "ClerkState variables and methods",
        "State variables and methods available on the `ClerkState` object.",
        demo,
    )


def on_load_demo() -> rx.Component:
    state_using_on_load_wrapper = rx.card(
        rx.vstack(
            rx.text(
                "Info from `on_load` event ",
                rx.text.strong("inside"),
                " of `clerk.on_load` wrapper:",
            ),
            rx.divider(),
            rx.text(
                State.info_from_load,
                data_testid="info_from_load",
            ),
        )
    )
    state_not_using_on_load_wrapper = rx.card(
        rx.vstack(
            rx.text(
                "Info from `on_load` event ",
                rx.text.strong("outside"),
                " of `clerk.on_load` wrapper:",
            ),
            rx.divider(),
            rx.text(
                State.info_from_load_without_wrapper,
                data_testid="info_from_load_without_wrapper",
            ),
        )
    )
    demo = rx.vstack(
        rx.markdown(
            dedent("""\
            Wrapping the `on_load` events is necessary because the ClerkState authentication is triggered from a frontend event that can't be guaranteed to run before the other `on_load` events.

            Sometimes the event outside the `clerk.on_load` wrapper will run before the ClerkState is updated (sometimes not).
            """)
        ),
        rx.grid(
            state_using_on_load_wrapper,
            state_not_using_on_load_wrapper,
            spacing="3",
            columns="2",
            width="100%",
        ),
    )
    return demo_card(
        "Better on_load handling",
        rx.text(
            "Wrap ",
            rx.code("on_load"),
            " events with ",
            rx.code(
                "clerk.on_load(...)",
                " to ensure the ClerkState is updated before events run.",
            ),
        ),
        demo,
    )


def on_auth_change_demo() -> rx.Component:
    demo = rx.vstack(
        rx.text("By registering an event handler method like this:"),
        rx.code_block(
            "clerk.register_on_auth_change_handler(State.do_something_on_log_in_or_out)",
            language="python",
            wrap_long_lines=True,
            width="100%",
        ),
        rx.text(
            "The event handler will be called any time the authentication state of the user changes. In this demo, you'll see a toast top-center when you log in or out as well as the state variable change below."
        ),
        rx.text(f"State.last_auth_change={State.last_auth_change}"),
        width="100%",
    )
    return demo_card(
        "On auth change callbacks",
        "You can register a method to be called when the user logs in or out.",
        demo,
    )


def clerk_loaded_demo() -> rx.Component:
    signed_in_area = rx.card(
        rx.vstack(
            rx.text("You'll only see content below if you are signed in"),
            rx.divider(),
            clerk.signed_in(
                rx.text("You are signed in.", data_testid="you_are_signed_in"),
                clerk.sign_out_button(rx.button("Sign out", width="100%")),
            ),
        )
    )
    signed_out_area = rx.card(
        rx.vstack(
            rx.text("You'll only see content below if you are signed out"),
            rx.divider(),
            clerk.signed_out(
                rx.text("You are signed out.", data_testid="you_are_signed_out"),
                clerk.sign_in_button(rx.button("Sign in", width="100%")),
            ),
        )
    )

    demo = rx.fragment(
        clerk.clerk_loading(
            rx.text("Clerk is loading..."),
            rx.spinner(size="3"),
        ),
        clerk.clerk_loaded(
            rx.vstack(
                rx.text("Clerk is loaded!"),
                rx.grid(
                    signed_in_area,
                    signed_out_area,
                    columns="2",
                    spacing="3",
                ),
                align="center",
            ),
        ),
    )
    return demo_card(
        "Clerk loaded and signed in/out areas",
        rx.markdown(
            "Demo of `clerk_loaded`, `clerk_loading`, and `signed_in`, `signed_out` components."
        ),
        demo,
    )


def links_to_demo_pages() -> rx.Component:
    demo = rx.vstack(
        rx.markdown(
            dedent("""\
            To use the built-in pages, just do:

            ```python
            clerk.add_sign_in_page(app)
            clerk.add_sign_up_page(app)
            ```

            But, you can also create your own with more customization.""")
        ),
        clerk.signed_out(
            rx.grid(
                rx.link(rx.button("Go to sign up page", width="100%"), href="/sign-up"),
                rx.link(rx.button("Go to sign in page", width="100%"), href="/sign-in"),
                width="100%",
                columns="2",
                spacing="3",
            )
        ),
        clerk.signed_in(
            rx.text("Sign out to see links to default sign-in and sign-up pages."),
            clerk.sign_out_button(rx.button("Sign out", width="100%")),
        ),
    )
    return demo_card(
        "Sign-in and sign-up pages",
        "Some basic sign-in and sign-up pages are implemented for easy use. You can also create your own.",
        demo,
    )


def user_info_demo() -> rx.Component:
    demo = rx.vstack(
        rx.markdown(
            dedent("""\
            To enable this behaviour, when creating the `clerk_provider`, set `register_user_state=True`.
            ```clerk.clerk_provider(..., register_user_state=True)```

            This is not enabled by default to avoid unnecessary api calls to the Clerk backend. Also note that only a subset of user information is retrieved by the ClerkUser state.

            Full user information can be retrieved easily within event handler methods via `await clerk.get_user(self)` that will return a full `clerk_backend_api.models.User` model.

            Test credentials will not have a name or image by default.
            """)
        ),
        clerk.signed_in(
            rx.hstack(
                rx.card(
                    rx.data_list.root(
                        data_list_item("first name", clerk.ClerkUser.first_name),
                        data_list_item("last name", clerk.ClerkUser.last_name),
                        data_list_item("username", clerk.ClerkUser.username),
                        data_list_item("email", clerk.ClerkUser.email_address),
                        data_list_item("has image", rx.text(clerk.ClerkUser.has_image)),
                    ),
                    # border=f"1px solid {rx.color('gray', 6)}",
                    # padding="2em",
                ),
                rx.avatar(src=clerk.ClerkUser.image_url, fallback="No image", size="9"),
                width="100%",
                justify="center",
                spacing="5",
            )
        ),
        clerk.signed_out(rx.text("Sign in to see user information.")),
    )

    return demo_card(
        "ClerkUser info",
        "To conveniently use basic information within the frontend, you can use the `clerk.ClerkUser` state.",
        demo,
    )


def user_profile_demo() -> rx.Component:
    demo = rx.vstack(
        rx.text(
            "Either include the ",
            rx.code("clerk.user_profile"),
            " component that renders a UI within your page.",
        ),
        rx.popover.root(
            rx.popover.trigger(
                rx.button("Show in popover"),
            ),
            rx.popover.content(
                rx.popover.close(
                    close_icon,
                ),
                clerk.user_profile(),
                max_width="1000px",
                avoid_collisions=True,
            ),
        ),
        rx.text(
            "Or you can redirect the user by rendering ",
            rx.code("clerk.redirect_to_user_profile()"),
            ". However, this will redirect as soon as it is rendered, so it's a bit tricky to use.",
        ),
        width="100%",
    )

    return demo_card(
        "User profile management",
        "Users can manage their profile via the Clerk interface.",
        demo,
    )


def demo_header() -> rx.Component:
    demo_intro = rx.vstack(
        rx.text(
            "The demos below are using a development Clerk API key, so you can try out everything with fake credentials."
        ),
        rx.text("To simply log in, you can use the email/password combination."),
    )
    clerk_user_info = rx.box(
        clerk.clerk_loaded(
            rx.cond(
                clerk.ClerkState.is_signed_in,
                rx.card(
                    rx.hstack(
                        rx.data_list.root(
                            data_list_item(
                                "Clerk user_id", rx.text(clerk.ClerkState.user_id)
                            ),
                            data_list_item("User button", clerk.user_button()),
                        ),
                    ),
                ),
                rx.text("Sign in to see user info."),
            )
        ),
        clerk.clerk_loading(rx.spinner(size="3")),
    )

    test_user_and_pass = rx.card(
        rx.vstack(
            rx.data_list.root(
                data_list_item("username", rx.code("test+clerk_test@gmail.com")),
                data_list_item("password", rx.code("test-clerk-password")),
            ),
            rx.hstack(
                clerk.signed_in(
                    clerk.sign_out_button(rx.button("Sign out", data_testid="sign_out"))
                ),
                clerk.signed_out(
                    rx.hstack(
                        clerk.sign_in_button(
                            rx.button("Sign in", data_testid="sign_in")
                        ),
                        clerk.sign_up_button(
                            rx.button("Sign up", data_testid="sign_up")
                        ),
                    ),
                ),
            ),
        ),
    )
    using_demo_instructions = rx.box(
        rx.text(
            "Or if you want test signing up, you can use any email with ",
            rx.code("+clerk_test"),
            " appended to it. E.g., ",
            rx.code("any_email+clerk_test@anydomain.com"),
            ".",
        ),
        rx.text(
            "Use any password you like, and the verification code will be ",
            rx.code("424242"),
            ".",
        ),
        rx.text(
            "More info on test credentials can be found ",
            rx.link(
                "in the Clerk documentation.",
                href="https://clerk.com/docs/testing/test-emails-and-phones",
            ),
        ),
    )

    return rx.vstack(
        rx.heading("Demos", size="6"),
        rx.grid(
            demo_intro,
            clerk_user_info,
            test_user_and_pass,
            using_demo_instructions,
            columns=rx.breakpoints(initial="1", sm="2"),
            spacing="4",
        ),
    )


def index() -> rx.Component:
    clerk.register_on_auth_change_handler(State.do_something_on_log_in_or_out)

    # Note: Using `clerk.wrap_app(...)` instead of `clerk.clerk_provider(...)` here.
    return rx.box(
        rx.vstack(
            rx.flex(
                demo_page_header_and_description(),
                getting_started(),
                spacing="7",
                direction=rx.breakpoints(initial="column", sm="row"),
            ),
            # rx.button("Dev reset", on_click=clerk.ClerkState.force_reset),
            rx.divider(),
            demo_header(),
            rx.grid(
                current_clerk_state_values(),
                clerk_loaded_demo(),
                on_load_demo(),
                on_auth_change_demo(),
                user_info_demo(),
                links_to_demo_pages(),
                user_profile_demo(),
                columns=rx.breakpoints(initial="1", sm="2", md="3", xl="4"),
                spacing="4",
                align="stretch",
            ),
            align="center",
            spacing="7",
        ),
        height="100vh",
        max_width="100%",
        overflow_y="auto",
        padding="2em",
    )


# Add state and page to the app.
app = rx.App()

# This wraps the entire app (all pages) with the ClerkProvider.
clerk.wrap_app(
    app,
    publishable_key=os.environ["CLERK_PUBLISHABLE_KEY"],
    secret_key=os.environ.get("CLERK_SECRET_KEY"),
    register_user_state=True,
    # NOTE: Colors customizable via the `Appearance` object. (baseTheme is not yet implemented)
    # appearance=Appearance(
    #     variables=Variables(
    #         color_primary="#111A27",
    #         color_background="#C2F3FF",
    #     ),
    # ),
)

# NOTE: Use the `clerk.on_load` to ensure that the ClerkState is updated *before* any other on_load events are run.
#  The `ClerkState` is updated by an event sent from the frontend that is not guaranteed to run before the reflex on_load events.
app.add_page(
    index,
    on_load=[
        *clerk.on_load([State.do_something_on_load]),
        State.do_something_on_load_without_wrapper,
    ],
)
clerk.add_sign_in_page(app)
clerk.add_sign_up_page(app)
