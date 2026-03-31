"""CC Movement Monitor — Number (slider) Entities."""
from __future__ import annotations
import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import BoatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                             async_add_entities: AddEntitiesCallback) -> None:
    coordinator: BoatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BoatReminderDaysNumber(coordinator, entry),
        BoatWarningDaysNumber(coordinator, entry),
    ])


class _BoatNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(self, coordinator: BoatCoordinator, entry: ConfigEntry,
                 unique_suffix: str, conf_key: str, default: int,
                 min_val: int, max_val: int) -> None:
        self._coordinator = coordinator
        self._entry       = entry
        self._conf_key    = conf_key
        self._attr_unique_id    = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info  = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_unit_of_measurement = "days"
        self._val = float(entry.options.get(conf_key, entry.data.get(conf_key, default)))

    @property
    def native_value(self) -> float:
        return self._val

    async def async_set_native_value(self, value: float) -> None:
        self._val = value
        opts = dict(self._entry.options)
        opts[self._conf_key] = int(value)
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        # Always read from config entry — it's the authoritative source
        self._val = float(self._entry.options.get(
            self._conf_key, self._entry.data.get(self._conf_key, self._val)
        ))


class BoatReminderDaysNumber(_BoatNumber):
    _attr_name = "Move Reminder Days"
    _attr_icon = "mdi:calendar-check"
    def __init__(self, c, e):
        super().__init__(c, e, "reminder_days", "reminder_days", 14, 1, 28)

class BoatWarningDaysNumber(_BoatNumber):
    _attr_name = "Early Warning Days"
    _attr_icon = "mdi:calendar-alert"
    def __init__(self, c, e):
        super().__init__(c, e, "warning_days", "warning_days", 10, 1, 27)
