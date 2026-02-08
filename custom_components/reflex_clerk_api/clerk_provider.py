import asyncio
import logging
import os
import time
import uuid
from collections.abc import Callable
from typing import Any, ClassVar, Self, TypeVar, cast

import authlib.jose.errors as jose_errors
import clerk_backend_api
import reflex as rx
from authlib.jose import JWTClaims, jwt
from reflex.event import EventCallback, EventType, IndividualEventType
from reflex.utils.exceptions import ImmutableStateError

from reflex_clerk_api.base import ClerkBase

from .models import Appearance


class ReflexClerkApiError(Exception):
    pass


class MissingSecretKeyError(ReflexClerkApiError):
    pass


class MissingUserError(ReflexClerkApiError):
    pass


class ClerkState(rx.State):
    is_signed_in: bool = False
    """Whether the user is logged in."""

    auth_checked: bool = False
    """Whether the auth state of the user has been checked yet.
    I.e., has Clerk sent a response to the frontend yet."""

    claims: JWTClaims | None = None
    """The JWT claims of the user, if they are logged in."""
    user_id: str | None = None
    """The clerk user ID of the user, if they are logged in."""

    # NOTE: ClassVar tells reflex it doesn't need to include these in the persisted state per instance.
    _auth_wait_timeout_seconds: ClassVar[float] = 1.0
    _secret_key: ClassVar[str | None] = None
    """The Clerk secret_key set during clerk_provider creation."""
    _on_load_events: ClassVar[dict[uuid.UUID, EventType[()]]] = {}
    _dependent_handlers: ClassVar[dict[int, EventCallback]] = {}
    _client: ClassVar[clerk_backend_api.Clerk | None] = None
    _jwk_keys: ClassVar[dict[str, Any] | None] = None
    "JWK keys from Clerk for decoding any users JWT tokens (only required once per instance)."
    _last_jwk_reset: ClassVar[float] = 0.0
    _claims_options: ClassVar[dict[str, Any]] = {
        # "iss": {"value": "https://<your-iss>.clerk.accounts.dev"},
        "exp": {"essential": True},
        "nbf": {"essential": True},
        # "azp": {"essential": False, "values": ["http://localhost:3000", "https://example.com"]},
    }

    @classmethod
    def register_dependent_handler(cls, handler: EventCallback) -> None:
        """Register a handler to be called any time this state updates.

        I.e. Any events that should be triggered on login/logout.
        """
        assert isinstance(handler, rx.EventHandler)
        hash_id = hash((handler.state_full_name, handler.fn))
        logging.debug(f"Dependent hash_id: {hash_id}")
        cls._dependent_handlers[hash_id] = handler

    @classmethod
    def set_auth_wait_timeout_seconds(cls, seconds: float) -> None:
        """Sets the max time to wait for initial auth check before running other on_load events.

        Note: on_load events will still be run after a timed out auth check.
        Check ClerkState.auth_checked to see if auth check is complete.
        """
        cls._auth_wait_timeout_seconds = seconds

    @classmethod
    def set_claims_options(cls, claims_options: dict[str, Any]) -> None:
        """Set the claims options for the JWT claims validation."""
        cls._claims_options = claims_options

    @property
    def client(self) -> clerk_backend_api.Clerk:
        if self._client is None:
            self._set_client()
        assert self._client is not None
        return self._client

    @rx.event(background=True)
    async def set_clerk_session(self, token: str) -> EventType:
        """Manually obtain user session information via the Clerk JWT.

        This event is triggered by the frontend via the ClerkSessionSynchronizer/ClerkProvider component.

        Note: Only the parts that modify the per-instance state need to be in an `async with self` block.
        """
        logging.debug("Setting Clerk session")
        jwks = await self._get_jwk_keys()
        try:
            decoded: JWTClaims = jwt.decode(
                token, {"keys": jwks}, claims_options=self._claims_options
            )
        except jose_errors.DecodeError as e:
            # E.g. DecodeError -- Something went wrong just getting the JWT
            # On next attempt, new JWKs will be fetched
            async with self:
                self.auth_error = e
            self._request_jwk_reset()
            logging.warning(f"JWT decode error: {e}")
            return ClerkState.clear_clerk_session
        try:
            # Validate the token according to the claim options (e.g. iss, exp, nbf, azp.)
            decoded.validate()
        except (jose_errors.InvalidClaimError, jose_errors.MissingClaimError) as e:
            logging.warning(f"JWT token is invalid: {e}")
            return ClerkState.clear_clerk_session

        async with self:
            self.is_signed_in = True
            self.claims = decoded
            self.user_id = str(decoded.get("sub"))
            self.auth_checked = True
        return list(self._dependent_handlers.values())

    @rx.event
    def clear_clerk_session(self) -> EventType:
        """Clear the Clerk session information.

        This event is triggered by the frontend via the ClerkSessionSynchronizer/ClerkProvider component.
        """
        logging.debug("Clearing Clerk session")
        self.reset()
        self.auth_checked = True
        return list(self._dependent_handlers.values())

    @rx.event(background=True)
    async def wait_for_auth_check(self, uid: uuid.UUID | str) -> EventType:
        """Wait for the Clerk authentication to complete (event sent from frontend).

        Can't just use a blocking wait_for_auth_check because we are really waiting for the frontend event trigger to run, so we need to not block that while we wait.

        This can then return on_load events once auth_checked is True.
        """
        uid = uuid.UUID(uid) if isinstance(uid, str) else uid
        logging.debug(f"Waiting for auth check: {uid} ({type(uid)})")

        on_loads = self._on_load_events.get(uid, None)
        if on_loads is None:
            logging.warning("Waited for auth, but no on_load events registered.")
            on_loads = []

        start_time = time.time()
        while time.time() - start_time < self._auth_wait_timeout_seconds:
            if self.auth_checked:
                logging.debug("Auth check complete")
                return on_loads
            logging.debug("...waiting for auth...")
            # TODO: Ideally, wait on some event instead of sleeping
            await asyncio.sleep(0.05)
        logging.warning("Auth check timed out")
        return on_loads

    @classmethod
    def _set_secret_key(cls, secret_key: str) -> None:
        if not secret_key:
            raise MissingSecretKeyError("secret_key must be set (and not empty)")
        cls._secret_key = secret_key

    @classmethod
    def _set_on_load_events(cls, uid: uuid.UUID, on_load_events: EventType[()]) -> None:
        logging.debug(f"Registing on_load events: {uid}")
        cls._on_load_events[uid] = on_load_events

    @classmethod
    def _set_client(cls) -> None:
        if cls._secret_key:
            secret_key = cls._secret_key
        else:
            if "CLERK_SECRET_KEY" not in os.environ:
                raise MissingSecretKeyError(
                    "CLERK_SECRET_KEY either needs to be passed into clerk_provider(...) or set as an environment variable."
                )
            secret_key = os.environ["CLERK_SECRET_KEY"]
        client = clerk_backend_api.Clerk(bearer_auth=secret_key)
        cls._client = client

    @classmethod
    def _set_jwk_keys(cls, keys: dict[str, Any] | None) -> None:
        cls._jwk_keys = keys

    @classmethod
    def _request_jwk_reset(cls) -> None:
        """Reset the JWK keys so they will be re-fetched on next attempt.

        Only do so if it has been a while since last reset (to prevent malicious tokens from forcing
        constant re-fetching).
        """
        now = time.time()
        if now - cls._last_jwk_reset < 10:
            logging.warning("JWK reset requested too soon")
            return
        cls._last_jwk_reset = time.time()
        cls._jwk_keys = None

    async def _get_jwk_keys(self) -> dict[str, Any]:
        """Get the JWK keys from the Clerk API.

        Note: Cannot be a property because it requires async call to populate.
        Only needs to be done once (will be refreshed on errors).
        """
        if self._jwk_keys:
            return self._jwk_keys
        jwks = await self.client.jwks.get_jwks_async()
        assert jwks is not None
        assert jwks.keys is not None
        keys = jwks.model_dump()["keys"]
        self._set_jwk_keys(keys)
        return keys

    # @rx.event
    # def force_reset(self) -> None:
    #     """Force a reset of the Clerk state.
    #
    #     E.g. During development testing.
    #     """
    #     self.reset()
    #     self._set_jwk_keys(None)
    #     return rx.toast.success("Forced reset complete.")


