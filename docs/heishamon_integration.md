# HeishaMon HTTP/REST API technical reference for LLM integration

HeishaMon provides a lightweight but fully functional HTTP/REST API that enables read and write operations on Panasonic Aquarea heat pumps without requiring MQTT. The primary data endpoint `/json` returns **115+ parameters** including temperatures, power consumption, and compressor status—everything needed for predictive heating control. Commands use simple GET requests to `/command` with query parameters. **No authentication is required** for the API endpoints, making integration straightforward for local network deployments like PumpAhead.

## Available HTTP endpoints

HeishaMon's ESP8266/ESP32 firmware exposes six HTTP endpoints. For read-only integration, only `/json` is essential:

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/json` | GET | Returns all heat pump data in JSON format | No |
| `/command` | GET | Send control commands via query parameters | No |
| `/` | GET | Web interface (HTML) | No |
| `/debug` | GET | Raw hex data dump (203 bytes) | No |
| `/reboot` | GET | Trigger device restart | Yes |
| `/settings` | GET/POST | Configuration interface | Yes |

The `/json` endpoint is the **primary integration point** for monitoring systems. It returns real-time data as received from the heat pump's serial protocol, typically updating every few seconds. CORS headers (`Access-Control-Allow-Origin: *`) are enabled, allowing browser-based applications to query directly.

## JSON response structure and schema

The `/json` endpoint returns a structured object containing three main arrays:

```json
{
  "heatpump": [
    {"name": "Heatpump_State", "value": "1", "description": "On"},
    {"name": "Pump_Flow", "value": "10.51", "description": "l/min"},
    {"name": "Main_Inlet_Temp", "value": "32", "description": "°C"},
    {"name": "Main_Outlet_Temp", "value": "34.25", "description": "°C"},
    {"name": "Compressor_Freq", "value": "45", "description": "Hz"},
    {"name": "Outside_Temp", "value": "5", "description": "°C"},
    {"name": "Heat_Power_Production", "value": "4500", "description": "Watt"},
    {"name": "Heat_Power_Consumption", "value": "1200", "description": "Watt"}
  ],
  "1wire": [
    {"name": "28FF1234567890AB", "value": "23.5"}
  ],
  "s0": [
    {"name": "Watt/1", "value": "1500"},
    {"name": "WatthourTotal/1", "value": "12345"}
  ]
}
```

Each parameter appears as an object with `name`, `value`, and optionally `description` fields. Values are returned as strings regardless of underlying data type. The `1wire` array contains readings from any connected DS18B20 temperature sensors (identified by hex addresses), while `s0` holds external S0 pulse meter data for kWh monitoring.

## Complete parameter reference for predictive heating

HeishaMon exposes **115+ topics** (TOP0–TOP108+). Here are the parameters most relevant for PumpAhead's predictive control:

### Temperature sensors

| Topic ID | Name | Description | Unit |
|----------|------|-------------|------|
| TOP5 | `Main_Inlet_Temp` | Water returning to heat pump | °C |
| TOP6 | `Main_Outlet_Temp` | Water leaving heat pump | °C |
| TOP7 | `Main_Target_Temp` | Target outlet temperature | °C |
| TOP14 | `Outside_Temp` | Outdoor ambient temperature | °C |
| TOP21 | `Outside_Pipe_Temp` | Outdoor unit pipe temperature | °C |
| TOP10 | `DHW_Temp` | Domestic hot water actual | °C |
| TOP9 | `DHW_Target_Temp` | DHW target temperature | °C |
| TOP33 | `Room_Thermostat_Temp` | Room sensor (if connected) | °C |
| TOP36 | `Z1_Water_Temp` | Zone 1 water temperature | °C |
| TOP37 | `Z2_Water_Temp` | Zone 2 water temperature | °C |

### Power and COP calculation

| Topic ID | Name | Description | Unit |
|----------|------|-------------|------|
| TOP15 | `Heat_Power_Production` | Thermal output (heating) | Watt |
| TOP16 | `Heat_Power_Consumption` | Electrical input (heating) | Watt |
| TOP38 | `Cool_Power_Production` | Thermal output (cooling) | Watt |
| TOP39 | `Cool_Power_Consumption` | Electrical input (cooling) | Watt |
| TOP40 | `DHW_Power_Production` | Thermal output (DHW) | Watt |
| TOP41 | `DHW_Power_Consumption` | Electrical input (DHW) | Watt |

**COP is calculated as:** `Power_Production / Power_Consumption`. For K, L, and M series heat pumps, use the `extra/` topics (XTOP) for more accurate power values—standard TOP values may show incorrect readings like -200.

### Compressor and operational status

| Topic ID | Name | Description | Values/Unit |
|----------|------|-------------|-------------|
| TOP0 | `Heatpump_State` | Main on/off state | 0=off, 1=on |
| TOP8 | `Compressor_Freq` | Compressor frequency | Hz (0=stopped) |
| TOP1 | `Pump_Flow` | Water circulation rate | l/min |
| TOP93 | `Pump_Duty` | Pump duty cycle | % |
| TOP4 | `Operating_Mode_State` | Current mode | 0–8 (see below) |
| TOP26 | `Defrosting_State` | Defrost cycle active | 0=no, 1=yes |
| TOP17 | `Powerful_Mode_Time` | Powerful mode remaining | 0/30/60/90 min |
| TOP18 | `Quiet_Mode_Level` | Quiet mode setting | 0–3 |

**Operating modes (TOP4):** 0=Heat only, 1=Cool only, 2=Auto(Heat), 3=DHW only, 4=Heat+DHW, 5=Cool+DHW, 6=Auto(Heat)+DHW, 7=Auto(Cool), 8=Auto(Cool)+DHW

### Energy counters and runtime

| Topic ID | Name | Description | Unit |
|----------|------|-------------|------|
| TOP11 | `Operations_Hours` | Total compressor runtime | hours |
| TOP12 | `Operations_Counter` | Start/stop count | count |
| TOP90 | `Room_Heater_Operations_Hours` | Backup heater runtime (space) | hours |
| TOP91 | `DHW_Heater_Operations_Hours` | Backup heater runtime (DHW) | hours |

## Polling intervals and rate limit recommendations

HeishaMon has **no enforced rate limits** for HTTP reads, but practical constraints exist:

- **Recommended read interval: 5–30 seconds.** The heat pump updates data every few seconds via serial protocol. Polling faster than 5 seconds provides no benefit and increases ESP load.
- **For predictive algorithms:** 30-second intervals are typical for monitoring dashboards; 5–10 seconds for real-time control loops.
- **ESP resource limits:** The ESP8266 has limited memory. Avoid multiple simultaneous connections or extremely rapid polling that could cause instability.

For write operations (commands), the official documentation warns: **"Every second is way too much. Just a few per hour, per settings, should probably be fine."** Commands may write to the heat pump's EEPROM, which has finite write cycles. Additionally, rapid sequential commands can overwhelm the serial buffer, causing commands to be dropped.

## Authentication requirements

The HTTP API endpoints are **unauthenticated by default**:

- `/json` — No authentication
- `/command` — No authentication  
- `/debug` — No authentication

Admin functions require basic authentication:
- **Username:** `admin`
- **Default password:** `heisha` (or custom password set during initial setup)
- **Protected endpoints:** `/reboot`, `/settings`, `/firmware`, `/factoryreset`

**Security note:** HeishaMon is designed for trusted local networks only. There is no HTTPS support or token-based authentication. For PumpAhead integration, ensure the system operates on a secured network segment.

## Example HTTP requests and responses

### Reading all data

```bash
# Using hostname (mDNS)
curl http://heishamon.local/json

