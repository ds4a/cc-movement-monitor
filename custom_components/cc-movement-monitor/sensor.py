"""CC Movement Monitor — Sensor Entities."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DOMAIN,
    ENTITY_LATITUDE, ENTITY_LONGITUDE, ENTITY_SPEED, ENTITY_FIX,
    ENTITY_LAST_MOVED, ENTITY_STATIONARY_HOURS, ENTITY_STATIONARY_DAYS,
    ENTITY_DAYS_REMAINING, ENTITY_STATUS,
    STATUS_OK, STATUS_WARN, STATUS_ALERT, STATUS_NO_FIX,
)
from .coordinator import BoatCoordinator

_LOGGER = logging.getLogger(__name__)

_DEVICE_INFO_CACHE: dict[str, DeviceInfo] = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                             async_add_entities: AddEntitiesCallback) -> None:
    coordinator: BoatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BoatLatitudeSensor(coordinator, entry),
        BoatLongitudeSensor(coordinator, entry),
        BoatSpeedSensor(coordinator, entry),
        BoatGpsFixSensor(coordinator, entry),
        BoatLastMovedSensor(coordinator, entry),
        BoatStationaryHoursSensor(coordinator, entry),
        BoatStationaryDaysSensor(coordinator, entry),
        BoatDaysRemainingSensor(coordinator, entry),
        BoatMooringStatusSensor(coordinator, entry),
    ])


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    if entry.entry_id not in _DEVICE_INFO_CACHE:
        _DEVICE_INFO_CACHE[entry.entry_id] = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="CC Movement Monitor",
            manufacturer="Custom Integration",
            model="Victron Cerbo GX via Modbus TCP",
            sw_version="1.0.0",
        )
    return _DEVICE_INFO_CACHE[entry.entry_id]


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BoatCoordinator, entry: ConfigEntry, suffix: str):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id  = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = _device_info(entry)

    def _cfg(self, key, default=None):
        return self._entry.options.get(key, self._entry.data.get(key, default))

    @property
    def _data(self):
        return self.coordinator.data or {}


# ── Raw GPS ──────────────────────────────────────────────────────────────────

class BoatLatitudeSensor(_Base):
    _attr_name = "Latitude"
    _attr_icon = "mdi:latitude"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 7
    def __init__(self, c, e): super().__init__(c, e, ENTITY_LATITUDE)
    @property
    def native_value(self): return self._data.get("latitude")

class BoatLongitudeSensor(_Base):
    _attr_name = "Longitude"
    _attr_icon = "mdi:longitude"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 7
    def __init__(self, c, e): super().__init__(c, e, ENTITY_LONGITUDE)
    @property
    def native_value(self): return self._data.get("longitude")

class BoatSpeedSensor(_Base):
    _attr_name = "Speed"
    _attr_icon = "mdi:speedometer"
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "km/h"
    def __init__(self, c, e): super().__init__(c, e, ENTITY_SPEED)
    @property
    def native_value(self): return self._data.get("speed_kmh")

class BoatGpsFixSensor(_Base):
    _attr_name = "GPS Fix"
    _attr_icon = "mdi:crosshairs-gps"
    def __init__(self, c, e): super().__init__(c, e, ENTITY_FIX)
    @property
    def native_value(self):
        return "Fixed" if self._data.get("fix") == 1 else "No Fix"

# ── Derived ──────────────────────────────────────────────────────────────────

class BoatLastMovedSensor(_Base):
    _attr_name = "Last Moved"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    def __init__(self, c, e): super().__init__(c, e, ENTITY_LAST_MOVED)
    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_moved_utc

class BoatStationaryHoursSensor(_Base):
    _attr_name = "Hours Stationary"
    _attr_icon = "mdi:timer-sand"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "h"
    _attr_suggested_display_precision = 1
    def __init__(self, c, e): super().__init__(c, e, ENTITY_STATIONARY_HOURS)
    @property
    def native_value(self) -> float | None:
        lm = self.coordinator.last_moved_utc
        if lm is None: return None
        return round((datetime.now(timezone.utc) - lm).total_seconds() / 3600, 1)

class BoatStationaryDaysSensor(_Base):
    _attr_name = "Days Stationary"
    _attr_icon = "mdi:calendar-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"
    _attr_suggested_display_precision = 2
    def __init__(self, c, e): super().__init__(c, e, ENTITY_STATIONARY_DAYS)
    @property
    def native_value(self) -> float | None:
        lm = self.coordinator.last_moved_utc
        if lm is None: return None
        return round((datetime.now(timezone.utc) - lm).total_seconds() / 86400, 2)

class BoatDaysRemainingSensor(_Base):
    _attr_name = "Days Until Must Move"
    _attr_icon = "mdi:calendar-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"
    _attr_suggested_display_precision = 1
    def __init__(self, c, e): super().__init__(c, e, ENTITY_DAYS_REMAINING)
    @property
    def native_value(self) -> float | None:
        lm = self.coordinator.last_moved_utc
        if lm is None: return None
        threshold = self._cfg("reminder_days", 14)
        elapsed = (datetime.now(timezone.utc) - lm).total_seconds() / 86400
        return round(max(threshold - elapsed, 0), 1)

class BoatMooringStatusSensor(_Base):
    _attr_name = "Mooring Status"
    def __init__(self, c, e): super().__init__(c, e, ENTITY_STATUS)

    @property
    def native_value(self) -> str:
        if self._data.get("fix") != 1: return STATUS_NO_FIX
        lm = self.coordinator.last_moved_utc
        if lm is None: return STATUS_NO_FIX
        days = (datetime.now(timezone.utc) - lm).total_seconds() / 86400
        reminder = self._cfg("reminder_days", 14)
        warning  = self._cfg()
        if days >= reminder: return STATUS_ALERT
        if days >= warning:  return STATUS_WARN
        return STATUS_OK

    @property
    def icon(self) -> str:
        return {
            STATUS_OK:     "mdi:check-circle",
            STATUS_WARN:   "mdi:alert",
            STATUS_ALERT:  "mdi:alert-circle",
            STATUS_NO_FIX: "mdi:crosshairs-question",
        }.get(self.native_value, "mdi:ferry")
