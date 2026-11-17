"""NAD receiver media player, kept current by pushes from the receiver."""

from __future__ import annotations

from typing import override

import probatio as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import NadClient

CONF_MIN_VOLUME = "min_volume"
CONF_MAX_VOLUME = "max_volume"
CONF_SOURCES = "sources"

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=23): int,
        vol.Optional(CONF_NAME, default="NAD Receiver"): cv.string,
        vol.Optional(CONF_MIN_VOLUME, default=-92): int,
        vol.Optional(CONF_MAX_VOLUME, default=-20): int,
        vol.Optional(CONF_SOURCES, default={}): vol.Schema(
            {vol.Range(min=1, max=12): cv.string}
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NAD telnet media player."""
    async_add_entities([NadTelnet(config)])


class NadTelnet(MediaPlayerEntity):
    """NAD receiver on one long-lived telnet connection."""

    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_icon = "mdi:speaker-multiple"
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, config: ConfigType) -> None:
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = f"nad_telnet_{config[CONF_HOST]}"
        self._min_volume = config[CONF_MIN_VOLUME]
        self._max_volume = config[CONF_MAX_VOLUME]
        self._sources = {str(k): v for k, v in config[CONF_SOURCES].items()}
        self._source_ids = {v: k for k, v in self._sources.items()}
        self._attr_source_list = list(self._sources.values())
        self._client = NadClient(
            config[CONF_HOST], config[CONF_PORT], self._handle_change
        )

    @override
    async def async_added_to_hass(self) -> None:
        self._client.start()

    @override
    async def async_will_remove_from_hass(self) -> None:
        await self._client.stop()

    @callback
    def _handle_change(self) -> None:
        if self.hass:
            self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        return self._client.connected and "Main.Power" in self._client.state

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        power = self._client.state.get("Main.Power")
        if power is None:
            return None
        return MediaPlayerState.ON if power == "On" else MediaPlayerState.OFF

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        mute = self._client.state.get("Main.Mute")
        return None if mute is None else mute == "On"

    @property
    @override
    def volume_level(self) -> float | None:
        try:
            db = float(self._client.state["Main.Volume"])
        except (KeyError, ValueError):
            return None
        level = (db - self._min_volume) / (self._max_volume - self._min_volume)
        return min(max(level, 0.0), 1.0)

    @property
    @override
    def source(self) -> str | None:
        """Configured name of the active input, else `Input <n>`."""
        number = self._client.state.get("Main.Source")
        if number is None:
            return None
        return self._sources.get(number, f"Input {number}")

    async def async_turn_on(self) -> None:
        await self._client.send("Main.Power=On")

    async def async_turn_off(self) -> None:
        await self._client.send("Main.Power=Off")

    async def async_volume_up(self) -> None:
        await self._client.send("Main.Volume+")

    async def async_volume_down(self) -> None:
        await self._client.send("Main.Volume-")

    async def async_set_volume_level(self, volume: float) -> None:
        db = self._min_volume + round((self._max_volume - self._min_volume) * volume)
        await self._client.send(f"Main.Volume={db}")

    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.send(f"Main.Mute={'On' if mute else 'Off'}")

    async def async_select_source(self, source: str) -> None:
        if source in self._source_ids:
            await self._client.send(f"Main.Source={self._source_ids[source]}")
