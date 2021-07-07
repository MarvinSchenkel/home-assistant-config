"""The Z-Wave JS integration."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Callable

from async_timeout import timeout
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.exceptions import BaseZwaveJSServerError, InvalidServerVersion
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.notification import (
    EntryControlNotification,
    NotificationNotification,
)
from zwave_js_server.model.value import Value, ValueNotification

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .addon import AddonError, AddonManager, AddonState, get_addon_manager
from .api import async_register_api
from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_COMMAND_CLASS_NAME,
    ATTR_DATA_TYPE,
    ATTR_ENDPOINT,
    ATTR_EVENT,
    ATTR_EVENT_DATA,
    ATTR_EVENT_LABEL,
    ATTR_EVENT_TYPE,
    ATTR_HOME_ID,
    ATTR_LABEL,
    ATTR_NODE_ID,
    ATTR_PARAMETERS,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_PROPERTY_KEY_NAME,
    ATTR_PROPERTY_NAME,
    ATTR_TYPE,
    ATTR_VALUE,
    ATTR_VALUE_RAW,
    CONF_ADDON_DEVICE,
    CONF_ADDON_NETWORK_KEY,
    CONF_DATA_COLLECTION_OPTED_IN,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_NETWORK_KEY,
    CONF_USB_PATH,
    CONF_USE_ADDON,
    DATA_CLIENT,
    DATA_PLATFORM_SETUP,
    DATA_UNSUBSCRIBE,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
    LOGGER,
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_UPDATED_EVENT,
)
from .discovery import ZwaveDiscoveryInfo, async_discover_values
from .helpers import async_enable_statistics, get_device_id, get_unique_id
from .migrate import async_migrate_discovered_value
from .services import ZWaveServices

CONNECT_TIMEOUT = 10
DATA_CLIENT_LISTEN_TASK = "client_listen_task"
DATA_START_PLATFORM_TASK = "start_platform_task"
DATA_CONNECT_FAILED_LOGGED = "connect_failed_logged"
DATA_INVALID_SERVER_VERSION_LOGGED = "invalid_server_version_logged"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Z-Wave JS component."""
    hass.data[DOMAIN] = {}
    return True


