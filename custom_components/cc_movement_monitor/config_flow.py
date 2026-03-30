"""CC Movement Monitor — Config Flow."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step 1 — boat name and Cerbo GX connection details."""
        errors = {}

        if user_input is not None:
            # Coerce selector float values to int
            user_input["modbus_slave"]  = int(user_input["modbus_slave"])
            user_input["reminder_days"] = int(user_input["reminder_days"])
            user_input["warning_days"]  = int(user_input["warning_days"])

            host       = user_input["cerbo_host"].strip()
            slave      = user_input["modbus_slave"]
            skip_test  = user_input.pop("skip_connection_test", False)

            proceed = True
            if not skip_test:
                ok, err = await self._test_modbus(host, slave)
                if not ok:
                    proceed = False
                    errors["base"] = err

            if proceed:
                await self.async_set_unique_id(f"cc_movement_monitor_{host}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get("boat_name", "My Boat"),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("boat_name", default="My Boat"): str,
                vol.Required("cerbo_host"): str,
                vol.Required("modbus_slave", default=100): NumberSelector(
                    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required("reminder_days", default=14): NumberSelector(
                    NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required("warning_days", default=10): NumberSelector(
                    NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required("notify_push", default=True): bool,
                vol.Optional("notifier", default=""): str,
                vol.Required("notify_persistent", default=True): bool,
                vol.Required("notify_email", default=False): bool,
                vol.Optional("smtp_server", default="smtp.gmail.com"): str,
                vol.Optional("smtp_port", default=587): int,
                vol.Optional("smtp_user", default=""): str,
                vol.Optional("smtp_password", default=""): str,
                vol.Optional("smtp_recipient", default=""): str,
                vol.Required("skip_connection_test", default=False): bool,
            }),
            errors=errors,
        )

    async def _test_modbus(self, host: str, slave: int):
        """Try connecting to the Cerbo GX and reading one register."""
        def _test():
            try:
                from pymodbus.client import ModbusTcpClient
                c = ModbusTcpClient(host, port=502, timeout=5)
                if not c.connect():
                    return False, "cannot_connect"
                r = c.read_holding_registers(2806, count=1, slave=slave)
                c.close()
                return (False, "modbus_error") if r.isError() else (True, "")
            except Exception:  # noqa: BLE001
                return False, "cannot_connect"
        return await self.hass.async_add_executor_job(_test)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow."""
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options (reconfigure after setup)."""

    async def async_step_init(self, user_input=None):
        """Show options form."""
        if user_input is not None:
            user_input["reminder_days"] = int(user_input["reminder_days"])
            user_input["warning_days"]  = int(user_input["warning_days"])
            return self.async_create_entry(title="", data=user_input)

        cfg = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("reminder_days",
                    default=cfg.get("reminder_days", 14)): NumberSelector(
                    NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required("warning_days",
                    default=cfg.get("warning_days", 10)): NumberSelector(
                    NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required("notify_push",
                    default=cfg.get("notify_push", True)): bool,
                vol.Optional("notifier",
                    default=cfg.get("notifier", "")): str,
                vol.Required("notify_persistent",
                    default=cfg.get("notify_persistent", True)): bool,
                vol.Required("notify_email",
                    default=cfg.get("notify_email", False)): bool,
                vol.Optional("smtp_server",
                    default=cfg.get("smtp_server", "smtp.gmail.com")): str,
                vol.Optional("smtp_port",
                    default=cfg.get("smtp_port", 587)): int,
                vol.Optional("smtp_user",
                    default=cfg.get("smtp_user", "")): str,
                vol.Optional("smtp_password",
                    default=cfg.get("smtp_password", "")): str,
                vol.Optional("smtp_recipient",
                    default=cfg.get("smtp_recipient", "")): str,
            }),
        )
