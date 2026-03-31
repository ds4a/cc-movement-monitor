"""CC Movement Monitor — Home Assistant Integration."""
from __future__ import annotations

import logging
import pathlib
from datetime import datetime, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN
from .coordinator import BoatCoordinator
from .notify import async_send_notifications, async_dismiss_notifications

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH]

PANEL_URL  = "cc-movement-monitor"
PANEL_PATH = pathlib.Path(__file__).parent / "panel.html"

_last_warning_sent:   dict[str, datetime] = {}
_last_must_move_sent: dict[str, datetime] = {}
_was_moved_last:      dict[str, bool]     = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = BoatCoordinator(
        hass,
        cerbo_host=entry.data["cerbo_host"],
        modbus_slave=entry.data.get("modbus_slave", 100),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: hass.async_create_task(
                _async_check_and_notify(hass, entry, coordinator)
            )
        )
    )

    # ── Register static panel file ────────────────────────────────────────────
    # Serves panel.html at /cc_movement_monitor_panel/index.html
    # The panel is registered once globally — guard against multiple entries
    if not hass.data[DOMAIN].get("_panel_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path=f"/{DOMAIN}_panel",
                path=str(PANEL_PATH.parent),
                cache_headers=False,
            )
        ])
        _boat_name = entry.data.get("boat_name", "Boat")
        hass.components.frontend.async_register_built_in_panel(
            component_name="iframe",
            sidebar_title=f"{_boat_name} Monitor",
            sidebar_icon="mdi:ferry",
            frontend_url_path=PANEL_URL,
            config={"url": f"/{DOMAIN}_panel/panel.html?boat={_boat_name}"},
            require_admin=False,
        )
        hass.data[DOMAIN]["_panel_registered"] = True
        _LOGGER.info("CC Movement Monitor panel registered at /%s", PANEL_URL)

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    _LOGGER.info("CC Movement Monitor set up for %s", entry.data["cerbo_host"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        for store in (_last_warning_sent, _last_must_move_sent, _was_moved_last):
            store.pop(entry.entry_id, None)
    return unloaded


async def _async_reload_on_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_check_and_notify(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BoatCoordinator,
) -> None:
    data = coordinator.data
    if not data:
        return

    eid = entry.entry_id
    cfg = {**entry.data, **entry.options}

    boat_name     = cfg.get("boat_name", "Boat")
    reminder_days = int(cfg.get("reminder_days", 14))
    warning_days  = int(cfg.get("warning_days", 10))
    fix           = data.get("fix", 0)
    lat           = data.get("latitude")
    lon           = data.get("longitude")
    moved_now     = data.get("moved_this_update", False)
    last_moved    = coordinator.last_moved_utc
    now           = datetime.now(timezone.utc)

    if moved_now and not _was_moved_last.get(eid, False):
        _LOGGER.info("Boat is moving — clearing all reminders")
        await async_dismiss_notifications(
            hass, cfg, ["boat_early_warning", "boat_must_move"])
        _last_warning_sent.pop(eid, None)
        _last_must_move_sent.pop(eid, None)

    _was_moved_last[eid] = moved_now

    if fix != 1 or last_moved is None:
        return

    days_stationary = (now - last_moved).total_seconds() / 86400
    days_remaining  = max(reminder_days - days_stationary, 0)

    if days_stationary >= reminder_days:
        last = _last_must_move_sent.get(eid)
        if last is None or (now - last).total_seconds() > 43200:
            await async_send_notifications(
                hass, cfg,
                title=f"🚨 {boat_name} — YOU MUST MOVE",
                message=(
                    f"{boat_name} has been stationary for {days_stationary:.1f} days — "
                    f"your {reminder_days}-day CRT mooring limit has been reached."
                ),
                notification_id="boat_must_move",
                is_critical=True, lat=lat, lon=lon,
            )
            _last_must_move_sent[eid] = now
        return

    if days_stationary >= warning_days:
        last = _last_warning_sent.get(eid)
        if last is None or (now - last).total_seconds() > 86400:
            await async_send_notifications(
                hass, cfg,
                title=f"⚓ {boat_name} — Plan Your Move",
                message=(
                    f"{boat_name} has been moored for {days_stationary:.1f} days. "
                    f"Approximately {days_remaining:.1f} days remaining before "
                    f"your {reminder_days}-day mooring limit."
                ),
                notification_id="boat_early_warning",
                is_critical=False, lat=lat, lon=lon,
            )
            _last_warning_sent[eid] = now