class NotRegisteredError(ReflexClerkApiError):
    pass


class ClerkUser(rx.State):
    """Convenience class for using Clerk User information.

    This only contains a subset of the information available. Create your own state if you need more.

    Note: For this to be updated on login/logout events, it must be registered on the ClerkState.
    """

    first_name: str = ""
    last_name: str = ""
    username: str = ""
    email_address: str = ""
    phone_number: str = ""
    """The user's primary phone number in E.164 format (e.g., +12025551234)."""
    phone_number_id: str = ""
    """The Clerk phone_number_id for the primary phone number, used for updates."""
    has_image: bool = False
    image_url: str = ""

    # Set to True when the state is registered on the ClerkState to avoid registering it multiple times.
    _is_registered: ClassVar[bool] = False

    @rx.event
    async def load_user(self) -> None:
        try:
            user: clerk_backend_api.models.User = await get_user(self)
        except MissingUserError:
            logging.debug("Clearing user state")
            self.reset()
            return

        logging.debug("Updating user state")
        self.first_name = (
            user.first_name
            if user.first_name and user.first_name != clerk_backend_api.UNSET
            else ""
        )
        self.last_name = (
            user.last_name
            if user.last_name and user.last_name != clerk_backend_api.UNSET
            else ""
        )
        self.username = (
            user.username
            if user.username and user.username != clerk_backend_api.UNSET
            else ""
        )
        self.email_address = (
            user.email_addresses[0].email_address if user.email_addresses else ""
        )
        # Load primary phone number and its ID, falling back to the first if needed
        if user.phone_numbers:
            primary_phone = None
            primary_id = getattr(user, "primary_phone_number_id", None)
            if primary_id is not None:
                for pn in user.phone_numbers:
                    if getattr(pn, "id", None) == primary_id:
                        primary_phone = pn
                        break
            if primary_phone is None:
                primary_phone = user.phone_numbers[0]
            self.phone_number = getattr(primary_phone, "phone_number", "") or ""
            self.phone_number_id = getattr(primary_phone, "id", "") or ""
        else:
            self.phone_number = ""
            self.phone_number_id = ""
        self.has_image = True if user.has_image is True else False
        self.image_url = user.image_url or ""

    @rx.event
    async def update_phone_number(
        self, phone_number: str, verified: bool = False
    ) -> None:
        """Update the user's phone number in Clerk.

        This will create a new phone number and set it as primary, then delete the old one
        if it exists. Phone numbers must be in E.164 format (e.g., +12025551234).

        Args:
            phone_number: The new phone number in E.164 format.
            verified: Whether to mark the phone number as verified. Defaults to False.
                Set to True only if verification was handled externally (e.g., OTP flow).
        """
        # Skip if phone number hasn't changed
        if phone_number == self.phone_number:
            logging.debug("Phone number unchanged, skipping update")
            return

        old_phone_id = self.phone_number_id if self.phone_number_id else None

        try:
            # Use the helper function to avoid code duplication
            new_phone = await update_user_phone_number(
                self, phone_number, old_phone_id=old_phone_id, verified=verified
            )

            # Update local state
            if new_phone:
                self.phone_number = new_phone.phone_number or phone_number
                self.phone_number_id = new_phone.id or ""
            else:
                # Phone was deleted (empty phone_number passed)
                self.phone_number = ""
                self.phone_number_id = ""

        except clerk_backend_api.models.ClerkErrors:
            logging.error("Clerk API error updating phone")
            raise
        except Exception:
            logging.error("Error updating phone number")
            raise


