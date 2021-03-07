"""Support for Picnic sensors"""

import logging
from datetime import datetime, timedelta
from functools import partial
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)

from python_picnic_api import PicnicAPI

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

_LOGGER = logging.getLogger(__name__)

SLOT_TIMES = ["window_start", "window_end", "cut_off_time"]

COUNTRY_CODE = "country_code"

CART_ICON = "mdi:cart"
CART_NAME = "picnic_cart"

DELIVERY_ICON = "mdi:truck-delivery"
DELIVERY_NAME = "picnic_delivery"

DELIVERY_TIME_SLOT_ICON = "mdi:calendar-clock"
DELIVERY_TIME_SLOT_NAME = "picnic_delivery_time_slots"

ATTRIBUTION = "Information provided by Picnic.app"

ATTR_ATTRIBUTION = "attribution"
ATTR_DELIVERY = "delivery"
ATTR_TIME_SLOTS = "time_slots"
ATTR_PRICE = "price"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(COUNTRY_CODE, default="NL"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Picnic sensor"""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    country_code = config.get(COUNTRY_CODE)

    api = await hass.async_add_executor_job(
        partial(
            PicnicAPI, username=username, password=password, country_code=country_code
        )
    )
    data = PicnicData(hass, config, api)

    entities = [CartSensor(data), DeliverySensor(data), DeliveryTimeSlotSensor(data)]
    async_add_entities(entities, True)


class PicnicData:
    """Handle Picnic data object"""

    def __init__(self, hass, config, api):
        """Initialize the data object"""
        # try
        self._api = api
        self.hass = hass
        self.cart = None
        self.current_deliveries = {}
        self.open_delivery_time_slots = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update data"""
        await self.hass.async_add_executor_job(self._get_data)

    def _get_data(self):
        #        try:
        self.cart = self._api.get_cart()
        self.current_deliveries = self._api.get_deliveries()[0]
        self.open_delivery_time_slots = self.cart["delivery_slots"]
        _LOGGER.debug("Updated data from Picnic")


#       Not yet implemented in python_picnic_api
#        except UnauthorizedException:
#            _LOGGER.error("Can't connect to the Picnic API. Is your username/password valid?")


class CartSensor(Entity):
    """Cart Sensor class"""

    def __init__(self, data):
        self.attr = {}
        self._state = None
        self._data = data
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_PRICE: None,
        }

    async def async_update(self):
        """Update the sensor"""
        await self._data.async_update()

        if self._data.cart is None:
            return

        self._state = self._data.cart["total_count"]
        self._attributes[ATTR_PRICE] = self._data.cart["total_price"]

    @property
    def name(self):
        """Return the name of the sensor"""
        return CART_NAME

    @property
    def state(self):
        """Return the state of the sensor"""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor"""
        return CART_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes"""
        return self._attributes


class DeliverySensor(Entity):
    """Delivery Sensor class"""

    def __init__(self, data):
        self.attr = {}
        self._state = None
        self._data = data
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_DELIVERY: [],
        }

    async def async_update(self):
        """Update the sensor"""
        await self._data.async_update()

        self._attributes[ATTR_DELIVERY] = {}
        self._state = None

        delivery = self._data.current_deliveries

        if not delivery:
            return

        data = {}
        data["creation_time"] = delivery["creation_time"]
        data["delivery_id"] = delivery["delivery_id"]
        data.update(delivery["slot"])

        if "eta2" in delivery.keys():
            data["window_start"] = delivery["eta2"]["start"]
            data["window_end"] = delivery["eta2"]["end"]

        for time in SLOT_TIMES:
            if isinstance(data[time], str):
                data[time] = datetime.fromisoformat(data[time])

        self._attributes[ATTR_DELIVERY] = data

        if delivery["status"] == "COMPLETED":
            self._state = "order_delivered"
        elif "eta2" in delivery.keys():
            self._state = "order_announced"
        elif delivery["status"] == "CURRENT":
            self._state = "order_placed"

    @property
    def name(self):
        """Return the name of the sensor"""
        return DELIVERY_NAME

    @property
    def state(self):
        """Return the state of the sensor"""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor"""
        return DELIVERY_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes"""
        return self._attributes


class DeliveryTimeSlotSensor(Entity):
    """Delivery Time Slot Sensor class"""

    def __init__(self, data):
        self.attr = {}
        self._state = None
        self._data = data
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_TIME_SLOTS: [],
        }

    async def async_update(self):
        """Update the sensor"""
        await self._data.async_update()

        self._attributes[ATTR_TIME_SLOTS] = []
        self._state = None

        slots = self._data.open_delivery_time_slots

        if not slots:
            return

        for slot in slots:
            for time in SLOT_TIMES:
                if isinstance(slot[time], str):
                    slot[time] = datetime.fromisoformat(slot[time])
            if slot['is_available']:
                self._attributes[ATTR_TIME_SLOTS].append(slot)

        if len(self._attributes[ATTR_TIME_SLOTS]) > 0:
            self._state = self._attributes[ATTR_TIME_SLOTS][0]["window_start"]

    @property
    def name(self):
        """Return the name of the sensor"""
        return DELIVERY_TIME_SLOT_NAME

    @property
    def state(self):
        """Return the state of the sensor"""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor"""
        return DELIVERY_TIME_SLOT_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes"""
        return self._attributes