# Using IP address
curl http://192.168.1.100/json

# With timeout for reliability
curl --max-time 5 http://192.168.1.100/json
```

**Response (abbreviated):**
```json
{
  "heatpump": [
    {"name": "Heatpump_State", "value": "1"},
    {"name": "Pump_Flow", "value": "12.3"},
    {"name": "Main_Inlet_Temp", "value": "28"},
    {"name": "Main_Outlet_Temp", "value": "32"},
    {"name": "Compressor_Freq", "value": "52"},
    {"name": "Outside_Temp", "value": "3"},
    {"name": "Heat_Power_Production", "value": "5200"},
    {"name": "Heat_Power_Consumption", "value": "1350"},
    {"name": "Operating_Mode_State", "value": "4"},
    {"name": "DHW_Temp", "value": "48"}
  ],
  "1wire": [],
  "s0": []
}
```

### Sending commands (write operations)

```bash
# Turn heat pump on
curl "http://192.168.1.100/command?SetHeatpump=1"

# Set quiet mode to level 3 (quietest)
curl "http://192.168.1.100/command?SetQuietMode=3"

# Set DHW temperature to 55°C
curl "http://192.168.1.100/command?SetDHWTemp=55"

# Set operation mode to Heat+DHW
curl "http://192.168.1.100/command?SetOperationMode=4"

