# PumpAhead - Code Guide

Wytyczne implementacyjne dla projektu PumpAhead.

---

## Zasady ogólne

### Komentarze

- **Brak komentarzy dokumentacyjnych** (XML docs, `///`)
- Komentarze tylko w miejscach z workaroundami (1-3 linijki max)
- Kod powinien być samodokumentujący się (dobre nazwy, małe metody)

### Git commits

- Język: **angielski**
- Styl: krótkie, treściwe wiadomości
- Format: imperatyw (np. "Add", "Fix", "Update", nie "Added", "Fixed")
- Przykłady:
  - `Add heating curve calculator`
  - `Fix temperature validation`
  - `Update Shelly polling interval`

---

## Stack technologiczny

| Warstwa | Technologia |
|---------|-------------|
| Framework | .NET 10 |
| Frontend | Blazor Server |
| Scheduler | Quartz.NET |
| ORM | Entity Framework Core (Code First) |
| Baza danych | SQL Server |
| Logowanie | Serilog |
| CQRS | Własne interfejsy ICommandHandler/IQueryHandler |

---

## Architektura hexagonalna

Projekt stosuje architekturę hexagonalną (ports and adapters). Warstwy głębokie (DeepModel, UseCases) nie mogą zależeć od warstw zewnętrznych. Komunikacja z zewnętrznymi zasobami tylko przez interfejsy (porty).

```
┌─────────────────────────────────────────────────────────────────┐
│                        PumpAheadStartup                         │
│              (Blazor Server, Program.cs, DI, Quartz)            │
│                              UI                                 │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PumpAheadAdapters.Out                     │
│         (Shelly, Heishamon, OpenMeteo, SQL Server, Serilog)     │
│                    Implementacje interfejsów                    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PumpAheadUseCases                        │
│                    (CQRS: Commands + Queries)                   │
│                    Interfejsy do adapterów                      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PumpAheadDeepModel                        │
│            (Algorytm krzywej, korekta empiryczna)               │
│                      Czysta logika domenowa                     │
│                         Value Objects                           │
└─────────────────────────────────────────────────────────────────┘
```

### Kierunek zależności

```
PumpAheadStartup ──────► PumpAheadAdapters.Out ──────► PumpAheadUseCases ──────► PumpAheadDeepModel
                                   │                          │
                                   │                          │
                                   └──── implementuje ────────┘
                                         interfejsy z
                                         UseCases
```

---

## Struktura solucji

