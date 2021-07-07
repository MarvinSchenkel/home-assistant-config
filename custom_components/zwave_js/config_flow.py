"""Config flow for Z-Wave JS integration."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
import logging
from typing import Any

import aiohttp
from async_timeout import timeout
import voluptuous as vol
from zwave_js_server.version import VersionInfo, get_server_version

from homeassistant import config_entries, exceptions
from homeassistant.components.hassio import is_hassio
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import (
    AbortFlow,
    FlowHandler,
    FlowManager,
    FlowResult,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import disconnect_client
from .addon import AddonError, AddonInfo, AddonManager, AddonState, get_addon_manager
from .const import (
    CONF_ADDON_DEVICE,
    CONF_ADDON_EMULATE_HARDWARE,
    CONF_ADDON_LOG_LEVEL,
    CONF_ADDON_NETWORK_KEY,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_NETWORK_KEY,
    CONF_USB_PATH,
    CONF_USE_ADDON,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "ws://localhost:3000"
TITLE = "Z-Wave JS"

ADDON_SETUP_TIMEOUT = 5
ADDON_SETUP_TIMEOUT_ROUNDS = 4
CONF_EMULATE_HARDWARE = "emulate_hardware"
CONF_LOG_LEVEL = "log_level"
SERVER_VERSION_TIMEOUT = 10

ADDON_LOG_LEVELS = {
    "error": "Error",
    "warn": "Warn",
    "info": "Info",
    "verbose": "Verbose",
    "debug": "Debug",
    "silly": "Silly",
}
ADDON_USER_INPUT_MAP = {
    CONF_ADDON_DEVICE: CONF_USB_PATH,
    CONF_ADDON_NETWORK_KEY: CONF_NETWORK_KEY,
    CONF_ADDON_LOG_LEVEL: CONF_LOG_LEVEL,
    CONF_ADDON_EMULATE_HARDWARE: CONF_EMULATE_HARDWARE,
}

ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=True): bool})


def get_manual_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the manual step."""
    default_url = user_input.get(CONF_URL, DEFAULT_URL)
    return vol.Schema({vol.Required(CONF_URL, default=default_url): str})