@callback
def register_node_in_dev_reg(
    hass: HomeAssistant,
    entry: ConfigEntry,
    dev_reg: device_registry.DeviceRegistry,
    client: ZwaveClient,
    node: ZwaveNode,
) -> device_registry.DeviceEntry:
    """Register node in dev reg."""
    params = {
        "config_entry_id": entry.entry_id,
        "identifiers": {get_device_id(client, node)},
        "sw_version": node.firmware_version,
        "name": node.name or node.device_config.description or f"Node {node.node_id}",
        "model": node.device_config.label,
        "manufacturer": node.device_config.manufacturer,
    }
    if node.location:
        params["suggested_area"] = node.location
    device = dev_reg.async_get_or_create(**params)

    async_dispatcher_send(hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device)

    return device


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Z-Wave JS from a config entry."""
    use_addon = entry.data.get(CONF_USE_ADDON)
    if use_addon:
        await async_ensure_addon_running(hass, entry)

    client = ZwaveClient(entry.data[CONF_URL], async_get_clientsession(hass))
    dev_reg = device_registry.async_get(hass)
    ent_reg = entity_registry.async_get(hass)
    entry_hass_data: dict = hass.data[DOMAIN].setdefault(entry.entry_id, {})

    unsubscribe_callbacks: list[Callable] = []
    entry_hass_data[DATA_CLIENT] = client
    entry_hass_data[DATA_UNSUBSCRIBE] = unsubscribe_callbacks
    entry_hass_data[DATA_PLATFORM_SETUP] = {}

    registered_unique_ids: dict[str, dict[str, set[str]]] = defaultdict(dict)

    async def async_on_node_ready(node: ZwaveNode) -> None:
        """Handle node ready event."""
        LOGGER.debug("Processing node %s", node)

        platform_setup_tasks = entry_hass_data[DATA_PLATFORM_SETUP]

        # register (or update) node in device registry
        device = register_node_in_dev_reg(hass, entry, dev_reg, client, node)
        # We only want to create the defaultdict once, even on reinterviews
        if device.id not in registered_unique_ids:
            registered_unique_ids[device.id] = defaultdict(set)

        value_updates_disc_info = []

        # run discovery on all node values and create/update entities
        for disc_info in async_discover_values(node):
            platform = disc_info.platform

            # This migration logic was added in 2021.3 to handle a breaking change to
            # the value_id format. Some time in the future, this call (as well as the
            # helper functions) can be removed.
            async_migrate_discovered_value(
                hass,
                ent_reg,
                registered_unique_ids[device.id][platform],
                device,
                client,
                disc_info,
            )

            if platform not in platform_setup_tasks:
                platform_setup_tasks[platform] = hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(entry, platform)
                )

            await platform_setup_tasks[platform]

            LOGGER.debug("Discovered entity: %s", disc_info)
            async_dispatcher_send(
                hass, f"{DOMAIN}_{entry.entry_id}_add_{platform}", disc_info
            )

            # Capture discovery info for values we want to watch for updates
            if disc_info.assumed_state:
                value_updates_disc_info.append(disc_info)

        # add listener for value updated events if necessary
        if value_updates_disc_info:
            unsubscribe_callbacks.append(
                node.on(
                    "value updated",
                    lambda event: async_on_value_updated(
                        value_updates_disc_info, event["value"]
                    ),
                )
            )

        # add listener for stateless node value notification events
        unsubscribe_callbacks.append(
            node.on(
                "value notification",
                lambda event: async_on_value_notification(event["value_notification"]),
            )
        )
        # add listener for stateless node notification events
        unsubscribe_callbacks.append(
            node.on(
                "notification",
                lambda event: async_on_notification(event["notification"]),
            )
        )

    async def async_on_node_added(node: ZwaveNode) -> None:
        """Handle node added event."""
        platform_setup_tasks = entry_hass_data[DATA_PLATFORM_SETUP]

        # We need to set up the sensor platform if it hasn't already been setup in
        # order to create the node status sensor
        if SENSOR_DOMAIN not in platform_setup_tasks:
            platform_setup_tasks[SENSOR_DOMAIN] = hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
            )

        # This guard ensures that concurrent runs of this function all await the
        # platform setup task
        if not platform_setup_tasks[SENSOR_DOMAIN].done():
            await platform_setup_tasks[SENSOR_DOMAIN]

        # Create a node status sensor for each device
        async_dispatcher_send(
            hass, f"{DOMAIN}_{entry.entry_id}_add_node_status_sensor", node
        )

        # we only want to run discovery when the node has reached ready state,
        # otherwise we'll have all kinds of missing info issues.
        if node.ready:
            await async_on_node_ready(node)
            return
        # if node is not yet ready, register one-time callback for ready state
        LOGGER.debug("Node added: %s - waiting for it to become ready", node.node_id)
        node.once(
            "ready",
            lambda event: hass.async_create_task(async_on_node_ready(event["node"])),
        )
        # we do submit the node to device registry so user has
        # some visual feedback that something is (in the process of) being added
        register_node_in_dev_reg(hass, entry, dev_reg, client, node)

    @callback
    def async_on_node_removed(node: ZwaveNode) -> None:
        """Handle node removed event."""
        # grab device in device registry attached to this node
        dev_id = get_device_id(client, node)
        device = dev_reg.async_get_device({dev_id})
        # note: removal of entity registry entry is handled by core
        dev_reg.async_remove_device(device.id)  # type: ignore
        registered_unique_ids.pop(device.id, None)  # type: ignore

    @callback
    def async_on_value_notification(notification: ValueNotification) -> None:
        """Relay stateless value notification events from Z-Wave nodes to hass."""
        device = dev_reg.async_get_device({get_device_id(client, notification.node)})
        raw_value = value = notification.value
        if notification.metadata.states:
            value = notification.metadata.states.get(str(value), value)
        hass.bus.async_fire(
            ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
            {
                ATTR_DOMAIN: DOMAIN,
                ATTR_NODE_ID: notification.node.node_id,
                ATTR_HOME_ID: client.driver.controller.home_id,
                ATTR_ENDPOINT: notification.endpoint,
                ATTR_DEVICE_ID: device.id,  # type: ignore
                ATTR_COMMAND_CLASS: notification.command_class,
                ATTR_COMMAND_CLASS_NAME: notification.command_class_name,
                ATTR_LABEL: notification.metadata.label,
                ATTR_PROPERTY: notification.property_,
                ATTR_PROPERTY_NAME: notification.property_name,
                ATTR_PROPERTY_KEY: notification.property_key,
                ATTR_PROPERTY_KEY_NAME: notification.property_key_name,
                ATTR_VALUE: value,
                ATTR_VALUE_RAW: raw_value,
            },
        )

    @callback
    def async_on_notification(
        notification: EntryControlNotification | NotificationNotification,
    ) -> None:
        """Relay stateless notification events from Z-Wave nodes to hass."""
        device = dev_reg.async_get_device({get_device_id(client, notification.node)})
        event_data = {
            ATTR_DOMAIN: DOMAIN,
            ATTR_NODE_ID: notification.node.node_id,
            ATTR_HOME_ID: client.driver.controller.home_id,
            ATTR_DEVICE_ID: device.id,  # type: ignore
            ATTR_COMMAND_CLASS: notification.command_class,
        }

        if isinstance(notification, EntryControlNotification):
            event_data.update(
                {
                    ATTR_COMMAND_CLASS_NAME: "Entry Control",
                    ATTR_EVENT_TYPE: notification.event_type,
                    ATTR_DATA_TYPE: notification.data_type,
                    ATTR_EVENT_DATA: notification.event_data,
                }
            )
        else:
            event_data.update(
                {
                    ATTR_COMMAND_CLASS_NAME: "Notification",
                    ATTR_LABEL: notification.label,
                    ATTR_TYPE: notification.type_,
                    ATTR_EVENT: notification.event,
                    ATTR_EVENT_LABEL: notification.event_label,
                    ATTR_PARAMETERS: notification.parameters,
                }
            )

        hass.bus.async_fire(ZWAVE_JS_NOTIFICATION_EVENT, event_data)

    @callback
    def async_on_value_updated(
        value_updates_disc_info: list[ZwaveDiscoveryInfo], value: Value
    ) -> None:
        """Fire value updated event."""
        # Get the discovery info for the value that was updated. If we can't
        # find the discovery info, we don't need to fire an event
        try:
            disc_info = next(
                disc_info
                for disc_info in value_updates_disc_info
                if disc_info.primary_value.value_id == value.value_id
            )
        except StopIteration:
            return

        device = dev_reg.async_get_device({get_device_id(client, value.node)})

        unique_id = get_unique_id(
            client.driver.controller.home_id, disc_info.primary_value.value_id
        )
        entity_id = ent_reg.async_get_entity_id(disc_info.platform, DOMAIN, unique_id)

        raw_value = value_ = value.value
        if value.metadata.states:
            value_ = value.metadata.states.get(str(value), value_)

        hass.bus.async_fire(
            ZWAVE_JS_VALUE_UPDATED_EVENT,
            {
                ATTR_NODE_ID: value.node.node_id,
                ATTR_HOME_ID: client.driver.controller.home_id,
                ATTR_DEVICE_ID: device.id,  # type: ignore
                ATTR_ENTITY_ID: entity_id,
                ATTR_COMMAND_CLASS: value.command_class,
                ATTR_COMMAND_CLASS_NAME: value.command_class_name,
                ATTR_ENDPOINT: value.endpoint,
                ATTR_PROPERTY: value.property_,
                ATTR_PROPERTY_NAME: value.property_name,
                ATTR_PROPERTY_KEY: value.property_key,
                ATTR_PROPERTY_KEY_NAME: value.property_key_name,
                ATTR_VALUE: value_,
                ATTR_VALUE_RAW: raw_value,
            },
        )

    # connect and throw error if connection failed
    try:
        async with timeout(CONNECT_TIMEOUT):
            await client.connect()
    except InvalidServerVersion as err:
        if not entry_hass_data.get(DATA_INVALID_SERVER_VERSION_LOGGED):
            LOGGER.error("Invalid server version: %s", err)
            entry_hass_data[DATA_INVALID_SERVER_VERSION_LOGGED] = True
        if use_addon:
            async_ensure_addon_updated(hass)
        raise ConfigEntryNotReady from err
    except (asyncio.TimeoutError, BaseZwaveJSServerError) as err:
        if not entry_hass_data.get(DATA_CONNECT_FAILED_LOGGED):
            LOGGER.error("Failed to connect: %s", err)
            entry_hass_data[DATA_CONNECT_FAILED_LOGGED] = True
        raise ConfigEntryNotReady from err
    else:
        LOGGER.info("Connected to Zwave JS Server")
        entry_hass_data[DATA_CONNECT_FAILED_LOGGED] = False
        entry_hass_data[DATA_INVALID_SERVER_VERSION_LOGGED] = False

    services = ZWaveServices(hass, ent_reg, dev_reg)
    services.async_register()

    # Set up websocket API
    async_register_api(hass)

    async def start_platforms() -> None:
        """Start platforms and perform discovery."""
        driver_ready = asyncio.Event()

        async def handle_ha_shutdown(event: Event) -> None:
            """Handle HA shutdown."""
            await disconnect_client(hass, entry)

        listen_task = asyncio.create_task(
            client_listen(hass, entry, client, driver_ready)
        )
        entry_hass_data[DATA_CLIENT_LISTEN_TASK] = listen_task
        unsubscribe_callbacks.append(
            hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
        )

        try:
            await driver_ready.wait()
        except asyncio.CancelledError:
            LOGGER.debug("Cancelling start platforms")
            return

        LOGGER.info("Connection to Zwave JS Server initialized")

        # If opt in preference hasn't been specified yet, we do nothing, otherwise
        # we apply the preference
        if opted_in := entry.data.get(CONF_DATA_COLLECTION_OPTED_IN):
            await async_enable_statistics(client)
        elif opted_in is False:
            await client.driver.async_disable_statistics()

        # Check for nodes that no longer exist and remove them
        stored_devices = device_registry.async_entries_for_config_entry(
            dev_reg, entry.entry_id
        )
        known_devices = [
            dev_reg.async_get_device({get_device_id(client, node)})
            for node in client.driver.controller.nodes.values()
        ]

        # Devices that are in the device registry that are not known by the controller can be removed
        for device in stored_devices:
            if device not in known_devices:
                dev_reg.async_remove_device(device.id)

        # run discovery on all ready nodes
        await asyncio.gather(
            *[
                async_on_node_added(node)
                for node in client.driver.controller.nodes.values()
            ]
        )

        # listen for new nodes being added to the mesh
        unsubscribe_callbacks.append(
            client.driver.controller.on(
                "node added",
                lambda event: hass.async_create_task(
                    async_on_node_added(event["node"])
                ),
            )
        )
        # listen for nodes being removed from the mesh
        # NOTE: This will not remove nodes that were removed when HA was not running
        unsubscribe_callbacks.append(
            client.driver.controller.on(
                "node removed", lambda event: async_on_node_removed(event["node"])
            )
        )

    platform_task = hass.async_create_task(start_platforms())
    entry_hass_data[DATA_START_PLATFORM_TASK] = platform_task

    return True


async def client_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: ZwaveClient,
    driver_ready: asyncio.Event,
) -> None:
    """Listen with the client."""
    should_reload = True
    try:
        await client.listen(driver_ready)
    except asyncio.CancelledError:
        should_reload = False
    except BaseZwaveJSServerError as err:
        LOGGER.error("Failed to listen: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        # We need to guard against unknown exceptions to not crash this task.
        LOGGER.exception("Unexpected exception: %s", err)

    # The entry needs to be reloaded since a new driver state
    # will be acquired on reconnect.
    # All model instances will be replaced when the new state is acquired.
    if should_reload:
        LOGGER.info("Disconnected from server. Reloading integration")
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def disconnect_client(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Disconnect client."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: ZwaveClient = data[DATA_CLIENT]
    listen_task: asyncio.Task = data[DATA_CLIENT_LISTEN_TASK]
    platform_task: asyncio.Task = data[DATA_START_PLATFORM_TASK]
    listen_task.cancel()
    platform_task.cancel()
    platform_setup_tasks = (
        hass.data[DOMAIN].get(entry.entry_id, {}).get(DATA_PLATFORM_SETUP, {}).values()
    )
    for task in platform_setup_tasks:
        task.cancel()

    await asyncio.gather(listen_task, platform_task, *platform_setup_tasks)

    if client.connected:
        await client.disconnect()
        LOGGER.info("Disconnected from Zwave JS Server")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    info = hass.data[DOMAIN][entry.entry_id]

    for unsub in info[DATA_UNSUBSCRIBE]:
        unsub()

    tasks = []
    for platform, task in info[DATA_PLATFORM_SETUP].items():
        if task.done():
            tasks.append(
                hass.config_entries.async_forward_entry_unload(entry, platform)
            )
        else:
            task.cancel()
            tasks.append(task)

    unload_ok = all(await asyncio.gather(*tasks))

    if DATA_CLIENT_LISTEN_TASK in info:
        await disconnect_client(hass, entry)

    hass.data[DOMAIN].pop(entry.entry_id)

    if entry.data.get(CONF_USE_ADDON) and entry.disabled_by:
        addon_manager: AddonManager = get_addon_manager(hass)
        LOGGER.debug("Stopping Z-Wave JS add-on")
        try:
            await addon_manager.async_stop_addon()
        except AddonError as err:
            LOGGER.error("Failed to stop the Z-Wave JS add-on: %s", err)
            return False

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    if not entry.data.get(CONF_INTEGRATION_CREATED_ADDON):
        return

    addon_manager: AddonManager = get_addon_manager(hass)
    try:
        await addon_manager.async_stop_addon()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_create_snapshot()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_uninstall_addon()
    except AddonError as err:
        LOGGER.error(err)


async def async_ensure_addon_running(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure that Z-Wave JS add-on is installed and running."""
    addon_manager: AddonManager = get_addon_manager(hass)
    if addon_manager.task_in_progress():
        raise ConfigEntryNotReady
    try:
        addon_info = await addon_manager.async_get_addon_info()
    except AddonError as err:
        LOGGER.error(err)
        raise ConfigEntryNotReady from err

    usb_path: str = entry.data[CONF_USB_PATH]
    network_key: str = entry.data[CONF_NETWORK_KEY]
    addon_state = addon_info.state

    if addon_state == AddonState.NOT_INSTALLED:
        addon_manager.async_schedule_install_setup_addon(
            usb_path, network_key, catch_error=True
        )
        raise ConfigEntryNotReady

    if addon_state == AddonState.NOT_RUNNING:
        addon_manager.async_schedule_setup_addon(
            usb_path, network_key, catch_error=True
        )
        raise ConfigEntryNotReady

    addon_options = addon_info.options
    addon_device = addon_options[CONF_ADDON_DEVICE]
    addon_network_key = addon_options[CONF_ADDON_NETWORK_KEY]
    updates = {}
    if usb_path != addon_device:
        updates[CONF_USB_PATH] = addon_device
    if network_key != addon_network_key:
        updates[CONF_NETWORK_KEY] = addon_network_key
    if updates:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})


@callback
def async_ensure_addon_updated(hass: HomeAssistant) -> None:
    """Ensure that Z-Wave JS add-on is updated and running."""
    addon_manager: AddonManager = get_addon_manager(hass)
    if addon_manager.task_in_progress():
        raise ConfigEntryNotReady
    addon_manager.async_schedule_update_addon(catch_error=True)