```
PumpAhead.sln
│
├── src/
│   ├── PumpAheadDeepModel/           # Czysta logika domenowa
│   │   ├── HeatingCurve/             # Algorytm krzywej grzewczej
│   │   ├── Correction/               # Korekta empiryczna
│   │   └── ValueObjects/             # Value Objects (Temperature, Percentage, etc.)
│   │
│   ├── PumpAheadUseCases/            # CQRS Commands + Queries
│   │   ├── Ports/                    # Interfejsy (porty)
│   │   │   ├── ICommandHandler.cs    # Interfejs dla command handlers
│   │   │   ├── IQueryHandler.cs      # Interfejs dla query handlers
│   │   │   └── Out/                  # Porty wyjściowe (UseCase → Adapter)
│   │   ├── Commands/                 # Komendy (zapis, sterowanie)
│   │   │   ├── SaveTemperature/      # SaveTemperature.Command + SaveTemperature.Handler
│   │   │   ├── ControlHeating/       # ControlHeating.Command + ControlHeating.Handler
│   │   │   ├── UpdateConfiguration/  # UpdateConfiguration.Command + UpdateConfiguration.Handler
│   │   │   └── TriggerFallback/      # TriggerFallback.Command + TriggerFallback.Handler
│   │   ├── Queries/                  # Zapytania (odczyt)
│   │   │   ├── GetTemperature/       # GetTemperature.Query + GetTemperature.Data
│   │   │   ├── GetTemperatureHistory/
│   │   │   ├── GetConfiguration/
│   │   │   ├── GetControlHistory/    # Historia akcji sterowania
│   │   │   └── GetSystemStatus/      # Status systemu (dla FallbackService)
│   │   └── Services/                 # Serwisy pomocnicze
│   │       └── FallbackService/      # Monitoring + ręczne sterowanie fallback
│   │
│   ├── PumpAheadAdapters.Out/        # Implementacje adapterów
│   │   ├── Sensors/                  # Adaptery czujników
│   │   │   └── Shelly/
│   │   ├── HeatPump/                 # Adaptery pomp ciepła
│   │   │   └── Heishamon/
│   │   ├── Weather/                  # Adaptery pogody
│   │   │   └── OpenMeteo/
│   │   └── Persistence/              # Adaptery bazy danych
│   │       └── SqlServer/
│   │           ├── Entities/         # Encje EF (osobne od modeli domenowych)
│   │           ├── Configuration/    # Mapowanie encji + konfiguracja EF
│   │           └── Repositories/
│   │
│   └── PumpAheadStartup/             # Warstwa startowa
│       ├── Program.cs                # Punkt wejścia (czysty, używa extension methods)
│       ├── Extensions/               # Extension methods dla DI
│       │   ├── ServiceCollectionExtensions.Adapters.cs
│       │   ├── ServiceCollectionExtensions.UseCases.cs
│       │   ├── ServiceCollectionExtensions.Quartz.cs
│       │   ├── ServiceCollectionExtensions.Blazor.cs
│       │   ├── ServiceCollectionExtensions.Logging.cs
│       │   └── ServiceCollectionExtensions.FallbackService.cs
│       ├── Jobs/                     # Joby Quartz (cienkie, delegują do Commands)
│       ├── Components/               # Komponenty Blazor
│       └── Pages/                    # Strony Blazor
│
└── tests/
    ├── PumpAheadDeepModelTests/      # Testy jednostkowe logiki domenowej
    ├── PumpAheadProcessModelTests/   # Testy CQRS handlers (z mockami)
    └── PumpAheadEndToEndTests/       # Testy E2E
```

---

## Warstwy - szczegóły

### PumpAheadDeepModel

Czysta logika domenowa. **Zero zależności zewnętrznych.** Tylko standardowa biblioteka .NET.

**Używa Value Objects zamiast typów prostych.**

| Element | Opis |
|---------|------|
| HeatingCurveCalculator | Oblicza temperaturę zasilania (min 20°C, max 35°C) |
| EmpiricalCorrectionCalculator | Oblicza korektę - średnia ważona z 24h, wagi liniowo malejące |
| Temperature | Value Object - temperatura (Celsius) |
| Percentage | Value Object - procent (0-100) |
| CurvePoint | Value Object - punkt krzywej (temp zewn., temp zasilania) |
| Hours | Value Object - czas w godzinach (OFFSET) |

**Zasady:**
- Brak zależności od innych projektów
- Brak interfejsów do zewnętrznych zasobów
- Metody czyste (pure functions) gdzie możliwe
- Hardcoded: min 20°C, max 35°C w HeatingCurveCalculator
- Value Objects zamiast decimal/int/double

### PumpAheadUseCases

CQRS - Commands (zapis) i Queries (odczyt). Definiuje interfejsy (porty) do komunikacji z zewnętrznymi zasobami.

**Wzorzec CQRS:**

```
SaveTemperature/
├── SaveTemperature.cs          # Statyczna klasa
│   ├── Command                 # Nested class - dane wejściowe
│   └── Handler                 # Nested class - logika
```

Nazewnictwo: `SaveTemperature`, `GetTemperature` (bez sufiksów Command/Query).

**Porty wyjściowe (Out) - interfejsy:**

| Interfejs | Opis |
|-----------|------|
| ISensorReader | Odczyt temperatury z czujnika |
| IHeatPumpController | Sterowanie pompą ciepła |
| IWeatherForecastProvider | Pobieranie prognozy pogody |
| ITemperatureRepository | Zapis/odczyt historii temperatur |
| IForecastRepository | Zapis/odczyt prognoz (do korekty empirycznej) |
| IConfigurationRepository | Zapis/odczyt konfiguracji |
| IControlActionRepository | Zapis/odczyt historii akcji sterowania |