def get_on_supervisor_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the on Supervisor step."""
    default_use_addon = user_input[CONF_USE_ADDON]
    return vol.Schema({vol.Optional(CONF_USE_ADDON, default=default_use_addon): bool})


async def validate_input(hass: HomeAssistant, user_input: dict) -> VersionInfo:
    """Validate if the user input allows us to connect."""
    ws_address = user_input[CONF_URL]

    if not ws_address.startswith(("ws://", "wss://")):
        raise InvalidInput("invalid_ws_url")

    try:
        return await async_get_version_info(hass, ws_address)
    except CannotConnect as err:
        raise InvalidInput("cannot_connect") from err


async def async_get_version_info(hass: HomeAssistant, ws_address: str) -> VersionInfo:
    """Return Z-Wave JS version info."""
    try:
        async with timeout(SERVER_VERSION_TIMEOUT):
            version_info: VersionInfo = await get_server_version(
                ws_address, async_get_clientsession(hass)
            )
    except (asyncio.TimeoutError, aiohttp.ClientError) as err:
        # We don't want to spam the log if the add-on isn't started
        # or takes a long time to start.
        _LOGGER.debug("Failed to connect to Z-Wave JS server: %s", err)
        raise CannotConnect from err

    return version_info


class BaseZwaveJSFlow(FlowHandler):
    """Represent the base config flow for Z-Wave JS."""

    def __init__(self) -> None:
        """Set up flow instance."""
        self.network_key: str | None = None
        self.usb_path: str | None = None
        self.ws_address: str | None = None
        self.restart_addon: bool = False
        # If we install the add-on we should uninstall it on entry remove.
        self.integration_created_addon = False
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.version_info: VersionInfo | None = None

    @property
    @abstractmethod
    def flow_manager(self) -> FlowManager:
        """Return the flow manager of the flow."""

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Install Z-Wave JS add-on."""
        if not self.install_task:
            self.install_task = self.hass.async_create_task(self._async_install_addon())
            return self.async_show_progress(
                step_id="install_addon", progress_action="install_addon"
            )

        try:
            await self.install_task
        except AddonError as err:
            self.install_task = None
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")

        self.integration_created_addon = True
        self.install_task = None

        return self.async_show_progress_done(next_step_id="configure_addon")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on installation failed."""
        return self.async_abort(reason="addon_install_failed")

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start Z-Wave JS add-on."""
        if not self.start_task:
            self.start_task = self.hass.async_create_task(self._async_start_addon())
            return self.async_show_progress(
                step_id="start_addon", progress_action="start_addon"
            )

        try:
            await self.start_task
        except (CannotConnect, AddonError, AbortFlow) as err:
            self.start_task = None
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")

        self.start_task = None
        return self.async_show_progress_done(next_step_id="finish_addon_setup")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on start failed."""
        return self.async_abort(reason="addon_start_failed")

    async def _async_start_addon(self) -> None:
        """Start the Z-Wave JS add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        self.version_info = None
        try:
            if self.restart_addon:
                await addon_manager.async_schedule_restart_addon()
            else:
                await addon_manager.async_schedule_start_addon()
            # Sleep some seconds to let the add-on start properly before connecting.
            for _ in range(ADDON_SETUP_TIMEOUT_ROUNDS):
                await asyncio.sleep(ADDON_SETUP_TIMEOUT)
                try:
                    if not self.ws_address:
                        discovery_info = await self._async_get_addon_discovery_info()
                        self.ws_address = (
                            f"ws://{discovery_info['host']}:{discovery_info['port']}"
                        )
                    self.version_info = await async_get_version_info(
                        self.hass, self.ws_address
                    )
                except (AbortFlow, CannotConnect) as err:
                    _LOGGER.debug(
                        "Add-on not ready yet, waiting %s seconds: %s",
                        ADDON_SETUP_TIMEOUT,
                        err,
                    )
                else:
                    break
            else:
                raise CannotConnect("Failed to start Z-Wave JS add-on: timeout")
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    @abstractmethod
    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for config for Z-Wave JS add-on."""

    @abstractmethod
    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prepare info needed to complete the config entry.

        Get add-on discovery info and server version info.
        Set unique id and abort if already configured.
        """

    async def _async_get_addon_info(self) -> AddonInfo:
        """Return and cache Z-Wave JS add-on info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_info_failed") from err

        return addon_info

    async def _async_set_addon_config(self, config: dict) -> None:
        """Set Z-Wave JS add-on config."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            await addon_manager.async_set_addon_options(config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_set_config_failed") from err

    async def _async_install_addon(self) -> None:
        """Install the Z-Wave JS add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            await addon_manager.async_schedule_install_addon()
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.flow_manager.async_configure(flow_id=self.flow_id)
            )

    async def _async_get_addon_discovery_info(self) -> dict:
        """Return add-on discovery info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            discovery_info_config = await addon_manager.async_get_addon_discovery_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_get_discovery_info_failed") from err

        return discovery_info_config


