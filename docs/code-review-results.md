# Code Review Results - 2026-01-29

## Review wykonany przez 45 równoległych agentów

### NAPRAWIONE (15 poprawek):

| # | Plik | Naprawa |
|---|------|---------|
| 1 | `ChartStateService.cs` | **USUNIĘTY** (dead code) |
| 2 | `GuiExtensions.cs` | Usunięta rejestracja ChartStateService |
| 3 | `Temperature.cs` | Dodana walidacja absolute zero (-273.15°C) |
| 4 | `DhwTemperature.cs` | Usunięte XML komentarze |
| 5 | `WaterTemperature.cs` | Usunięte XML komentarze |
| 6 | `Frequency.cs` | Usunięte nieużywane IComparable i operatory |
| 7 | `TemperatureReadingConfiguration.cs` | Usunięte zbędne IsRequired, dodane SensorId config |
| 8 | `SensorConfiguration.cs` | Usunięte zbędne IsRequired(false), naprawiona relacja |
| 9 | `HeatPumpConfiguration.cs` | Usunięte 11x zbędne IsRequired() |
| 10 | `TemperatureReadingEntity.cs` | Usunięta zbędna navigation property |
| 11 | `CentralHeatingData.cs` | Uproszczone do primary constructor |
| 12 | `DomesticHotWaterData.cs` | Uproszczone do primary constructor |
| 13 | `SqlServerHeatPumpRepository.cs` | Naprawione użycia VO, `context` → `dbContext` |
| 14 | `SensorEndpoints.cs` | Usunięty dual ID logic i zbędna abstrakcja |
| 15 | `SqlServerTemperatureRepository.cs` | Select przed ToListAsync |

### POZOSTAŁE DO NAPRAWY (wymagają większych zmian):

| Plik | Problem | Severity |
|------|---------|----------|
| `HeatPump.cs` | Anemic model - to DTO, nie agregat. Brak business invariants, domain behavior. Powinien być `HeatPumpSnapshot` Value Object. | HIGH |
| `RecordSensorReading.cs` | Handler auto-tworzy sensor jeśli nie istnieje - łamie CQRS SRP. Powinien rzucić wyjątek, tworzenie sensora = osobny command. | HIGH |
| `ISensorRepository.cs` | 1) Logika biznesowa `DisplayName` w DTO 2) Mix CRUD + specialized ops 3) Hidden upsert semantics | HIGH |
| `GetAllSensorsHistory.cs` | N+1 query problem - foreach z query wewnątrz. Potrzebna metoda batch w repo. | HIGH |
| `IHeatPumpRepository.cs` | YAGNI - 5 metod, 3 nieużywane. Brak ISP (read+write w jednym interfejsie). | MEDIUM |
| `CompressorData.cs` | Podwójne wrappowanie - CompressorData wrappuje tylko Frequency (już jest VO). Usunąć i użyć Frequency w HeatPump. | MEDIUM |
| `SignalRSensorNotificationService.cs` | Implementacja outbound portu w Adapters.Gui zamiast Adapters.Out. | MEDIUM |
| `SqlServerHeatPumpRepository.cs` | DRY violation - manual property mapping w SaveAsync duplikuje MapToEntity | MEDIUM |
| `SqlServerSensorRepository.cs` | Zbędne query w SaveAsync - EF Core Update() może obsłużyć upsert automatycznie | LOW |

### PLIKI CZYSTE (brak problemów):

- SensorId.cs, SensorReading.cs, HeatPumpId.cs, PumpFlow.cs, OutsideTemperature.cs
- ICommandHandler.cs, IQueryHandler.cs, ITemperatureRepository.cs, ISensorNotificationService.cs
- GetTemperature.cs, GetTemperatureHistory.cs, SaveTemperature.cs
- SensorHub.cs, SensorEntity.cs, HeatPumpEntity.cs
- ServiceCollectionExtensions.Logging.cs, DeviceSettings.cs, PollingSettings.cs

### TESTY - problemy wspólne:

- Brak weryfikacji propagacji CancellationToken
- Shared mutable state w konstruktorze (anty-wzorzec)
- Brak weryfikacji wywołań repository (Received)