**Commands:**

| Command | Opis |
|---------|------|
| SaveTemperature | Zapisuje odczyt temperatury z czujnika |
| ControlHeating | Wykonuje cykl sterowania (główny algorytm) |
| UpdateConfiguration | Aktualizuje parametr konfiguracji |
| TriggerFallback | Ręczne wywołanie fallback na natywną krzywą |

**Queries:**

| Query | Opis |
|-------|------|
| GetTemperature | Pobiera aktualną temperaturę (ostatni zapis z bazy - czyste CQRS) |
| GetTemperatureHistory | Pobiera historię temperatur |
| GetConfiguration | Pobiera konfigurację |
| GetControlHistory | Pobiera historię akcji sterowania |
| GetSystemStatus | Pobiera status systemu (dla monitoringu i FallbackService) |

**FallbackService:**

- Monitoruje stan systemu (czy komunikacja działa)
- Automatyczny fallback po 1h nieudanych prób (Polly)
- Możliwość ręcznego wywołania fallback z UI
- Możliwość ręcznego powrotu do sterowania PumpAhead

**Zasady:**
- Zależy tylko od PumpAheadDeepModel
- Definiuje interfejsy, nie implementacje
- Handlers są cienkie - orkiestrują, logika w DeepModel

### PumpAheadAdapters.Out

Implementacje interfejsów zdefiniowanych w UseCases.

**Encje EF są OSOBNE od modeli domenowych.** Mapowanie w folderze `Configuration/`.

| Adapter | Implementuje | Technologia |
|---------|--------------|-------------|
| ShellySensorReader | ISensorReader | HTTP client |
| HeishamonHeatPumpController | IHeatPumpController | HTTP client |
| OpenMeteoWeatherProvider | IWeatherForecastProvider | HTTP client |
| SqlServerTemperatureRepository | ITemperatureRepository | EF Core |
| SqlServerForecastRepository | IForecastRepository | EF Core |
| SqlServerConfigurationRepository | IConfigurationRepository | EF Core |
| SqlServerControlActionRepository | IControlActionRepository | EF Core |

**Struktura Persistence/SqlServer:**

```
SqlServer/
├── Entities/                   # Encje EF (POCO)
│   ├── SensorEntity.cs
│   ├── TemperatureReadingEntity.cs
│   ├── ForecastReadingEntity.cs
│   ├── ConfigParameterEntity.cs
│   └── ControlActionEntity.cs
├── Configuration/              # Mapowanie EF + konwersja do/z modeli domenowych
│   ├── SensorConfiguration.cs
│   ├── TemperatureReadingConfiguration.cs
│   └── ...
├── PumpAheadDbContext.cs
└── Repositories/
    ├── SqlServerTemperatureRepository.cs
    └── ...
```

**Zasady:**
- Zależy od PumpAheadUseCases (implementuje interfejsy)
- Encje EF w osobnym folderze Entities
- Mapowanie encje ↔ modele domenowe TYLKO w Configuration
- HTTP clients bez retry - błędy propagowane do FallbackService

### PumpAheadStartup

Warstwa startowa. Kompozycja aplikacji, DI, UI.

**Zasady:**
- Program.cs maksymalnie czysty - używa extension methods
- Extension methods podzielone na kategorie (osobne pliki)
- Joby Quartz są cienkie - tylko wywołują Commands
- Komponenty Blazor tylko prezentacja - logika w Handlers
- **UI nie zawiera logiki biznesowej**

**Extension methods:**

