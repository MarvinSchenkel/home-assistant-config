"""
Sensor component for waste pickup dates from dutch and belgium waste collectors
Original Author: Pippijn Stortelder
Current Version: 5.0.2 202200913
20220829 - Major change: Added Calendar support (credits @WouterTuinstra)
20220829 - Give persistant notifications unique id's
20220901 - Code cleanup
20220913 - Fix: translate today and tomorrow sensor

Example config:
Configuration.yaml:
afvalbeheer:
    wastecollector: Blink
    resources:
    - restafval
    - gft
    - papier
    - pmd
    postcode: 1111AA
    streetnumber: 1
    upcomingsensor: 0                # (optional)
    dateformat: '%d-%m-%Y'           # (optional)
    dateonly: 0                      # (optional)
    dateobject: 0                    # (optional)
    dayofweek: 1                     # (optional)
    name: ''                         # (optional)
    nameprefix: 1                    # (optional)
    builtinicons: 0                  # (optional)
"""

import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.const import Platform

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORM_SCHEMA, CONF_ID
from .API import Get_WasteData_From_Config


__version__ = "5.0.2"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.debug("Setup of Afvalbeheer component Rest API retriever")

    config = config.get(DOMAIN, None)

    if config is None:
        # This should not be nesseceary to keep the 'old' config methode using sensor and platform working.
        # If using sensor there is no DOMAIN entry in config but Platform function will be called from sensor.
        return True

    if not isinstance(config, list):
        config = [config]

    for conf in config:

        data = Get_WasteData_From_Config(hass, conf)

        hass.data.setdefault(DOMAIN, {})[conf[CONF_ID]] = data

        await hass.helpers.discovery.async_load_platform(
            Platform.SENSOR, DOMAIN, {"config": conf}, conf
        )

        # if you add boolean to config you could disable calendar entities from here
        hass.helpers.discovery.load_platform(
            Platform.CALENDAR, DOMAIN, {"config": conf}, conf
        )

        await data.schedule_update(timedelta())

    return True
