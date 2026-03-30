"""CC Movement Monitor — Config Flow & Options Flow."""
from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_BOAT_NAME,
    DOMAIN,
    CONF_CERBO_HOST, CONF_MODBUS_SLAVE,
    CONF_REMINDER_DAYS, CONF_WARNING_DAYS,
    CONF_NOTIFIER,
    CONF_SMTP_SERVER, CONF_SMTP_PORT, CONF_SMTP_USER, CONF_SMTP_PASSWORD, CONF_SMTP_RECIPIENT,
    CONF_NOTIFY_PUSH, CONF_NOTIFY_PERSISTENT, CONF_NOTIFY_EMAIL,
    DEFAULT_REMINDER_DAYS, DEFAULT_WARNING_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Three-step setup wizard: connection → thresholds → notifications."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    # Step 1 ── Cerbo GX connection ──────────────────────────────────────────

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host  = user_input[CONF_CERBO_HOST].strip()
            slave = user_input[CONF_MODBUS_SLAVE]
            ok, err = await self._test_modbus(host, slave)
            if ok:
                self._data.update(user_input)
                return await self.async_step_thresholds()
            errors["base"] = err

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BOAT_NAME, default="My Boat"): str,
                vol.Required(CONF_CERBO_HOST): str,
                vol.Required(CONF_MODBUS_SLAVE, default=100):
                    vol.All(int, vol.Range(min=1, max=247)),
            }),
            errors=errors,
        )

    # Step 2 ── Thresholds ───────────────────────────────────────────────────

    async def async_step_thresholds(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_notifications()

        return self.async_show_form(
            step_id="thresholds",
            data_schema=vol.Schema({
                vol.Required(CONF_REMINDER_DAYS, default=DEFAULT_REMINDER_DAYS):
                    vol.All(int, vol.Range(min=1, max=28)),
                vol.Required(CONF_WARNING_DAYS, default=DEFAULT_WARNING_DAYS):
                    vol.All(int, vol.Range(min=1, max=27)),
            }),
        )

    # Step 3 ── Notifications ────────────────────────────────────────────────

    async def async_step_notifications(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_NOTIFY_EMAIL) and not user_input.get(CONF_SMTP_RECIPIENT):
                errors[CONF_SMTP_RECIPIENT] = "recipient_required"
            if user_input.get(CONF_NOTIFY_EMAIL) and not user_input.get(CONF_SMTP_SERVER):
                errors[CONF_SMTP_SERVER] = "smtp_required"
            if user_input.get(CONF_NOTIFY_PUSH) and not user_input.get(CONF_NOTIFIER, "").strip():
                errors[CONF_NOTIFIER] = "notifier_required"

            if not errors:
                self._data.update(user_input)
                await self.async_set_unique_id(f"cc_movement_monitor_{self._data[CONF_CERBO_HOST]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="CC Movement Monitor", data=self._data)

        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema({
                vol.Required(CONF_NOTIFY_PUSH,       default=True):  bool,
                vol.Optional(CONF_NOTIFIER,          default=""):    str,
                vol.Required(CONF_NOTIFY_PERSISTENT, default=True):  bool,
                vol.Required(CONF_NOTIFY_EMAIL,      default=False): bool,
                vol.Optional(CONF_SMTP_SERVER,       default="smtp.gmail.com"): str,
                vol.Optional(CONF_SMTP_PORT,         default=587):   int,
                vol.Optional(CONF_SMTP_USER,         default=""):    str,
                vol.Optional(CONF_SMTP_PASSWORD,     default=""):    str,
                vol.Optional(CONF_SMTP_RECIPIENT,    default=""):    str,
            }),
            errors=errors,
        )

    # Modbus connection test ──────────────────────────────────────────────────

    async def _test_modbus(self, host: str, slave: int):
        def _test():
            from pymodbus.client import ModbusTcpClient
            c = ModbusTcpClient(host, port=502, timeout=5)
            try:
                if not c.connect():
                    return False, "cannot_connect"
                r = c.read_holding_registers(2806, count=1, slave=slave)
                return (False, "modbus_error") if r.isError() else (True, "")
            except Exception:
                return False, "cannot_connect"
            finally:
                c.close()
        return await self.hass.async_add_executor_job(_test)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Reconfigure thresholds and notifications after initial setup."""

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_NOTIFY_EMAIL) and not user_input.get(CONF_SMTP_RECIPIENT, "").strip():
                errors[CONF_SMTP_RECIPIENT] = "recipient_required"
            if user_input.get(CONF_NOTIFY_PUSH) and not user_input.get(CONF_NOTIFIER, "").strip():
                errors[CONF_NOTIFIER] = "notifier_required"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        cfg = {**self._entry.data, **self._entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_REMINDER_DAYS,
                    default=cfg.get(CONF_REMINDER_DAYS, DEFAULT_REMINDER_DAYS)):
                    vol.All(int, vol.Range(min=1, max=28)),
                vol.Required(CONF_WARNING_DAYS,
                    default=cfg.get(CONF_WARNING_DAYS, DEFAULT_WARNING_DAYS)):
                    vol.All(int, vol.Range(min=1, max=27)),
                vol.Required(CONF_NOTIFY_PUSH,
                    default=cfg.get(CONF_NOTIFY_PUSH, True)): bool,
                vol.Optional(CONF_NOTIFIER,
                    default=cfg.get(CONF_NOTIFIER, "")): str,
                vol.Required(CONF_NOTIFY_PERSISTENT,
                    default=cfg.get(CONF_NOTIFY_PERSISTENT, True)): bool,
                vol.Required(CONF_NOTIFY_EMAIL,
                    default=cfg.get(CONF_NOTIFY_EMAIL, False)): bool,
                vol.Optional(CONF_SMTP_SERVER,
                    default=cfg.get(CONF_SMTP_SERVER, "smtp.gmail.com")): str,
                vol.Optional(CONF_SMTP_PORT,
                    default=cfg.get(CONF_SMTP_PORT, 587)): int,
                vol.Optional(CONF_SMTP_USER,
                    default=cfg.get(CONF_SMTP_USER, "")): str,
                vol.Optional(CONF_SMTP_PASSWORD,
                    default=cfg.get(CONF_SMTP_PASSWORD, "")): str,
                vol.Optional(CONF_SMTP_RECIPIENT,
                    default=cfg.get(CONF_SMTP_RECIPIENT, "")): str,
            }),
            errors=errors,
        )
