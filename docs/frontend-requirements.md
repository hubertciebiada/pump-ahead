# PumpAhead Frontend - Specyfikacja UI

## Struktura strony

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HEADER (stały na górze)                                                     │
│ ┌─────────────┬────────────┬──────────────────┬─────────┬─────────┐        │
│ │ Logo        │ Dashboard  │ Krzywa grzewcza  │ Refresh │ Settings│        │
│ │ "PumpAhead" │ (aktywny)  │ (link)           │ (ikona) │ (ikona) │        │
│ └─────────────┴────────────┴──────────────────┴─────────┴─────────┘        │
├─────────────────────────────────────────────────────────────────────────────┤
│ TREŚĆ (scrollowalna)                                                        │
│                                                                             │
│ ┌─────────────────────┬─────────────────────┬─────────────────────┐        │
│ │ WYKRES 1            │ WYKRES 2            │ WYKRES 3            │        │
│ │ Temperatura         │ Centralne           │ Temperatura         │        │
│ │ zewnętrzna          │ Ogrzewanie          │ wewnętrzna          │        │
│ │                     │                     │                     │        │
│ │ [wykres liniowy]    │ [wykres liniowy]    │ [wykres liniowy]    │        │
│ │ kolor: cyan         │ kolor: magenta      │ kolor: niebieski    │        │
│ │                     │                     │ + linia docelowa    │        │
│ │                     │                     │   (zielona przeryw.)│        │
│ └─────────────────────┴─────────────────────┴─────────────────────┘        │
│                                                                             │
│ ┌────────────────┬────────────────┬────────────────┬────────────────┐      │
│ │ KARTA 1        │ KARTA 2        │ KARTA 3        │ KARTA 4        │      │
│ │ Otoczenie      │ CO             │ CWU            │ Sprężarka      │      │
│ │                │                │                │                │      │
│ │ [lista pól]    │ [lista pól]    │ [lista pól]    │ [lista pól]    │      │
│ │                │                │                │                │      │
│ └────────────────┴────────────────┴────────────────┴────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Header

| Pozycja | Element | Opis |
|---------|---------|------|
| Lewa | Logo "PumpAhead" | Link do strony głównej |
| Środek-lewa | Link "Dashboard" | Strona główna `/` |
| Środek | Link "Krzywa grzewcza" | Strona `/heating-curve` |
| Prawa | Przycisk Refresh | Ikona `refresh`, odświeża dane |
| Prawa | Przycisk Settings | Ikona `settings`, otwiera dialog |

---

## Wiersz wykresów (3 kolumny)

### Wykres 1: Temperatura zewnętrzna
- **Pozycja**: lewa kolumna
- **Typ**: wykres liniowy (TradingView style)
- **Kolor linii**: cyan `#26c6da`
- **Oś X**: czas (ostatnie 24h)
- **Oś Y**: temperatura °C
- **Dane**: aktualna temperatura na zewnątrz (API pogodowe)

### Wykres 2: Centralne Ogrzewanie
- **Pozycja**: środkowa kolumna
- **Typ**: wykres liniowy
- **Kolor linii**: magenta `#ff4081`
- **Oś X**: czas (ostatnie 24h)
- **Oś Y**: temperatura °C
- **Dane**: temperatura zasilania CO z pompy ciepła

### Wykres 3: Temperatura wewnętrzna
- **Pozycja**: prawa kolumna
- **Typ**: wykres liniowy
- **Kolor linii**: niebieski `#2196f3`
- **Dodatkowa linia**: temperatura docelowa (zielona `#4caf50`, przerywana)
- **Oś X**: czas (ostatnie 24h)
- **Oś Y**: temperatura °C
- **Dane**: odczyty z sensorów Shelly

---

## Wiersz kart danych (4 kolumny)

### Karta 1: Otoczenie

| Ikona | Pole | Wartość | Kolor ikony |
|-------|------|---------|-------------|
| `home` | [Nazwa sensora - dynamiczna] | XX,X°C | niebieski |
| `thermostat` | Wewnętrzna (oczekiwana) | XX,X°C | zielony |
| `cloud` | Zewnętrzna (aktualna) | XX,X°C | cyan |
| `schedule` | Zewnętrzna (+Xh) | XX,X°C | pomarańczowy |
| `trending_up` | Korekta empiryczna | ±X,X°C | szary |

### Karta 2: CO (Centralne Ogrzewanie)

| Ikona | Pole | Wartość | Kolor ikony |
|-------|------|---------|-------------|
| `show_chart` | Zasilanie wg krzywej | XX°C | szary |
| `timer` | Offset | Xh | cyan |
| `calculate` | Zasilanie z offsetem | XX°C | niebieski |
| `tune` | Zasilanie zadane | XX°C | pomarańczowy |
| `opacity` | Zasilanie faktyczne | XX°C | czerwony |
| `water_drop` | Powrót faktyczny | XX°C | szary |

### Karta 3: CWU (Ciepła Woda Użytkowa)

| Ikona | Pole | Wartość | Kolor ikony |
|-------|------|---------|-------------|
| `bathtub` | Zadana | XX°C | pomarańczowy |
| `hot_tub` | Aktualna | XX°C | czerwony |
| `swap_vert` | Delta wygrzewania | X°C | cyan |
| `wb_sunny` | Sugerowana godz. wygrzewania | HH:MM | zielony |

### Karta 4: Sprężarka

| Ikona | Pole | Wartość | Kolor ikony |
|-------|------|---------|-------------|
| `speed` | Częstotliwość | XX Hz | niebieski |
| `replay` | Cykle włącz/wyłącz | XXX | pomarańczowy |
| `access_time` | Czas pracy | XXXXh | cyan |


---

## Strona: Krzywa grzewcza

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HEADER (jak wyżej, "Krzywa grzewcza" aktywny)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Krzywa grzewcza                                                         │ │
│ │                                                                         │ │
│ │  55°C ┤                                                                 │ │
│ │       │ ●                                                               │ │
│ │  50°C ┤   ●                                                             │ │
│ │       │     ●                                                           │ │
│ │  45°C ┤       ●                                                         │ │
│ │       │         ●                                                       │ │
│ │  40°C ┤           ●                                                     │ │
│ │       │             ●                                                   │ │
│ │  35°C ┤               ●                                                 │ │
│ │       │                 ●                                               │ │
│ │  30°C ┤                   ●                                             │ │
│ │       │                     ●                                           │ │
│ │  25°C ┤                       ●                                         │ │
│ │       └───┴───┴───┴───┴───┴───┴───┴                                     │ │
│ │       -15 -10  -5   0   5  10  15  °C zewn.                             │ │
│ │                                                                         │ │
│ │  Oś X: Temperatura zewnętrzna                                           │ │
│ │  Oś Y: Temperatura zasilania CO                                         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Motyw kolorystyczny

- **Tło**: ciemnoszary `#1e1e1e`
- **Tło kart**: ciemnoszary `#2d2d2d`
- **Tekst**: jasnoszary `#d4d4d4`
- **Siatka wykresów**: `#333333`
