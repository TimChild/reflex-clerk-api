from typing import Any

import reflex as rx

from reflex_clerk_api.base import ClerkBase
from reflex_clerk_api.models import Appearance


class CreateOrganization(ClerkBase):
    """
    The CreateOrganization component provides a form for users to create new organizations.

    This component renders Clerk's <CreateOrganization /> React component,
    allowing users to set up new organizations with customizable appearance and routing.
    """

    tag = "CreateOrganization"

    appearance: Appearance | None = None
    "Optional object to style your components. Will only affect Clerk components."

    path: str | None = None
    "The path where the component is mounted when routing is set to 'path'."

    routing: str | None = None
    "The routing strategy for your pages. Defaults to 'path' for frameworks that handle routing, or 'hash' for other SDKs."

    after_create_organization_url: str | None = None
    "The full URL or path to navigate to after creating an organization."

    skip_invitation_screen: bool | None = None
    "Controls whether to skip the invitation screen when creating an organization."

    hide_slug: bool | None = None
    "Controls whether the optional slug field in the Organization creation screen is hidden."

    fallback: rx.Component | None = None
    "An optional element to be rendered while the component is mounting."


class OrganizationProfile(ClerkBase):
    """
    The OrganizationProfile component allows users to manage their organization membership and security settings.

    This component renders Clerk's <OrganizationProfile /> React component,
    allowing users to manage organization information, members, billing, and security settings.
    """

    tag = "OrganizationProfile"

    appearance: Appearance | None = None
    "Optional object to style your components. Will only affect Clerk components."

    path: str | None = None
    "The path where the component is mounted when routing is set to 'path'."

    routing: str | None = None
    "The routing strategy for your pages. Defaults to 'path' for frameworks that handle routing, or 'hash' for other SDKs."

    after_leave_organization_url: str | None = None
    "The full URL or path to navigate to after leaving an organization."

    custom_pages: list[dict[str, Any]] | None = None
    "An array of custom pages to add to the organization profile."

    fallback: rx.Component | None = None
    "An optional element to be rendered while the component is mounting."


class OrganizationSwitcher(ClerkBase):
    """
    The OrganizationSwitcher component displays the currently active organization and allows users to switch between organizations.

    This component renders Clerk's <OrganizationSwitcher /> React component,
    providing a dropdown interface for organization switching with customizable appearance.
    """

    tag = "OrganizationSwitcher"

    appearance: Appearance | None = None
    "Optional object to style your components. Will only affect Clerk components."

    organization_profile_mode: str | None = None
    "Controls whether selecting the organization opens as a modal or navigates to a page. Defaults to 'modal'."

    organization_profile_url: str | None = None
    "The full URL or path leading to the organization management interface."

    organization_profile_props: dict | None = None
    "Specify options for the underlying OrganizationProfile component."

    create_organization_mode: str | None = None
    "Controls whether selecting create organization opens as a modal or navigates to a page. Defaults to 'modal'."

    create_organization_url: str | None = None
    "The full URL or path leading to the create organization interface."

    after_leave_organization_url: str | None = None
    "The full URL or path to navigate to after leaving an organization."

    after_create_organization_url: str | None = None
    "The full URL or path to navigate to after creating an organization."

    after_select_organization_url: str | None = None
    "The full URL or path to navigate to after selecting an organization."

    default_open: bool | None = None
    "Controls whether the OrganizationSwitcher should open by default during the first render."

    hide_personal: bool | None = None
    "Controls whether the personal account option is hidden in the switcher."

    hide_slug: bool | None = None
    "Controls whether the optional slug field in the Organization creation screen is hidden."

    fallback: rx.Component | None = None
    "An optional element to be rendered while the component is mounting."


class OrganizationList(ClerkBase):
    """
    The OrganizationList component displays a list of organizations that the user is a member of.

    This component renders Clerk's <OrganizationList /> React component,
    providing an interface to view and manage organization memberships.
    """

    tag = "OrganizationList"

    appearance: Appearance | None = None
    "Optional object to style your components. Will only affect Clerk components."

    after_create_organization_url: str | None = None
    "The full URL or path to navigate to after creating an organization."

    after_select_organization_url: str | None = None
    "The full URL or path to navigate to after selecting an organization."

    after_select_personal_url: str | None = None
    "The full URL or path to navigate to after selecting the personal account."

    create_organization_mode: str | None = None
    "Controls whether selecting create organization opens as a modal or navigates to a page. Defaults to 'modal'."

    create_organization_url: str | None = None
    "The full URL or path leading to the create organization interface."

    hide_personal: bool | None = None
    "Controls whether the personal account option is hidden in the list."

    hide_slug: bool | None = None
    "Controls whether the optional slug field in the Organization creation screen is hidden."

    skip_invitation_screen: bool | None = None
    "Controls whether to skip the invitation screen when creating an organization."

    fallback: rx.Component | None = None
    "An optional element to be rendered while the component is mounting."


create_organization = CreateOrganization.create
organization_profile = OrganizationProfile.create
organization_switcher = OrganizationSwitcher.create
organization_list = OrganizationList.create
