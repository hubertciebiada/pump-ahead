# PumpAhead - Mini HLD

## Problem

Krzywa grzewcza pompy ciepła reaguje na **aktualną** temperaturę zewnętrzną. Instalacje z dużą bezwładnością termiczną (ogrzewanie podłogowe, bufory ciepła) reagują z opóźnieniem 6-12 godzin. Te dwa fakty razem powodują:

1. **Rano niedogrzane** - w nocy było zimno, pompa grzała, ale ciepło "dotarło" do pomieszczeń dopiero gdy mieszkańcy wstali i wyszli
2. **W dzień przegrzane** - pompa nadal grzeje bo rano było zimno, a dodatkowo słońce przez okna dogrzewa

Efekt: dyskomfort + zmarnowana energia + gorszy COP (bo grzanie w najzimniejszych godzinach).

---

## Dla kogo jest PumpAhead?

**Wymagania:**
- Pompa ciepła Panasonic Aquarea z modułem Heishamon
- Instalacja z dużą bezwładnością termiczną:
  - Ogrzewanie podłogowe
  - Bufor ciepła
  - Ciężka konstrukcja budynku (akumulacja w masie)

**Nie nadaje się dla:**
- Innych producentów pomp ciepła (Heishamon działa tylko z Panasonic)
- Grzejników (szybka reakcja, mała bezwładność)

**Tryb pracy:** Tylko grzanie (MVP). Chłodzenie w przyszłych wersjach.

---

## Proponowane rozwiązanie

### Idea

Zamiast patrzeć na temperaturę TERAZ, patrzymy na temperaturę za X godzin (gdzie X = bezwładność instalacji). Krzywa grzewcza działa normalnie, ale z "przesuniętą" temperaturą zewnętrzną.

### Źródło danych o przyszłości

1. **Prognoza pogody** (Open-Meteo, darmowe, godzinowa)
2. **Korekta empiryczna**: "prognoza mówiła -5°C, jest -7°C → korekta -2°C dla następnych obliczeń"

### Dodatkowe korzyści

- Grzanie w cieplejszych godzinach = lepszy COP

---

## Architektura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Open-Meteo    │────▶│   PumpAhead     │────▶│   Heishamon     │
│   (prognoza)    │     │   .NET Web      │     │   (HTTP API)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                        │
                               ▼                        ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   SQL Server    │     │  Pompa ciepła   │
                        │   (historia,    │     │  Panasonic      │
                        │    config)      │     │  Aquarea        │
                        └─────────────────┘     └─────────────────┘
                               ▲
                               │
                        ┌─────────────────┐
                        │  Shelly H&T     │
                        │  Gen3 (temp.    │
                        │  wewnętrzna)    │
                        └─────────────────┘
