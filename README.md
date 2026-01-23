# PumpAhead

Predictive heating control for Panasonic Aquarea heat pumps.

## Why?

Traditional heat pumps react to **current** outdoor temperature. But underfloor heating has 6-12 hours of thermal lag. Result: cold mornings, hot afternoons, wasted energy.

PumpAhead uses weather forecasts to heat **proactively** – anticipating temperature changes instead of reacting to them.

## How it works

1. Fetches weather forecast (Open-Meteo API)
2. Looks at predicted temperature X hours ahead (X = your system's thermal lag)
3. Calculates optimal supply water temperature
4. Sends command to heat pump via Heishamon
5. Learns from forecast errors to improve accuracy

## Requirements

**Hardware:**
- Panasonic Aquarea heat pump
- Heishamon module
- Shelly H&T Gen3 (indoor temp sensor)
- Server (Raspberry Pi, NAS, or PC)

**System:**
- High thermal inertia (underfloor heating, buffer tank, heavy construction)
- Local network access to devices

## Tech Stack

- .NET 10
- Blazor Server
- SQL Server + EF Core
- Quartz.NET
- Serilog

## Docs

- [HLD](docs/pump-ahead-hld.md) – design & algorithm
- [Code Guide](docs/code-guide.md) – implementation guidelines

## License

MIT
