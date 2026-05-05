from __future__ import annotations
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up the Movie Tracker sensors."""
    sensors = [
        MovieTrackerCountSensor(hass, "Watched", "watched"),
        MovieTrackerCountSensor(hass, "Wishlist", "wishlist"),
        MovieTrackerLatestSensor(hass)
    ]
    async_add_entities(sensors, True)

class MovieTrackerCountSensor(SensorEntity):
    """Sensor for counting movies in a list."""
    def __init__(self, hass, name, list_key):
        self._hass = hass
        self._list_key = list_key
        self._attr_name = f"Movie Tracker {name}"
        self._attr_unique_id = f"movie_tracker_{list_key}_count"
        self._attr_icon = "mdi:movie-open" if list_key == "watched" else "mdi:heart"
        self._state = 0

    @property
    def state(self):
        return self._state

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        @callback
        def update_state():
            self.async_schedule_update_ha_state(True)
        
        self.async_on_remove(
            self._hass.bus.async_listen("movie_tracker_updated", update_state)
        )

    async def async_update(self):
        """Update the sensor state."""
        from homeassistant.helpers.storage import Store
        store = Store(self._hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        items = data.get(self._list_key, {})
        self._state = len(items)
        self._attr_extra_state_attributes = {
            "items": [m.get("title") for m in list(items.values())[:10]]
        }

class MovieTrackerLatestSensor(SensorEntity):
    """Sensor for the latest watched movie."""
    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Movie Tracker Latest Watched"
        self._attr_unique_id = "movie_tracker_latest_watched"
        self._attr_icon = "mdi:clock-check"
        self._state = "N/A"

    @property
    def state(self):
        return self._state

    async def async_added_to_hass(self):
        @callback
        def update_state():
            self.async_schedule_update_ha_state(True)
        self.async_on_remove(self._hass.bus.async_listen("movie_tracker_updated", update_state))

    async def async_update(self):
        from homeassistant.helpers.storage import Store
        store = Store(self._hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        watched = data.get("watched", {})
        if not watched:
            self._state = "Žádné"
            return
            
        # Sort by watched_at
        latest = sorted(watched.values(), key=lambda x: x.get("watched_at", ""), reverse=True)
        if latest:
            self._state = latest[0].get("title", "Neznámý")
            self._attr_extra_state_attributes = {
                "id": latest[0].get("id"),
                "watched_at": latest[0].get("watched_at"),
                "poster": latest[0].get("poster")
            }
