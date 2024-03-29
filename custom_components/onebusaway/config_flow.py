"""Adds config flow for Blueprint."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_ID, CONF_TOKEN
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    OneBusAwayApiClient,
    OneBusAwayApiClientAuthenticationError,
    OneBusAwayApiClientCommunicationError,
    OneBusAwayApiClientError,
)
from .const import DOMAIN, LOGGER


class OneBusAwayFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Blueprint."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                arrival = await self._test_url(
                    url=user_input[CONF_URL],
                    key=user_input[CONF_TOKEN],
                    stop=user_input[CONF_ID],
                )
            except OneBusAwayApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except OneBusAwayApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except OneBusAwayApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=arrival["routeShortName"],
                    description=arrival["routeLongName"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default="https://api.pugetsound.onebusaway.org/api"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.URL),
                    ),
                    vol.Optional(
                        CONF_TOKEN, default="e1452dde-44fa-4bf9-821b-96ace8fbcbf6"
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                    vol.Required(CONF_ID, default="1_55778"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                }
            ),
            errors=_errors,
        )

    async def _test_url(self, url: str, key: str, stop: str):
        """Validate credentials."""
        client = OneBusAwayApiClient(
            url=url,
            key=key,
            stop=stop,
            session=async_create_clientsession(self.hass),
        )
        json = await client.async_get_data()
        return json["data"]["entry"]["arrivalsAndDepartures"][0]
