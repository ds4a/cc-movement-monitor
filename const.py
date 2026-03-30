"""Constants for the CC Movement Monitor integration."""

DOMAIN = "cc_movement_monitor"
NAME   = "CC Movement Monitor"

# Config entry keys
CONF_BOAT_NAME         = "boat_name"
CONF_CERBO_HOST        = "cerbo_host"
CONF_MODBUS_SLAVE      = "modbus_slave"
CONF_REMINDER_DAYS     = "reminder_days"
CONF_WARNING_DAYS      = "warning_days"
CONF_NOTIFIER          = "notifier"
CONF_SMTP_SERVER       = "smtp_server"
CONF_SMTP_PORT         = "smtp_port"
CONF_SMTP_USER         = "smtp_user"
CONF_SMTP_PASSWORD     = "smtp_password"
CONF_SMTP_RECIPIENT    = "smtp_recipient"
CONF_NOTIFY_PUSH       = "notify_push"
CONF_NOTIFY_PERSISTENT = "notify_persistent"
CONF_NOTIFY_EMAIL      = "notify_email"

# Defaults
DEFAULT_MODBUS_PORT    = 502
DEFAULT_REMINDER_DAYS  = 14
DEFAULT_WARNING_DAYS   = 10
DEFAULT_SCAN_INTERVAL  = 60       # seconds
MOVEMENT_THRESHOLD_M   = 50.0     # metres

# Victron Modbus registers  (Unit ID 100 = com.victronenergy.gps)
REG_LATITUDE   = 2800   # int32,  scale 1e-7
REG_LONGITUDE  = 2802   # int32,  scale 1e-7
REG_SPEED      = 2804   # uint16, scale 0.01  m/s
REG_FIX        = 2806   # uint16, 0=no fix / 1=fix
REG_ALTITUDE   = 2808   # int32,  scale 0.01  metres

# Entity unique_id suffixes
ENTITY_LATITUDE         = "latitude"
ENTITY_LONGITUDE        = "longitude"
ENTITY_SPEED            = "speed"
ENTITY_FIX              = "gps_fix"
ENTITY_LAST_MOVED       = "last_moved"
ENTITY_STATIONARY_HOURS = "stationary_hours"
ENTITY_STATIONARY_DAYS  = "stationary_days"
ENTITY_DAYS_REMAINING   = "days_remaining"
ENTITY_STATUS           = "mooring_status"

# Mooring status values
STATUS_OK     = "OK"
STATUS_WARN   = "Move Soon"
STATUS_ALERT  = "MUST MOVE"
STATUS_NO_FIX = "No GPS Fix"

# Storage keys
STORE_LAST_MOVED = "last_moved_utc"
STORE_LAST_LAT   = "last_lat"
STORE_LAST_LON   = "last_lon"
