"""Sensor platform for onebusaway."""
from __future__ import annotations
from datetime import datetime, timezone
from time import time

from homeassistant.helpers.entity import DeviceInfo

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.const import (
    CONF_URL,
    CONF_ID,
    CONF_TOKEN,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTRIBUTION, DOMAIN, NAME, VERSION

from .api import OneBusAwayApiClient

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="onebusaway",
        name="OneBusAway Sensor",
        icon="mdi:bus-clock",
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    client = OneBusAwayApiClient(
        url=entry.data[CONF_URL],
        key=entry.data[CONF_TOKEN],
        stop=entry.data[CONF_ID],
        session=async_get_clientsession(hass),
    )
    async_add_devices(
        OneBusAwaySensor(
            client=client,
            entity_description=entity_description,
            stop=entry.data[CONF_ID],
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class OneBusAwaySensor(SensorEntity):
    """onebusaway Sensor class."""

    def __init__(
        self,
        client: OneBusAwayApiClient,
        entity_description: SensorEntityDescription,
        stop: str,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__()
        self.entity_description = entity_description
        self.client = client
        self._attr_attribution = ATTRIBUTION
        self._attr_unique_id = stop
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop)},
            name=NAME,
            model=VERSION,
            manufacturer=NAME,
        )

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    data = None
    unsub = None
    next_arrival = None

    def compute_next(self) -> datetime:
        """Compute the next arrival time from the last read data."""
        if self.data is None:
            return None
        # This is a unix timestamp value except in
        # milliseconds because precision is super
        # important when discussing train departure
        # times
        current = time() * 1000
        # We want the soonest time that is after the current time
        departures = [
            d["predictedDepartureTime"]
            for d in self.data.get("data")["entry"]["arrivalsAndDepartures"]
            if d["predictedDepartureTime"] > current
        ]
        departure = min(departures) / 1000
        return datetime.fromtimestamp(departure, timezone.utc)

    def refresh(self, _timestamp) -> None:
        """Invalidate the current sensor state."""
        self.schedule_update_ha_state(True)

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        return self.next_arrival

    async def async_update(self):
        """Retrieve latest state."""
        self.data = await self.client.async_get_data()

        soonest = self.compute_next()
        if soonest != self.next_arrival:
            self.next_arrival = soonest
            if self.unsub is not None:
                self.unsub()

            #
            # set a timer to go off at the next arrival time so we can
            # invalidate the state
            #
            self.unsub = async_track_point_in_time(
                self.hass, self.refresh, self.next_arrival
            )