| Plik | Odpowiedzialność |
|------|------------------|
| ServiceCollectionExtensions.Adapters.cs | Rejestracja adapterów |
| ServiceCollectionExtensions.UseCases.cs | Rejestracja CQRS handlers |
| ServiceCollectionExtensions.Quartz.cs | Konfiguracja Quartz i jobów |
| ServiceCollectionExtensions.Blazor.cs | Konfiguracja Blazor Server |
| ServiceCollectionExtensions.Logging.cs | Konfiguracja Serilog |
| ServiceCollectionExtensions.FallbackService.cs | Konfiguracja FallbackService (śledzenie błędów, próg fallback) |

---

## CQRS - szczegóły

### Struktura Command

```
SaveTemperature.cs:
- static class SaveTemperature
  - record Command(SensorId, Temperature, Timestamp)
  - class Handler : ICommandHandler<Command>
    - Handle(Command) → void
```

### Struktura Query

```
GetTemperature.cs:
- static class GetTemperature
  - record Query(SensorId)
  - record Data(Temperature, Timestamp)
  - class Handler : IQueryHandler<Query, Data>
    - Handle(Query) → Data
```

### Interfejsy CQRS

Własne interfejsy w `PumpAheadUseCases/Ports/`:

```
ICommandHandler<TCommand>
- Task HandleAsync(TCommand command)

IQueryHandler<TQuery, TResult>
- Task<TResult> HandleAsync(TQuery query)
```

### Dispatch

Handlery rejestrowane w DI jako serwisy. Wstrzykiwane bezpośrednio (bez mediatora).

---

## Retry i Fallback

**Architektura retry:**
- Retry jest na poziomie **jobów**, nie wewnątrz HTTP clientów
- Pojedynczy job próbuje wykonać zadanie - jeśli fail, kończy się
- Następny job odpala się zgodnie z harmonogramem (co 30 min)
- **FallbackService** śledzi historię błędów

**Logika fallback:**
- FallbackService liczy nieudane próby w oknie czasowym
- Po 1h ciągłych błędów (np. 2 nieudane joby) → automatyczny fallback na natywną krzywą
- UI pokazuje status i sugestię powrotu gdy komunikacja stabilna

**Powrót z fallback:**
- Decyzja użytkownika (ręcznie z UI)
- UI pokazuje: "Komunikacja OK od X minut - chcesz wrócić do sterowania PumpAhead?"

---

## Quartz - joby

Joby mają minimalną logikę orkiestracji.

| Job | Interwał | Logika |
|-----|----------|--------|
| ShellyPollingJob | Co 5 min | 1. Odpytaj ISensorReader 2. Wywołaj SaveTemperature.Command z danymi |
| ControlAlgorithmJob | Co 30 min | Wywołaj ControlHeating.Command |

---

## UI (Blazor Server)

**Zasady:**
- Komponenty tylko prezentacyjne
- Logika w CQRS handlers (wstrzykiwane przez DI)
- Brak bezpośredniego dostępu do adapterów
- SignalR do live updates wykresów

**Strony:**

| Strona | Query/Command | Faza | Opis |
|--------|---------------|------|------|
| Dashboard | GetTemperature, GetSystemStatus | 0 | Wykres temperatury, status systemu |
| Fallback Control | GetSystemStatus, TriggerFallback | 1 | Ręczne sterowanie fallback, sugestia powrotu |
| Configuration | GetConfiguration, UpdateConfiguration | 2 | Edycja OFFSET, krzywej, lokalizacji |
| Temperature History | GetTemperatureHistory | 2 | Historia odczytów temperatury |
| Control History | GetControlHistory | 2 | Historia akcji sterowania |

---

## Konfiguracja

### appsettings.json (statyczna)

| Klucz | Opis |
|-------|------|
| ConnectionStrings:DefaultConnection | Connection string SQL Server |
| Devices:Shelly:Address | Adres IP Shelly |
| Devices:Heishamon:Address | Adres Heishamon |
| Polling:ShellyIntervalMinutes | Interwał Shelly (domyślnie 5) |
| Polling:ControlIntervalMinutes | Interwał sterowania (domyślnie 30) |
| Fallback:ErrorWindowMinutes | Okno czasowe do liczenia błędów (domyślnie 60) |
| Fallback:MaxErrorsBeforeFallback | Liczba błędów przed fallback (domyślnie 2) |