```

---

## Algorytm

### Krzywa grzewcza

Liniowa interpolacja między dwoma punktami:
- (-15°C zewn. → 31°C zasilania)
- (15°C zewn. → 24°C zasilania)

**Ograniczenia:**
- Poniżej -15°C zewn. = 31°C zasilania (obcięcie)
- Powyżej 15°C zewn. = 24°C zasilania (obcięcie)
- **Minimum 20°C zasilania** - hardcoded, poniżej nie ma sensu grzać
- **Maksimum 35°C zasilania** - hardcoded zabezpieczenie wylewki przed pęknięciem

### Cykl sterowania (co 30-60 minut)

```
1. Pobierz aktualną temperaturę zewnętrzną z Heishamon
2. Pobierz prognozę na najbliższe 24h z Open-Meteo
3. Porównaj poprzednią prognozę z rzeczywistością → oblicz korektę
4. Weź temperaturę prognozowaną za OFFSET godzin (np. 6h)
5. Zastosuj korektę empiryczną
6. Oblicz temperaturę zasilania według krzywej grzewczej
7. Waliduj: min 20°C, max 35°C
8. Wyślij do Heishamon: setZ1HeatRequestTemp={wyliczona}
9. Zapisz do bazy (do analizy i korekty)
```

### Obsługa błędów

**Fallback:**
Przy błędzie krytycznym (brak komunikacji przez 1h, błąd algorytmu):
1. Wyślij komendę do Heishamon: przejście na **natywną krzywą grzewczą** pompy
2. Zaloguj błąd (Serilog, poziom Error)

Pompa wraca do trybu autonomicznego - system nie zostaje bez sterowania.

**Powrót z fallback:**
- Ręczna decyzja użytkownika
- UI pokazuje sugestię gdy komunikacja działa stabilnie ("Komunikacja OK od X minut - chcesz wrócić do sterowania PumpAhead?")

### Parametry do strojenia

| Parametr | Opis | Wartość startowa | Konfiguracja |
|----------|------|------------------|--------------|
| OFFSET | Bezwładność domu w godzinach | 6h | UI (na żywo) |
| Krzywa grzewcza | Punkty (temp_zew, temp_zasilania) | (-15,31), (15,24) | UI (na żywo) |
| Agresywność korekty | Jak bardzo ufamy korekcie vs nowej prognozie (0-100%) | 50% | UI (na żywo) |
| Min temp. zasilania | Poniżej nie ma sensu grzać | 20°C | Hardcoded |
| Max temp. zasilania | Zabezpieczenie wylewki | 35°C | Hardcoded |

### Korekta empiryczna - szczegóły

**Źródło rzeczywistej temperatury:** Heishamon (czujnik pompy ciepła)

**Pamięć błędów:** Średnia ważona z ostatnich 24 godzin. Wagi liniowo malejące - nowsze błędy mają większą wagę.

**Przykład:**
- Prognoza na 14:00 mówiła: **-5°C**
- Rzeczywistość o 14:00 (z Heishamon): **-7°C**
- Błąd: **-2°C**

Jak uwzględnić dla prognozy na 20:00 która mówi -8°C?

| Agresywność | Obliczenie | Wynik |
|-------------|------------|-------|
| 100% | -8°C + (-2°C) | -10°C |
| 50% | -8°C + (-1°C) | -9°C |
| 0% | -8°C + 0°C | -8°C |

---

## Wymagania

### Hardware

| Element | Koszt | Uwagi |
|---------|-------|-------|
| Heishamon (gotowy) | ~200 zł | Faza 1 |
| Shelly H&T Gen3 | ~100 zł | Faza 0 |
| Hosting (RPi/NAS/PC) | 0 zł | Lokalnie w domu |

### Komunikacja

| Urządzenie | Protokół | Uwagi |
|------------|----------|-------|
| Shelly H&T Gen3 | HTTP polling (REST API) | Lokalna sieć LAN |
| Heishamon | HTTP (GET/command) | Lokalna sieć LAN |
| Open-Meteo | HTTPS REST API | Wymaga współrzędnych (lat/lon) |

### Heishamon API

**Odczyt danych:**
```
GET http://heishamon.local/json
```

**Zapis parametrów:**
```
GET http://heishamon.local/command?setZ1HeatRequestTemp=32
```

**Fallback na natywną krzywą:**
```
GET http://heishamon.local/command?setZ1HeatCurve=1
```
> **TODO:** Zweryfikować poprawność komendy w dokumentacji Heishamon.

---

## Fazy rozwoju

Fazy to etapy rozwoju projektu, nie tryby działania aplikacji. Przejście między fazami następuje manualnie.

### Faza 0: Zbieranie danych

**Cel:** Poznanie bezwładności termicznej domu.

**Zakres:**
- Aplikacja webowa zbierająca temperaturę wewnętrzną z Shelly H&T Gen3
- Polling HTTP co 5 minut (konfigurowalne)
- Zapis do bazy danych
- Prosty dashboard z wykresem temperatury

**Czego NIE MA:**
- Heishamon (brak sterowania pompą)
- Temperatura zewnętrzna (będzie z Heishamon w Fazie 1)
- Algorytm sterowania

**Efekt:** Dane pokazujące jak temperatura wewnętrzna reaguje na zmiany (dzień/noc, pogoda).

### Faza 1: MVP

**Cel:** Działające sterowanie predykcyjne.

**Zakres:**
- Wszystko z Fazy 0
- Heishamon: odczyt temperatury zewnętrznej + sterowanie
- Open-Meteo: prognoza pogody
- Algorytm z OFFSET
- Korekta empiryczna
- Dashboard z historią
- Strona Fallback Control (ręczne sterowanie fallback)

**Konfiguracja:** Przez appsettings.json lub bezpośrednio w bazie (bez UI).

**Efekt:** Redukcja wahań temperatury, oszczędność energii.

### Faza 2: Configuration UI

**Cel:** Wygodna konfiguracja z poziomu UI.

**Zakres:**
- Strona Configuration (edycja OFFSET, krzywej, lokalizacji, agresywności korekty)
- Strona Temperature History (przeglądanie historii)
- Strona Control History (przeglądanie akcji sterowania)

---

## Przyszłe rozszerzenia (poza MVP)

Funkcje do rozważenia po walidacji MVP:

- **Integracja G14** - grzanie w tanich strefach taryfowych
- **Auto-tuning OFFSET** - automatyczne dostosowanie na podstawie temperatury wewnętrznej
- **Nasłonecznienie** - uwzględnienie zysków słonecznych (azymut okien + prognoza zachmurzenia)
- **Notyfikacje** - mail/push przy błędach lub anomaliach
- **Wiele czujników** - temperatura z różnych pomieszczeń (średnia/min/max)
- **SaaS** - udostępnienie jako usługa dla innych użytkowników Aquarea

---

## Oczekiwany efekt

- Oszczędność 10-15% energii
- Lepszy komfort (brak niedogrzania rano, brak przegrzania w dzień)
- Redukcja wahań temperatury wewnętrznej

---

## Instalacja testowa

Aplikacja jest rozwijana i testowana na następującej instalacji:

### Sprzęt

| Element | Specyfikacja |
|---------|--------------|
| Pompa ciepła | Panasonic Aquarea KIT-ADC07K3E5 (7kW, seria K) |
| Ogrzewanie | Podłogówka 170m², 1200m PEX, 13 obwodów |
| Budynek | Dom jednorodzinny, n50=1.31 (szczelny) |

### Parametry przed wdrożeniem

| Parametr | Wartość |
|----------|---------|
| Sterowanie | Tylko natywna krzywa grzewcza (reaktywna) |
| Krzywa grzewcza | (-15°C → 31°C), (15°C → 24°C) |
| Cel temperatury | 22°C |
| Rzeczywiste minimum | 20.1°C (rano) |
| Rzeczywiste maksimum | 24.5°C (po południu) |
| **Amplituda wahań** | **4.4°C** |

### Koszty (przed optymalizacją)

- Styczeń 2026 (mroźny): 636 kWh = ~650 zł
- Sezon grzewczy: szacunkowo ~2500-3000 zł