class ConfigFlow(BaseZwaveJSFlow, config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Z-Wave JS."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        super().__init__()
        self.use_addon = False

    @property
    def flow_manager(self) -> config_entries.ConfigEntriesFlowManager:
        """Return the correct flow manager."""
        return self.hass.config_entries.flow

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor()

        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a manual configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual", data_schema=get_manual_schema({})
            )

        errors = {}

        try:
            version_info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            errors["base"] = err.error
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(
                version_info.home_id, raise_on_progress=False
            )
            # Make sure we disable any add-on handling
            # if the controller is reconfigured in a manual step.
            self._abort_if_unique_id_configured(
                updates={
                    **user_input,
                    CONF_USE_ADDON: False,
                    CONF_INTEGRATION_CREATED_ADDON: False,
                }
            )
            self.ws_address = user_input[CONF_URL]
            return self._async_create_entry_from_vars()

        return self.async_show_form(
            step_id="manual", data_schema=get_manual_schema(user_input), errors=errors
        )

    async def async_step_hassio(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Receive configuration from add-on discovery info.

        This flow is triggered by the Z-Wave JS add-on.
        """
        self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"
        try:
            version_info = await async_get_version_info(self.hass, self.ws_address)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(version_info.home_id)
        self._abort_if_unique_id_configured(updates={CONF_URL: self.ws_address})

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the add-on discovery."""
        if user_input is not None:
            return await self.async_step_on_supervisor(
                user_input={CONF_USE_ADDON: True}
            )

        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
            )
        if not user_input[CONF_USE_ADDON]:
            return await self.async_step_manual()

        self.use_addon = True

        addon_info = await self._async_get_addon_info()

        if addon_info.state == AddonState.RUNNING:
            addon_config = addon_info.options
            self.usb_path = addon_config[CONF_ADDON_DEVICE]
            self.network_key = addon_config.get(CONF_ADDON_NETWORK_KEY, "")
            return await self.async_step_finish_addon_setup()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_configure_addon()

        return await self.async_step_install_addon()

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for config for Z-Wave JS add-on."""
        addon_info = await self._async_get_addon_info()
        addon_config = addon_info.options

        if user_input is not None:
            self.network_key = user_input[CONF_NETWORK_KEY]
            self.usb_path = user_input[CONF_USB_PATH]

            new_addon_config = {
                **addon_config,
                CONF_ADDON_DEVICE: self.usb_path,
                CONF_ADDON_NETWORK_KEY: self.network_key,
            }

            if new_addon_config != addon_config:
                await self._async_set_addon_config(new_addon_config)

            return await self.async_step_start_addon()

        usb_path = addon_config.get(CONF_ADDON_DEVICE, self.usb_path or "")
        network_key = addon_config.get(CONF_ADDON_NETWORK_KEY, self.network_key or "")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PATH, default=usb_path): str,
                vol.Optional(CONF_NETWORK_KEY, default=network_key): str,
            }
        )

        return self.async_show_form(step_id="configure_addon", data_schema=data_schema)

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prepare info needed to complete the config entry.

        Get add-on discovery info and server version info.
        Set unique id and abort if already configured.
        """
        if not self.ws_address:
            discovery_info = await self._async_get_addon_discovery_info()
            self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"

        if not self.unique_id:
            if not self.version_info:
                try:
                    self.version_info = await async_get_version_info(
                        self.hass, self.ws_address
                    )
                except CannotConnect as err:
                    raise AbortFlow("cannot_connect") from err

            await self.async_set_unique_id(
                self.version_info.home_id, raise_on_progress=False
            )

        self._abort_if_unique_id_configured(
            updates={
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_NETWORK_KEY: self.network_key,
            }
        )
        return self._async_create_entry_from_vars()

    @callback
    def _async_create_entry_from_vars(self) -> FlowResult:
        """Return a config entry for the flow."""
        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_NETWORK_KEY: self.network_key,
                CONF_USE_ADDON: self.use_addon,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )


