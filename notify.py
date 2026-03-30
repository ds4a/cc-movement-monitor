"""CC Movement Monitor — Notification helper (push / persistent / SMTP)."""
from __future__ import annotations
import logging, smtplib, ssl
from email.message import EmailMessage
from typing import Any
from homeassistant.core import HomeAssistant
from .const import (
    CONF_NOTIFIER, CONF_NOTIFY_EMAIL, CONF_NOTIFY_PERSISTENT, CONF_NOTIFY_PUSH,
    CONF_SMTP_PASSWORD, CONF_SMTP_PORT, CONF_SMTP_RECIPIENT, CONF_SMTP_SERVER, CONF_SMTP_USER,
)

_LOGGER = logging.getLogger(__name__)


async def async_send_notifications(
    hass: HomeAssistant, cfg: dict[str, Any],
    title: str, message: str, notification_id: str,
    is_critical: bool = False,
    lat: float | None = None, lon: float | None = None,
) -> None:
    maps_url = f"https://maps.google.com/?q={lat},{lon}" if lat and lon else ""

    # ── Push ──────────────────────────────────────────────────────────────────
    if cfg.get(CONF_NOTIFY_PUSH) and cfg.get(CONF_NOTIFIER, "").strip():
        notifier = cfg[CONF_NOTIFIER].strip().replace("notify.", "")
        data: dict[str, Any] = {
            "title": title, "message": message,
            "data": {"tag": notification_id, "group": "cc_movement_monitor",
                     "url": "/lovelace/cc-movement-monitor", "notification_icon": "mdi:ferry"},
        }
        if is_critical:
            data["data"]["push"] = {"sound": {"name": "default", "critical": 1, "volume": 1.0}}
            data["data"]["importance"] = "high"
        try:
            await hass.services.async_call("notify", notifier, data, blocking=False)
            _LOGGER.info("Push sent via notify.%s", notifier)
        except Exception as exc:
            _LOGGER.warning("Push failed: %s", exc)

    # ── Persistent ────────────────────────────────────────────────────────────
    if cfg.get(CONF_NOTIFY_PERSISTENT):
        msg = message + (f"\n\n[View on map]({maps_url})" if maps_url else "")
        try:
            await hass.services.async_call(
                "persistent_notification", "create",
                {"notification_id": notification_id, "title": title, "message": msg},
                blocking=False,
            )
        except Exception as exc:
            _LOGGER.warning("Persistent notification failed: %s", exc)

    # ── Email ─────────────────────────────────────────────────────────────────
    if cfg.get(CONF_NOTIFY_EMAIL) and cfg.get(CONF_SMTP_RECIPIENT, "").strip():
        body = message
        if maps_url:
            body += f"\n\nCurrent position: {maps_url}"
        body += "\n\n— CC Movement Monitoring System"
        await hass.async_add_executor_job(
            _send_email_sync,
            cfg.get(CONF_SMTP_SERVER, ""), cfg.get(CONF_SMTP_PORT, 587),
            cfg.get(CONF_SMTP_USER, ""), cfg.get(CONF_SMTP_PASSWORD, ""),
            cfg[CONF_SMTP_RECIPIENT], title, body,
        )


def _send_email_sync(server, port, user, password, recipient, subject, body):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"]    = user
        msg["To"]      = recipient
        msg.set_content(body)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(server, port, timeout=15) as s:
            s.ehlo(); s.starttls(context=ctx)
            if user and password:
                s.login(user, password)
            s.send_message(msg)
        _LOGGER.info("Email sent to %s", recipient)
    except Exception as exc:
        _LOGGER.error("Email failed: %s", exc)


async def async_dismiss_notifications(
    hass: HomeAssistant, cfg: dict[str, Any], notification_ids: list[str],
) -> None:
    for nid in notification_ids:
        try:
            await hass.services.async_call(
                "persistent_notification", "dismiss", {"notification_id": nid}, blocking=False)
        except Exception:
            pass
    if cfg.get(CONF_NOTIFY_PUSH) and cfg.get(CONF_NOTIFIER, "").strip():
        notifier = cfg[CONF_NOTIFIER].strip().replace("notify.", "")
        for nid in notification_ids:
            try:
                await hass.services.async_call(
                    "notify", notifier,
                    {"message": "clear_notification", "data": {"tag": nid}},
                    blocking=False)
            except Exception:
                pass
