"""CC Movement Monitor — DataUpdateCoordinator."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, MOVEMENT_THRESHOLD_M,
    REG_LATITUDE, REG_LONGITUDE, REG_SPEED, REG_FIX,
    STORE_LAST_MOVED, STORE_LAST_LAT, STORE_LAST_LON,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.position"


class BoatCoordinator(DataUpdateCoordinator):
    """Polls Cerbo GX Modbus for GPS data and tracks boat movement."""

    def __init__(self, hass: HomeAssistant, cerbo_host: str, modbus_slave: int) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._host  = cerbo_host
        self._slave = modbus_slave
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

        self.last_moved_utc: datetime | None = None
        self.last_lat: float | None = None
        self.last_lon: float | None = None
        self._store_loaded = False

    # ── Persistent storage ────────────────────────────────────────────────────

    async def _load_store(self) -> None:
        data = await self._store.async_load()
        if data:
            raw_dt = data.get(STORE_LAST_MOVED)
            if raw_dt:
                try:
                    self.last_moved_utc = datetime.fromisoformat(raw_dt)
                except ValueError:
                    pass
            self.last_lat = data.get(STORE_LAST_LAT)
            self.last_lon = data.get(STORE_LAST_LON)
        self._store_loaded = True
        _LOGGER.debug("Loaded stored position: lat=%s lon=%s last_moved=%s",
                      self.last_lat, self.last_lon, self.last_moved_utc)

    async def _save_store(self) -> None:
        await self._store.async_save({
            STORE_LAST_MOVED: self.last_moved_utc.isoformat() if self.last_moved_utc else None,
            STORE_LAST_LAT:   self.last_lat,
            STORE_LAST_LON:   self.last_lon,
        })

    # ── Modbus ────────────────────────────────────────────────────────────────

    async def _async_read_modbus(self) -> dict[str, Any]:
        """Async Modbus read using AsyncModbusTcpClient."""
        from pymodbus.client import AsyncModbusTcpClient
        from pymodbus.exceptions import ModbusException, ConnectionException

        client = AsyncModbusTcpClient(self._host, port=502, timeout=5)
        try:
            await client.connect()
            if not client.connected:
                raise UpdateFailed(f"Cannot connect to Cerbo GX at {self._host}:502")

            async def read_int32(addr: int) -> int:
                r = await client.read_holding_registers(addr, count=2, device_id=self._slave)
                if r.isError():
                    raise UpdateFailed(f"Modbus error at register {addr}")
                hi, lo = r.registers
                raw = (hi << 16) | lo
                return raw - 0x100000000 if raw >= 0x80000000 else raw

            async def read_uint16(addr: int) -> int:
                r = await client.read_holding_registers(addr, count=1, device_id=self._slave)
                if r.isError():
                    raise UpdateFailed(f"Modbus error at register {addr}")
                return r.registers[0]

            return {
                "latitude":  (await read_int32(REG_LATITUDE))  * 1e-7,
                "longitude": (await read_int32(REG_LONGITUDE)) * 1e-7,
                "speed_ms":  (await read_uint16(REG_SPEED))    * 0.01,
                "fix":        await read_uint16(REG_FIX),
            }
        except ConnectionException as exc:
            raise UpdateFailed(f"Cannot connect to Cerbo GX at {self._host}:502: {exc}") from exc
        except ModbusException as exc:
            raise UpdateFailed(f"Modbus error: {exc}") from exc
        finally:
            client.close()

    # ── Haversine ─────────────────────────────────────────────────────────────

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a  = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ── Main update loop ──────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        if not self._store_loaded:
            await self._load_store()

        raw = await self._async_read_modbus()
        lat, lon = raw["latitude"], raw["longitude"]
        fix       = raw["fix"]
        speed_kmh = raw["speed_ms"] * 3.6
        moved     = False

        if fix == 1:
            if self.last_lat is not None and self.last_lon is not None:
                dist = self._haversine_m(self.last_lat, self.last_lon, lat, lon)
                _LOGGER.debug("Distance from last position: %.1fm", dist)
                if dist >= MOVEMENT_THRESHOLD_M:
                    moved = True
                    _LOGGER.info("Boat moved %.1fm — updating timestamp", dist)
            else:
                moved = True  # first fix ever
                _LOGGER.info("First GPS fix — seeding position store")

            if moved:
                self.last_lat       = lat
                self.last_lon       = lon
                self.last_moved_utc = datetime.now(timezone.utc)
                await self._save_store()

        return {
            "latitude":          lat,
            "longitude":         lon,
            "speed_kmh":         round(speed_kmh, 2),
            "fix":               fix,
            "last_moved_utc":    self.last_moved_utc,
            "moved_this_update": moved,
        }