### Baza danych (dynamiczna)

| Klucz | Opis |
|-------|------|
| Offset | Bezwładność instalacji (godziny) |
| CorrectionAggression | Agresywność korekty (0-100%) |
| Latitude | Szerokość geograficzna |
| Longitude | Długość geograficzna |
| HeatingCurvePoints | Punkty krzywej (JSON) |

---

## Encje SQL Server

Encje EF (w Adapters.Out/Persistence/SqlServer/Entities):

| Encja | Opis |
|-------|------|
| SensorEntity | Czujnik (Id, Name, Address, Type, IsActive) |
| TemperatureReadingEntity | Odczyt (Id, SensorId, Temperature, Timestamp) |
| ForecastReadingEntity | Prognoza (Id, Timestamp, ForecastFor, Temperature, CalculatedWaterSupplyTemperature) |
| ConfigParameterEntity | Parametr (Id, Key, Value, UpdatedAt) |
| ControlActionEntity | Akcja (Id, Timestamp, OutdoorTemp, ForecastTemp, CorrectedTemp, SupplyTemp) |

---

## Testy

### PumpAheadDeepModelTests

- Testy jednostkowe HeatingCurveCalculator (min 20°C, max 35°C, interpolacja)
- Testy jednostkowe EmpiricalCorrectionCalculator (średnia ważona)
- Testy Value Objects

### PumpAheadProcessModelTests

- Testy CQRS handlers z mockami interfejsów
- Testy orkiestracji
- Testy FallbackService

### PumpAheadEndToEndTests

- Testy z prawdziwą bazą (TestContainers lub LocalDB)
- Testy integracyjne adapterów

---

## Fazy implementacji

### Faza 0: Zbieranie danych

**Implementuj:**
- PumpAheadDeepModel: ValueObjects (Temperature, Percentage)
- PumpAheadUseCases: Ports (ICommandHandler, IQueryHandler, ISensorReader, ITemperatureRepository, IConfigurationRepository)
- PumpAheadUseCases: SaveTemperature, GetTemperature, GetTemperatureHistory
- PumpAheadAdapters.Out: ShellySensorReader, SqlServer*Repository, Entities, Configuration
- PumpAheadStartup: Program.cs, Extensions, ShellyPollingJob, Dashboard
- Testy: DeepModelTests, ProcessModelTests

**NIE implementuj:**
- HeatingCurveCalculator, EmpiricalCorrectionCalculator
- IHeatPumpController, IWeatherForecastProvider, IForecastRepository
- Heishamon, OpenMeteo adaptery
- ControlAlgorithmJob, FallbackService
- GetConfiguration, UpdateConfiguration (Faza 2)
- Strony: Configuration, Temperature History, Control History, Fallback Control

**Konfiguracja:** appsettings.json (adresy urządzeń, interwały)

### Faza 1: MVP (sterowanie)

**Dodaj:**
- PumpAheadDeepModel: HeatingCurveCalculator, EmpiricalCorrectionCalculator, Hours, CurvePoint
- PumpAheadUseCases: IHeatPumpController, IWeatherForecastProvider, IForecastRepository, IControlActionRepository
- PumpAheadUseCases: ControlHeating, TriggerFallback, GetSystemStatus, FallbackService
- PumpAheadAdapters.Out: HeishamonHeatPumpController, OpenMeteoWeatherProvider, ForecastRepository, ControlActionRepository
- PumpAheadStartup: ControlAlgorithmJob
- Strona: Fallback Control (ręczne sterowanie fallback)
- Testy: pełne pokrycie dla nowych komponentów

**Konfiguracja:** appsettings.json + bezpośrednio w bazie (bez UI)

### Faza 2: Configuration UI

**Dodaj:**
- PumpAheadUseCases: GetConfiguration, UpdateConfiguration, GetControlHistory
- Strona: Configuration (edycja OFFSET, krzywej, lokalizacji, agresywności)
- Strona: Temperature History
- Strona: Control History
