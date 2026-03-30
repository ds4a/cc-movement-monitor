# ⚓ CC Movement Monitor

A Home Assistant custom integration that tracks narrowboat's GPS position
via the Victron Cerbo GX Modbus TCP interface, and sends automatic move reminders
when she has been stationary longer than your configured threshold.

---

## Features

- 📍 **Live GPS** — polls Cerbo GX Modbus TCP every 60 seconds (no MQTT bridge, no Python scripts)
- 📅 **Stationary timer** — hours and days since the boat last moved, persisted across HA restarts
- 🔔 **Smart notifications** — early warning (every 24 h) + urgent must-move (every 12 h)
- 📱 **Three channels** — iOS/Android push with Critical Alert, HA dashboard, SMTP email
- 🎚️ **Live threshold sliders** — adjust via the dashboard, no config editing needed
- 🗺️ **Lovelace dashboard** — auto-created on first install
- 🛰️ **GPS-fix aware** — status shows "No GPS Fix" when the aerial has no lock

---

## Requirements

- Home Assistant 2024.1.0+
- HACS installed
- Victron Cerbo GX with **Modbus TCP enabled**
  (Cerbo GX → Settings → Services → Modbus TCP → Enable)
- GPS receiver connected to the Cerbo GX

---

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ menu → **Custom repositories**
2. URL: `https://github.com/ds4a/cc-movement-monitor`  Category: **Integration**
3. Click **Download**
4. Restart Home Assistant
5. Settings → Devices & Services → **Add Integration** → search **CC Movement Monitor**

### Manual

Copy `custom_components/cc_movement_monitor/` into `config/custom_components/` and restart.

---

## Setup Wizard

### Step 1 — Cerbo GX Connection

| Field | Notes |
|---|---|
| Cerbo GX IP Address | e.g. `192.168.1.100` |
| Modbus Slave / Unit ID | Usually `100` — verify on Cerbo → Settings → Services → Modbus TCP → Available services |

The wizard tests the connection and reads register 2806 (GPS fix) before continuing.

### Step 2 — Mooring Thresholds

| Field | Default | Notes |
|---|---|---|
| Must Move After | 14 days | CRT continuous cruising standard |
| Early Warning At | 10 days | Heads-up 4 days before deadline |

### Step 3 — Notifications

| Field | Notes |
|---|---|
| Push notifications | Requires HA Companion App |
| Notifier name | e.g. `mobile_app_johns_iphone` — Settings → Mobile App → your device |
| Dashboard alerts | Persistent notification in HA sidebar |
| Email | Requires SMTP details |
| Gmail | Use an App Password — myaccount.google.com/apppasswords |

---

## Entities Created

### Sensors (9)
| Entity ID | Description |
|---|---|
| `sensor.cc_movement_monitor_latitude` | Current latitude |
| `sensor.cc_movement_monitor_longitude` | Current longitude |
| `sensor.cc_movement_monitor_speed` | Speed in km/h |
| `sensor.cc_movement_monitor_gps_fix` | `Fixed` / `No Fix` |
| `sensor.cc_movement_monitor_last_moved` | Timestamp of last movement (persists across restarts) |
| `sensor.cc_movement_monitor_hours_stationary` | Hours since last move |
| `sensor.cc_movement_monitor_days_stationary` | Days since last move |
| `sensor.cc_movement_monitor_days_until_must_move` | Days remaining before deadline |
| `sensor.cc_movement_monitor_mooring_status` | `OK` / `Move Soon` / `MUST MOVE` / `No GPS Fix` |

### Number — sliders (2)
| Entity ID | Description |
|---|---|
| `number.cc_movement_monitor_move_reminder_days` | Deadline threshold 1–28 days |
| `number.cc_movement_monitor_early_warning_days` | Warning threshold 1–27 days |

### Switches (3)
| Entity ID | Description |
|---|---|
| `switch.cc_movement_monitor_push_notifications` | Toggle mobile push |
| `switch.cc_movement_monitor_dashboard_alerts` | Toggle persistent notifications |
| `switch.cc_movement_monitor_email_alerts` | Toggle email |

---

## How Movement Detection Works

Every 60 seconds the coordinator reads Modbus registers 2800 (latitude) and 2802 (longitude)
from the Cerbo GX. It compares the new reading against the stored last-known position using
a **haversine distance** calculation. If the boat has moved more than **50 metres**, the
last-moved timestamp is updated and saved to HA Storage so it survives restarts.

The 50 m threshold ignores GPS drift while the boat is moored — typical anchor wobble
is 5–15 m.

---

## Notification Behaviour

| Event | Frequency | Channels |
|---|---|---|
| Early warning threshold reached | Every 24 h | Push + Dashboard + Email |
| Deadline (must-move) reached | Every 12 h | Push (Critical) + Dashboard + Email |
| the boat moves | Immediate | Dismiss push + dismiss dashboard |

**iOS Critical Alerts** bypass silent mode — the must-move alert will wake your phone
even if it is silenced.

---

## Changing Settings After Setup

**Settings → Devices & Services → CC Movement Monitor → Configure**

Or drag the slider entities directly on the CC Movement Monitor dashboard.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot connect" during setup | Verify IP; confirm Modbus TCP is enabled on port 502 |
| "Modbus error" during setup | Check the Slave/Unit ID on Cerbo → Settings → Services → Modbus TCP |
| GPS Fix shows "No Fix" | Check GPS antenna connection on Cerbo GX; wait for satellite lock |
| `days_stationary` not updating | Check `sensor.cc_movement_monitor_last_moved` has a timestamp; restart integration |
| Push notifications not arriving | Verify notifier name exactly matches the Companion App entry in HA |
| Email not sending | For Gmail use an App Password, not your account password |
