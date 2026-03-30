"""
CC Movement Monitor — Home Assistant Integration
============================================
Tracks narrowboat's GPS position via Victron Cerbo GX Modbus TCP
and sends move reminders when she's been stationary too long.

On setup:
  1. Coordinator polls Cerbo GX Modbus every 60 s
  2. Sensor / number / switch entities registered
  3. Notification logic runs after every coordinator update
  4. Lovelace dashboard created
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_BOAT_NAME,
    DOMAIN, CONF_CERBO_HOST, CONF_MODBUS_SLAVE,
    CONF_REMINDER_DAYS, CONF_WARNING_DAYS,
    DEFAULT_REMINDER_DAYS, DEFAULT_WARNING_DAYS,
)
from .coordinator import BoatCoordinator
from .notify import async_send_notifications, async_dismiss_notifications

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH]

# Per-entry throttle state
_last_warning_sent:   dict[str, datetime] = {}
_last_must_move_sent: dict[str, datetime] = {}
_was_moved_last:      dict[str, bool]     = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = BoatCoordinator(
        hass,
        cerbo_host=entry.data[CONF_CERBO_HOST],
        modbus_slave=entry.data.get(CONF_MODBUS_SLAVE, 100),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Wire the notification logic to every coordinator update
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: hass.async_create_task(
                _async_check_and_notify(hass, entry, coordinator)
            )
        )
    )

    # Auto-create the Lovelace dashboard (best-effort, non-fatal)
    hass.async_create_task(_async_create_dashboard(hass, entry))

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    _LOGGER.info("CC Movement Monitor set up for %s", entry.data[CONF_CERBO_HOST])
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


# ── Notification logic ────────────────────────────────────────────────────────

async def _async_check_and_notify(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BoatCoordinator,
) -> None:
    data = coordinator.data
    if not data:
        return

    eid = entry.entry_id
    cfg = {**entry.data, **entry.options}
    boat_name = cfg.get(CONF_BOAT_NAME, "Boat")
    reminder_days = cfg.get(CONF_REMINDER_DAYS, DEFAULT_REMINDER_DAYS)
    warning_days  = cfg.get(CONF_WARNING_DAYS,  DEFAULT_WARNING_DAYS)

    fix              = data.get("fix", 0)
    lat, lon         = data.get("latitude"), data.get("longitude")
    moved_now        = data.get("moved_this_update", False)
    last_moved       = coordinator.last_moved_utc
    prev_moved       = _was_moved_last.get(eid, False)
    now              = datetime.now(timezone.utc)

    # Dismiss alerts when the boat moves
    if moved_now and not prev_moved:
        _LOGGER.info("The boat is moving — clearing all reminders")
        await async_dismiss_notifications(
            hass, cfg, ["boat_early_warning", "boat_must_move"])
        _last_warning_sent.pop(eid, None)
        _last_must_move_sent.pop(eid, None)

    _was_moved_last[eid] = moved_now

    if fix != 1 or last_moved is None:
        return

    days_stationary = (now - last_moved).total_seconds() / 86400
    days_remaining  = max(reminder_days - days_stationary, 0)

    # Must-move (every 12 h)
    if days_stationary >= reminder_days:
        last = _last_must_move_sent.get(eid)
        if last is None or (now - last).total_seconds() > 43200:
            await async_send_notifications(
                hass, cfg,
                title=f"🚨 {boat_name} — YOU MUST MOVE",
                message=(
                    f"The boat has been stationary for {days_stationary:.1f} days — "
                    f"your {reminder_days}-day CRT mooring limit has been reached."
                ),
                notification_id="boat_must_move",
                is_critical=True, lat=lat, lon=lon,
            )
            _last_must_move_sent[eid] = now
        return  # don't also send early warning

    # Early warning (every 24 h)
    if days_stationary >= warning_days:
        last = _last_warning_sent.get(eid)
        if last is None or (now - last).total_seconds() > 86400:
            await async_send_notifications(
                hass, cfg,
                title=f"⚓ {boat_name} — Plan Your Move",
                message=(
                    f"The boat has been moored for {days_stationary:.1f} days. "
                    f"Approximately {days_remaining:.1f} days remaining before "
                    f"your {reminder_days}-day mooring limit."
                ),
                notification_id="boat_early_warning",
                is_critical=False, lat=lat, lon=lon,
            )
            _last_warning_sent[eid] = now


# ── Lovelace dashboard (best-effort) ─────────────────────────────────────────

async def _async_create_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Attempt to register a CC Movement Monitor Lovelace dashboard.
    This uses an internal HA API that may vary between releases,
    so failures are caught and logged as warnings rather than errors.
    """
    try:
        from homeassistant.components.lovelace import _get_storage_collection  # type: ignore[attr-defined]

        url_path = "cc-movement-monitor"
        storage = await _get_storage_collection(hass)

        # Don't overwrite if it already exists
        existing = {d["url_path"] for d in await storage.async_get_info()}
        if url_path in existing:
            _LOGGER.debug("CC Movement Monitor dashboard already exists")
            return

        await storage.async_create_item({
            "url_path":       url_path,
            "title":          the boat,
            "icon":           "mdi:ferry",
            "show_in_sidebar": True,
            "require_admin":   False,
            "mode":           "storage",
        })
        _LOGGER.info("CC Movement Monitor dashboard created at /lovelace/%s", url_path)

    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning(
            "Could not auto-create Lovelace dashboard (%s). "
            "You can add it manually — see README for the YAML.",
            exc,
        )