class ClerkSessionSynchronizer(rx.Component):
    """ClerkSessionSynchronizer component.

    This is slightly adapted from Elliot Kroo's reflex-clerk.
    """

    tag = "ClerkSessionSynchronizer"

    def add_imports(
        self,
    ) -> rx.ImportDict:
        addl_imports: rx.ImportDict = {
            "@clerk/clerk-react": ["useAuth"],
            "react": ["useContext", "useEffect"],
            "$/utils/context": ["EventLoopContext"],
            "$/utils/state": ["ReflexEvent"],
        }
        return addl_imports

    def add_custom_code(self) -> list[str]:
        clerk_state_name = ClerkState.get_full_name()

        return [
            """
function ClerkSessionSynchronizer({ children }) {
  const { getToken, isLoaded, isSignedIn } = useAuth()
  const [ addEvents, connectErrors ] = useContext(EventLoopContext)

  useEffect(() => {
      if (isLoaded && !!addEvents) {
        if (isSignedIn) {
          getToken().then(token => {
            addEvents([ReflexEvent("%s.set_clerk_session", {token})])
          })
        } else {
          addEvents([ReflexEvent("%s.clear_clerk_session")])
        }
      }
  }, [isSignedIn])

  return (
      <>{children}</>
  )
}
"""
            % (clerk_state_name, clerk_state_name)
        ]


