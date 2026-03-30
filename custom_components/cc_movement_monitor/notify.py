"""CC Movement Monitor — Notification helper."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

_LOGGER = logging.getLogger(__name__)


async def async_send_notifications(
    hass, cfg, title, message, notification_id,
    is_critical=False, lat=None, lon=None,
):
    maps_url = f"https://maps.google.com/?q={lat},{lon}" if lat and lon else ""

    if cfg.get("notify_push") and cfg.get("notifier", "").strip():
        notifier = cfg["notifier"].strip().replace("notify.", "")
        data = {
            "title": title, "message": message,
            "data": {"tag": notification_id, "group": "cc_movement_monitor",
                     "url": "/lovelace/cc-movement-monitor", "notification_icon": "mdi:ferry"},
        }
        if is_critical:
            data["data"]["push"] = {"sound": {"name": "default", "critical": 1, "volume": 1.0}}
            data["data"]["importance"] = "high"
        try:
            await hass.services.async_call("notify", notifier, data, blocking=False)
        except Exception as exc:
            _LOGGER.warning("Push failed: %s", exc)

    if cfg.get("notify_persistent"):
        msg = message + (f"\n\n[View on map]({maps_url})" if maps_url else "")
        try:
            await hass.services.async_call(
                "persistent_notification", "create",
                {"notification_id": notification_id, "title": title, "message": msg},
                blocking=False,
            )
        except Exception as exc:
            _LOGGER.warning("Persistent notification failed: %s", exc)

    if cfg.get("notify_email") and cfg.get("smtp_recipient", "").strip():
        body = message
        if maps_url:
            body += f"\n\nCurrent position: {maps_url}"
        body += "\n\n— CC Movement Monitor"
        await hass.async_add_executor_job(
            _send_email_sync,
            cfg.get("smtp_server", ""),
            cfg.get("smtp_port", 587),
            cfg.get("smtp_user", ""),
            cfg.get("smtp_password", ""),
            cfg["smtp_recipient"],
            title,
            body,
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
            s.ehlo()
            s.starttls(context=ctx)
            if user and password:
                s.login(user, password)
            s.send_message(msg)
        _LOGGER.info("Email sent to %s", recipient)
    except Exception as exc:
        _LOGGER.error("Email failed: %s", exc)


async def async_dismiss_notifications(hass, cfg, notification_ids):
    for nid in notification_ids:
        try:
            await hass.services.async_call(
                "persistent_notification", "dismiss",
                {"notification_id": nid}, blocking=False)
        except Exception:
            pass
    if cfg.get("notify_push") and cfg.get("notifier", "").strip():
        notifier = cfg["notifier"].strip().replace("notify.", "")
        for nid in notification_ids:
            try:
                await hass.services.async_call(
                    "notify", notifier,
                    {"message": "clear_notification", "data": {"tag": nid}},
                    blocking=False)
            except Exception:
                pass