class OptionsFlowHandler(BaseZwaveJSFlow, config_entries.OptionsFlow):
    """Handle an options flow for Z-Wave JS."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Set up the options flow."""
        super().__init__()
        self.config_entry = config_entry
        self.original_addon_config: dict[str, Any] | None = None
        self.revert_reason: str | None = None

    @property
    def flow_manager(self) -> config_entries.OptionsFlowManager:
        """Return the correct flow manager."""
        return self.hass.config_entries.options

    @callback
    def _async_update_entry(self, data: dict[str, Any]) -> None:
        """Update the config entry with new data."""
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor()

        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a manual configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=get_manual_schema(
                    {CONF_URL: self.config_entry.data[CONF_URL]}
                ),
            )

        errors = {}

        try:
            version_info = await validate_input(self.hass, user_input)
        except InvalidInput as err:
            errors["base"] = err.error
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if self.config_entry.unique_id != version_info.home_id:
                return self.async_abort(reason="different_device")

            # Make sure we disable any add-on handling
            # if the controller is reconfigured in a manual step.
            self._async_update_entry(
                {
                    **self.config_entry.data,
                    **user_input,
                    CONF_USE_ADDON: False,
                    CONF_INTEGRATION_CREATED_ADDON: False,
                }
            )

            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            return self.async_create_entry(title=TITLE, data={})

        return self.async_show_form(
            step_id="manual", data_schema=get_manual_schema(user_input), errors=errors
        )

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor",
                data_schema=get_on_supervisor_schema(
                    {CONF_USE_ADDON: self.config_entry.data.get(CONF_USE_ADDON, True)}
                ),
            )
        if not user_input[CONF_USE_ADDON]:
            return await self.async_step_manual()

        addon_info = await self._async_get_addon_info()

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_addon()

        return await self.async_step_configure_addon()

    async def async_step_configure_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for config for Z-Wave JS add-on."""
        addon_info = await self._async_get_addon_info()
        addon_config = addon_info.options

        if user_input is not None:
            self.network_key = user_input[CONF_NETWORK_KEY]
            self.usb_path = user_input[CONF_USB_PATH]

            new_addon_config = {
                **addon_config,
                CONF_ADDON_DEVICE: self.usb_path,
                CONF_ADDON_NETWORK_KEY: self.network_key,
                CONF_ADDON_LOG_LEVEL: user_input[CONF_LOG_LEVEL],
                CONF_ADDON_EMULATE_HARDWARE: user_input[CONF_EMULATE_HARDWARE],
            }

            if new_addon_config != addon_config:
                if addon_info.state == AddonState.RUNNING:
                    self.restart_addon = True
                # Copy the add-on config to keep the objects separate.
                self.original_addon_config = dict(addon_config)
                await self._async_set_addon_config(new_addon_config)

            if addon_info.state == AddonState.RUNNING and not self.restart_addon:
                return await self.async_step_finish_addon_setup()

            if (
                self.config_entry.data.get(CONF_USE_ADDON)
                and self.config_entry.state == config_entries.ConfigEntryState.LOADED
            ):
                # Disconnect integration before restarting add-on.
                await disconnect_client(self.hass, self.config_entry)

            return await self.async_step_start_addon()

        usb_path = addon_config.get(CONF_ADDON_DEVICE, self.usb_path or "")
        network_key = addon_config.get(CONF_ADDON_NETWORK_KEY, self.network_key or "")
        log_level = addon_config.get(CONF_ADDON_LOG_LEVEL, "info")
        emulate_hardware = addon_config.get(CONF_ADDON_EMULATE_HARDWARE, False)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PATH, default=usb_path): str,
                vol.Optional(CONF_NETWORK_KEY, default=network_key): str,
                vol.Optional(CONF_LOG_LEVEL, default=log_level): vol.In(
                    ADDON_LOG_LEVELS
                ),
                vol.Optional(CONF_EMULATE_HARDWARE, default=emulate_hardware): bool,
            }
        )

        return self.async_show_form(step_id="configure_addon", data_schema=data_schema)

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add-on start failed."""
        return await self.async_revert_addon_config(reason="addon_start_failed")

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prepare info needed to complete the config entry update.

        Get add-on discovery info and server version info.
        Check for same unique id and abort if not the same unique id.
        """
        if self.revert_reason:
            self.original_addon_config = None
            reason = self.revert_reason
            self.revert_reason = None
            return await self.async_revert_addon_config(reason=reason)

        if not self.ws_address:
            discovery_info = await self._async_get_addon_discovery_info()
            self.ws_address = f"ws://{discovery_info['host']}:{discovery_info['port']}"

        if not self.version_info:
            try:
                self.version_info = await async_get_version_info(
                    self.hass, self.ws_address
                )
            except CannotConnect:
                return await self.async_revert_addon_config(reason="cannot_connect")

        if self.config_entry.unique_id != self.version_info.home_id:
            return await self.async_revert_addon_config(reason="different_device")

        self._async_update_entry(
            {
                **self.config_entry.data,
                CONF_URL: self.ws_address,
                CONF_USB_PATH: self.usb_path,
                CONF_NETWORK_KEY: self.network_key,
                CONF_USE_ADDON: True,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            }
        )
        # Always reload entry since we may have disconnected the client.
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
        return self.async_create_entry(title=TITLE, data={})

    async def async_revert_addon_config(self, reason: str) -> FlowResult:
        """Abort the options flow.

        If the add-on options have been changed, revert those and restart add-on.
        """
        # If reverting the add-on options failed, abort immediately.
        if self.revert_reason:
            _LOGGER.error(
                "Failed to revert add-on options before aborting flow, reason: %s",
                reason,
            )

        if self.revert_reason or not self.original_addon_config:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            return self.async_abort(reason=reason)

        self.revert_reason = reason
        addon_config_input = {
            ADDON_USER_INPUT_MAP[addon_key]: addon_val
            for addon_key, addon_val in self.original_addon_config.items()
        }
        _LOGGER.debug("Reverting add-on options, reason: %s", reason)
        return await self.async_step_configure_addon(addon_config_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Indicate connection error."""


class InvalidInput(exceptions.HomeAssistantError):
    """Error to indicate input data is invalid."""

    def __init__(self, error: str) -> None:
        """Initialize error."""
        super().__init__()
        self.error = error