InitialState = dict[str, Any]
# Should this be EventSpec instead?
JSCallable = Callable


class ClerkProvider(ClerkBase):
    """ClerkProvider component."""

    # The React component tag.
    tag = "ClerkProvider"

    # NOTE: This might be relevant to getting apperance.base_theme to work.
    # lib_dependencies: list[str] = ["@clerk/themes"]
    # def add_imports(self) -> rx.ImportDict:
    #     return {
    #         "@clerk/themes": ["dark", "neobrutalism", "shadesOfPurple"],
    #     }

    # The props of the React component.
    # Note: when Reflex compiles the component to Javascript,
    # `snake_case` property names are automatically formatted as `camelCase`.
    # The prop names may be defined in `camelCase` as well.
    # some_prop: rx.Var[str] = "some default value"
    # some_other_prop: rx.Var[int] = 1

    # Event triggers declaration if any.
    # Below is equivalent to merging `{ "on_change": lambda e: [e] }`
    # onto the default event triggers of parent/base Component.
    # The function defined for the `on_change` trigger maps event for the javascript
    # trigger to what will be passed to the backend event handler function.
    # on_change: rx.EventHandler[lambda e: [e]]

    after_multi_session_single_sign_out_url: str = ""
    """The URL to navigate to after a successful sign-out from multiple sessions."""

    after_sign_out_url: str = ""
    """The full URL or path to navigate to after a successful sign-out."""

    allowed_redirect_origins: list[str | str] = []
    """An optional list of domains to validate user-provided redirect URLs against."""

    allowed_redirect_protocols: list[str] = []
    """An optional list of protocols to validate user-provided redirect URLs against."""

    # NOTE: `apperance.base_theme` does not work yet.
    appearance: Appearance | None = None
    """Optional object to style your components. Will only affect Clerk components."""

    clerk_js_url: str = ""
    """Define the URL that @clerk/clerk-js should be hot-loaded from."""

    clerk_js_variant: str | None = None
    """If your web application only uses control components, set this to 'headless'."""

    clerk_js_version: str = ""
    """Define the npm version for @clerk/clerk-js."""

    # domain: str | JSCallable[[str], bool] = ""
    domain: str = ""
    """Required if your application is a satellite application. Sets the domain."""

    dynamic: bool = False
    """(For Next.js only) Indicates whether Clerk should make dynamic auth data available."""

    # initial_state: InitialState | None = None
    # """Provide an initial state of the Clerk client during server-side rendering."""

    # is_satellite: bool | JSCallable[[str], bool] = False
    is_satellite: bool = False
    """Whether the application is a satellite application."""

    # Not implemented
    # localization: Localization | None = None
    # See https://clerk.com/docs/customization/localization#clerk-localizations for more info.
    # """Optional object to localize your components. Will only affect Clerk components."""

    nonce: str = ""
    """Nonce value passed to the @clerk/clerk-js script tag for CSP implementation."""

    publishable_key: str = ""
    """The Clerk Publishable Key for your instance, found on the API keys page in the Clerk Dashboard."""

    # proxy_url: str | JSCallable[[str], str] = ""
    proxy_url: str = ""
    """The URL of the proxy server to use for Clerk API requests."""

    router_push: JSCallable[[str], None | Any] | None = None
    """A function to push a new route into the history stack for navigation."""

    router_replace: JSCallable[[str], None | Any] | None = None
    """A function to replace the current route in the history stack for navigation."""

    # sdk_metadata: dict[str, str] = {"name": "", "version": "", "environment": ""}
    # """Contains information about the SDK that the host application is using."""

    # select_initial_session: Callable[[Any], None | Any] | None = None
    # """Function to override the default behavior of using the last active session during client initialization."""

    sign_in_fallback_redirect_url: str = "/"
    """The fallback URL to redirect to after the user signs in if there's no redirect_url in the path."""

    sign_up_fallback_redirect_url: str = "/"
    """The fallback URL to redirect to after the user signs up if there's no redirect_url in the path."""

    sign_in_force_redirect_url: str = ""
    """URL to always redirect to after the user signs in."""

    sign_up_force_redirect_url: str = ""
    """URL to always redirect to after the user signs up."""

    sign_in_url: str = ""
    """URL used for any redirects that might happen, pointing to your primary application on the client-side."""

    sign_up_url: str = ""
    """URL used for any redirects that might happen, pointing to your primary application on the client-side."""

    standard_browser: bool = True
    """Indicates whether ClerkJS assumes cookies can be set (browser setup)."""

    support_email: str = ""
    """Optional support email for display in authentication screens."""

    sync_host: str = ""
    """URL of the web application that the Chrome Extension will sync the authentication state from."""

    telemetry: bool | dict[str, bool] | None = None
    """Controls whether Clerk will collect telemetry data."""

    touch_session: bool = True
    """Indicates whether the Clerk Frontend API touch endpoint is called during page focus to keep the last active session alive."""

    waitlist_url: str = ""
    """The full URL or path to the waitlist page."""

    @classmethod
    def create(cls, *children, **props) -> Self:
        return cast(Self, super().create(*children, **props))

    def add_custom_code(self) -> list[str]:
        return []