# Multiple commands in one request (recommended)
curl "http://192.168.1.100/command?SetQuietMode=2&SetZ1HeatRequestTemperature=22"

# Force DHW heating cycle
curl "http://192.168.1.100/command?SetForceDHW=1"

# Smart Grid mode (requires Optional PCB emulation)
curl "http://192.168.1.100/command?SetSmartGridMode=2"
```

### Python integration example

```python
import requests
import time

HEISHAMON_IP = "192.168.1.100"

def get_heatpump_data():
    """Fetch all heat pump parameters."""
    response = requests.get(f"http://{HEISHAMON_IP}/json", timeout=5)
    data = response.json()
    
    # Convert to dictionary for easier access
    params = {item["name"]: item["value"] for item in data["heatpump"]}
    return params

def calculate_cop(params):
    """Calculate current COP from power values."""
    production = float(params.get("Heat_Power_Production", 0))
    consumption = float(params.get("Heat_Power_Consumption", 1))
    return production / consumption if consumption > 0 else 0

def send_command(command, value):
    """Send a command to the heat pump."""
    url = f"http://{HEISHAMON_IP}/command?{command}={value}"
    response = requests.get(url, timeout=5)
    return response.status_code == 200

# Example usage for PumpAhead
params = get_heatpump_data()
print(f"Outside temp: {params['Outside_Temp']}°C")
print(f"Outlet temp: {params['Main_Outlet_Temp']}°C")
print(f"Compressor: {params['Compressor_Freq']} Hz")
print(f"Current COP: {calculate_cop(params):.2f}")
```

## Command reference for write operations

| Command | Description | Values |
|---------|-------------|--------|
| `SetHeatpump` | Main power | 0=off, 1=on |
| `SetOperationMode` | Operating mode | 0=Heat, 1=Cool, 2=Auto, 3=DHW, 4=Heat+DHW, 5=Cool+DHW, 6=Auto+DHW |
| `SetQuietMode` | Noise level | 0=off, 1/2/3=quiet levels |
| `SetPowerfulMode` | Boost duration | 0=off, 1=30min, 2=60min, 3=90min |
| `SetDHWTemp` | DHW target | 40–75°C |
| `SetForceDHW` | Force DHW cycle | 0=off, 1=on |
| `SetZ1HeatRequestTemperature` | Zone 1 heating | -5 to +5 (shift) or 20–max (direct) |
| `SetZ1CoolRequestTemperature` | Zone 1 cooling | -5 to +5 or 20–max |
| `SetSmartGridMode` | SG Ready | 0=normal, 1=reduced, 2=recommended, 3=forced |
| `SetCurves` | Heating curves | JSON object (see docs) |

## Integration considerations for PumpAhead

For a predictive heating control system, focus on these aspects:

**Essential read parameters:** `Outside_Temp`, `Main_Outlet_Temp`, `Main_Inlet_Temp`, `Compressor_Freq`, `Heat_Power_Production`, `Heat_Power_Consumption`, and `Operating_Mode_State`. These provide the core inputs for predicting thermal demand and optimizing COP.

**Write sparingly:** Heat pumps are slow thermal systems. Adjust setpoints infrequently—perhaps hourly based on predictions rather than minute-by-minute. This protects EEPROM and aligns with how heat pumps operate.

**Use Smart Grid modes:** For demand response or price-based optimization, `SetSmartGridMode` (requires Optional PCB emulation in HeishaMon settings) provides standardized modes: normal operation, reduced output, increased output, or forced maximum. This is cleaner than manipulating temperature setpoints.

**Handle K/L/M series correctly:** These newer models require the `extra/` topics for accurate power readings. Check `Heat_Pump_Model` (TOP92) to detect the series and adjust parsing accordingly.

## Conclusion

HeishaMon's HTTP API provides complete access to Panasonic Aquarea heat pump data through a simple, unauthenticated REST interface. The `/json` endpoint delivers **115+ parameters** suitable for sophisticated predictive control, while `/command` enables setpoint changes via straightforward GET requests. For PumpAhead integration, poll `/json` at 10–30 second intervals for monitoring, calculate COP from the production/consumption power values, and send commands sparingly to respect EEPROM limitations. The lack of authentication simplifies development but requires network-level security measures for production deployments.