"""CC Movement Monitor — Switch (notification toggle) Entities."""
from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN
from .coordinator import BoatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                             async_add_entities: AddEntitiesCallback) -> None:
    coordinator: BoatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BoatPushSwitch(coordinator, entry),
        BoatPersistentSwitch(coordinator, entry),
        BoatEmailSwitch(coordinator, entry),
    ])


class _BoatSwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BoatCoordinator, entry: ConfigEntry,
                 unique_suffix: str, conf_key: str, default: bool) -> None:
        self._coordinator = coordinator
        self._entry       = entry
        self._conf_key    = conf_key
        self._attr_unique_id   = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._is_on = bool(entry.options.get(conf_key, entry.data.get(conf_key, default)))

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        self._is_on = True; self._persist(); self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._is_on = False; self._persist(); self.async_write_ha_state()

    def _persist(self) -> None:
        opts = dict(self._entry.options)
        opts[self._conf_key] = self._is_on
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state not in ("unknown", "unavailable"):
            self._is_on = state.state == "on"


class BoatPushSwitch(_BoatSwitch):
    _attr_name = "Push Notifications"
    _attr_icon = "mdi:bell-alert"
    def __init__(self, c, e): super().__init__(c, e, "notify_push", "notify_push", True)

class BoatPersistentSwitch(_BoatSwitch):
    _attr_name = "Dashboard Alerts"
    _attr_icon = "mdi:monitor-dashboard"
    def __init__(self, c, e): super().__init__(c, e, "notify_persistent", "notify_persistent", True)

class BoatEmailSwitch(_BoatSwitch):
    _attr_name = "Email Alerts"
    _attr_icon = "mdi:email-alert"
    def __init__(self, c, e): super().__init__(c, e, "notify_email", "notify_email", False)