def on_load(on_load_events: EventType[()] | None) -> list[IndividualEventType[()]]:
    """Use this to wrap any on_load events that should happen after Clerk has checked authentication.

    Args:
        on_load_events: The events to run after authentication is checked.

    Examples:
        app.add_page(..., on_load=clerk.on_load(<events>))
    """
    if on_load_events is None:
        return []
    on_load_list = (
        on_load_events if isinstance(on_load_events, list) else [on_load_events]
    )

    # Add the on_load events to a registry in the ClerkState instead of actually passing them to on_load.
    #  Then, the wait_for_auth_check event will return the on_load events once auth_checked is True.
    #  Can't just use a blocking wait_for_auth_check because we are really waiting for the frontend event trigger to run,
    #  so we need to not block that while we wait.
    uid = uuid.uuid4()
    ClerkState._set_on_load_events(uid, on_load_list)
    return [ClerkState.wait_for_auth_check(uid)]


T = TypeVar("T", bound=rx.State)


async def _get_state_within_handler(
    current_state: rx.State, desired_state: type[T]
) -> T:
    """Get the desired state from within an event handler.

    Note: Need to be in `async with self` block if called from background event.
    """
    try:
        state = await current_state.get_state(desired_state)
    except ImmutableStateError:
        async with current_state:
            state = await current_state.get_state(desired_state)
    return state


async def get_user(current_state: rx.State) -> clerk_backend_api.models.User:
    """Get the User object from Clerk given the currently logged in user.

    Note: Must be used within an event handler in order to get the appropriate clerk_state.

    Args:
        current_state: The `self` state from the current event handler.

    Examples:

    ```python
    class State(rx.State):
        @rx.event
        async def handle_getting_user_email(self) -> EventType:
            user = await clerk.get_user(self)
            return rx.toast.info(f"User: {user.email}")
    ```
    """
    clerk_state = await _get_state_within_handler(current_state, ClerkState)
    user_id = clerk_state.user_id
    if user_id is None:
        raise MissingUserError("No user_id to get user for")
    user = await clerk_state.client.users.get_async(user_id=user_id)
    if user is None:
        raise MissingUserError("No user found")
    return user


async def update_user_phone_number(
    current_state: rx.State,
    phone_number: str,
    old_phone_id: str | None = None,
    verified: bool = False,
) -> clerk_backend_api.models.PhoneNumber | None:
    """Update the user's phone number in Clerk.

    This creates a new phone number and sets it as primary. If old_phone_id is provided,
    the old phone number will be deleted after the new one is created.

    Phone numbers must be in E.164 format (e.g., +12025551234).

    Args:
        current_state: The `self` state from the current event handler.
        phone_number: The new phone number in E.164 format. Empty string to remove phone.
        old_phone_id: Optional ID of the old phone number to delete.
        verified: Whether to mark the phone number as verified. Defaults to False.
            Set to True only if verification was handled externally (e.g., OTP flow).

    Returns:
        The new PhoneNumber object if created, None if deleted.

    Examples:

    ```python
    class State(rx.State):
        @rx.event
        async def update_my_phone(self) -> EventType:
            new_phone = await clerk.update_user_phone_number(self, "+12025551234")
            return rx.toast.success(f"Phone updated: {new_phone.phone_number}")

        @rx.event
        async def update_verified_phone(self) -> EventType:
            # Only use verified=True if you've handled verification externally
            new_phone = await clerk.update_user_phone_number(
                self, "+12025551234", verified=True
            )
            return rx.toast.success("Phone updated and verified")
    ```
    """
    clerk_state = await _get_state_within_handler(current_state, ClerkState)
    user_id = clerk_state.user_id
    if user_id is None:
        raise MissingUserError("No user_id to update phone for")

    new_phone: clerk_backend_api.models.PhoneNumber | None = None

    if phone_number:
        # Create new phone number (primary; verification controlled by parameter)
        new_phone = await clerk_state.client.phone_numbers.create_async(
            request=clerk_backend_api.models.CreatePhoneNumberRequestBody(
                user_id=user_id,
                phone_number=phone_number,
                verified=verified,
                primary=True,
            )
        )
        logging.debug("Created new phone number for user")

        # Delete old phone number if it existed
        if old_phone_id:
            try:
                await clerk_state.client.phone_numbers.delete_async(
                    phone_number_id=old_phone_id
                )
                logging.debug("Deleted old phone number")
            except Exception:
                logging.warning("Could not delete old phone number")
    else:
        # If phone_number is empty, just delete the old one
        if old_phone_id:
            await clerk_state.client.phone_numbers.delete_async(
                phone_number_id=old_phone_id
            )
            logging.debug("Deleted phone number")

    return new_phone


def register_on_auth_change_handler(handler: EventCallback) -> None:
    """Register a handler to be called any time the user logs in or out.

    Args:
        handler: The event handler function to be called.
    """
    ClerkState.register_dependent_handler(handler)


def clerk_provider(
    *children,
    publishable_key: str,
    secret_key: str | None = None,
    register_user_state: bool = False,
    appearance: Appearance | None = None,
    **props,
) -> rx.Component:
    """
    Create a ClerkProvider component to wrap your app/page that uses clerk authentication.

    Note: can also use `wrap_app` to wrap the entire app.

    Args:
        children: The children components to wrap.
        publishable_key: The Clerk Publishable Key for your instance.
        secret_key: Your Clerk app's Secret Key, which you can find in the Clerk Dashboard. It will be prefixed with sk_test_ in development instances and sk_live_ in production instances. Do not expose this on the frontend with a public environment variable.
        register_user_state: Whether to register the ClerkUser state to automatically load user information on login.
        appearance: Optional object to style your components. Will only affect Clerk components.
    """
    if secret_key:
        ClerkState._set_secret_key(secret_key)

    if register_user_state:
        register_on_auth_change_handler(ClerkUser.load_user)

    return ClerkProvider.create(
        ClerkSessionSynchronizer.create(*children),
        publishable_key=publishable_key,
        appearance=appearance,
        **props,
    )


def wrap_app(
    app: rx.App,
    publishable_key: str,
    secret_key: str | None = None,
    register_user_state: bool = False,
    appearance: Appearance | None = None,
    **props,
) -> rx.App:
    """Wraps the entire app with the ClerkProvider.

    For multi-page apps where all pages require Clerk authentication components (including knowing if the user
    is **not** signed in).

    Args:
        app: The Reflex app to wrap.
        publishable_key: The Clerk Publishable Key for your instance.
        secret_key: Your Clerk app's Secret Key. (not needed for frontend only)
        register_user_state: Whether to register the ClerkUser state to automatically load user information on login.
    """
    # 1 makes this the first wrapper around the content
    #  (0 would place it after, 100 would also wrap default reflex wrappers)
    app.app_wraps[(1, "ClerkProvider")] = lambda _: clerk_provider(
        publishable_key=publishable_key,
        secret_key=secret_key,
        register_user_state=register_user_state,
        appearance=appearance,
        **props,
    )
    return app
