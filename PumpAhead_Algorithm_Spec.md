# PumpAhead — Specyfikacja algorytmu sterowania klimatem

> **Projekt:** Smart Home HA — predykcyjne sterowanie ogrzewaniem i chłodzeniem
> **Autor:** Hubert + Claude (konwersacja 2026-03-29)
> **Status:** Projekt algorytmu, pre-implementacja
> **Docelowa forma:** Custom integration dla Home Assistant (HACS)

---

## 1. Definicja problemu

### 1.1 Problem ogólny

Inteligentne sterowanie źródłami ciepła/chłodu o **dużej bezwładności termicznej** (ogrzewanie podłogowe) z opcjonalnym wspomaganiem szybkim źródłem konwekcyjnym (split/fan-coil) w wybranych pomieszczeniach — tak, aby utrzymać stałą temperaturę zadaną zarówno zimą (grzanie) jak i latem (chłodzenie).

**Priorytetem jest wolne źródło (UFH).** Każde pomieszczenie ma podłogówkę. Nie każde ma split. Algorytm musi działać w obu konfiguracjach:

| Konfiguracja | Pomieszczenia | Sterowanie |
|---|---|---|
| **UFH only** | Wszystkie (13 pętli) | Model RC + predykcja → pozycja zaworu 0–100% |
| **UFH + split** | Wybrane (max 6 z klimatyzacją) | Jak wyżej + koordynacja z szybkim źródłem |

| Źródło | Typ | τ (stała czasowa) | Rola | Tryby | Wymagane |
|--------|-----|-------------------|------|-------|----------|
| Ogrzewanie/chłodzenie podłogowe (UFH) | Woda w wylewce betonowej | 4–6 godzin | Baza — ciągłe, wolne, energooszczędne | heat + cool | **zawsze** |
| Pompa powietrze-powietrze (split) | Konwekcja powietrzna | 5–15 minut | Boost — szybka korekta, droższa | heat + cool | **opcjonalnie** per pokój |

Architektura algorytmu musi być **modularna**: core to sterowanie UFH z modelem predykcyjnym, a warstwa koordynacji z szybkim źródłem to opcjonalny moduł aktywowany per pokój. Pokój bez splita dostaje pełen benefit z predykcji pogodowej i pre-ładowania wylewki — po prostu nie ma fallbacku gdy model się pomyli.

### 1.2 Tryby pracy

**Heating (zima):** UFH grzeje wylewkę, split dogrewa powietrze gdy UFH nie nadąża. Split **nigdy nie chłodzi** w reakcji na lekki overshoot — jeśli podłogówka nagrzeje pokój do 23°C przy setpoincie 22°C, system czeka.

**Cooling (lato):** UFH chłodzi wylewkę (Aquarea w trybie cool), split schładza powietrze gdy UFH nie nadąża. Split **nigdy nie grzeje** w reakcji na lekki undershoot. Role odwrócone, asymetria ta sama.

**Deadband:** Gdy |T_room − T_set| < deadband (np. 0.5°C) — split nie wchodzi w żadnym trybie.

**Przełączanie heat/cool:** Automatyczne na podstawie T_outdoor lub ręczne sezonowe. Tryb "auto" pozwala na przełączanie w ciągu dnia (wiosna/jesień: zimna noc → ciepły dzień).

### 1.3 Dodatkowe ograniczenie w trybie cooling — punkt rosy

Temperatura powierzchni podłogi **nie może spaść poniżej T_dew** (temperatura punktu rosy), bo kondensacja zniszczy podłogę. To jedyny przypadek gdzie **wilgotność powietrza jest krytycznym pomiarem** — wymagany czujnik wilgotności w każdym pokoju z floor cooling.

T_dew ≈ T_air − (100 − RH) / 5  (przybliżenie Magnus)

Constraint: **T_floor_surface ≥ T_dew + 2°C** (margines bezpieczeństwa)

### 1.4 Asymetria mocy w trybie cooling

Floor cooling ma **mniejszą moc** niż floor heating (~30–40 W/m² vs ~50–80 W/m²) z powodu mniejszego ΔT między podłogą a powietrzem. Split w trybie cool ma pełną moc. To oznacza, że latem split będzie aktywniejszy niż zimą.

### 1.5 Patologia do uniknięcia — priority inversion

Split grzeje/chłodzi pokój w minuty → termostat zadowolony → podłogówka się zamyka → wylewka traci temperaturę → split pracuje non-stop jako primary. COP spada, koszty rosną, podłogówka jest martwa.

**Źródło:** Tekmar Essay E006 "Control of Radiant Floor Heating Zones" (Watts) — opisuje dokładnie tę patologię i rozwiązanie przez PWM na wolnym źródle.

---

## 2. Stan wiedzy — co mówi nauka i branża

### 2.1 Problem jest dobrze rozpoznany

Koordynacja wolnego źródła radiacyjnego z szybkim konwekcyjnym to znany problem w HVAC. Rozwiązany komercyjnie (Tekmar, Ekinex KNX), akademicko (hybridGEOTABS), ale **brak zunifikowanej implementacji open-source**.

### 2.2 Kluczowe źródła

#### Akademickie

| Paper | Autorzy | Rok | Kluczowy wynik |
|-------|---------|-----|----------------|
| Cloud-based MPC for GEOTABS | Drgoňa, Picard, Helsen | 2020 | Field test: 53.5% oszczędności energii, 36.9% poprawa komfortu vs rule-based. 24h horyzont, 1h krok. Journal of Process Control. |
| Fan-coil vs radiant floor comparison | Atienza-Márquez et al. | 2017 | RF+FC najlepszy tradeoff. Fan-coil 62–70% mocy przy rozruchu, spada gdy wylewka się nagrzeje. τ₆₃ podłogówki = 4.4–4.7h. Energy and Buildings. |
| Hierarchical MIMO MPC | Killian & Kozek | 2018 | Dwupoziomowy MPC: górny = wolna dynamika budynku, dolny = szybkie przełączanie komponentów. Applied Energy. |
| MPC for A2W HP + radiant floor | Rastegarpour et al. | 2019 | Porównanie SMPC, LTV-MPC, NMPC. Wolna dynamika czyni nawet NMPC obliczalnym w real-time. |
| MPC + weather forecasts | Oldewurtel et al. | 2012 | Stochastyczny MPC z affine disturbance feedback. Chance constraints → SOCP. <1% nadwyżka kosztu vs deterministic przy zachowaniu komfortu. Energy and Buildings. |
| Singular perturbation for buildings | Gupta et al. | 2017 | Dekompozycja na wolny (powłoka) i szybki (powietrze) podsystem. Osobne LQR dają wynik ~= pełny LQR przy ułamku kosztu obliczeniowego. |
| RC model for pipe-embedded floors | Liu et al. | 2016 | Star-type RC model wylewki z rurami. Błąd <5.5% vs FEM. Energy and Buildings. |
| Radiant floor MPC optimization | Li et al. | 2021 | MPC redukuje czas odpowiedzi podłogówki o 56%, COP HP +24.5% vs PID. Energy. |

#### Komercyjne

| Producent | Produkt | Podejście |
|-----------|---------|-----------|
| **Tekmar** (Watts) | 557 thermostat | PWM na wolnym źródle. Stage 2 (szybkie) wchodzi dopiero przy 100% duty cycle Stage 1. 3 czujniki: pokój, wylewka, outdoor. |
| **Ekinex** | EK-EQ2-TP (KNX) | Offset setpointów. Fan-coil jako auxiliary stage, wyłącza się gdy główny system radiacyjny daje radę sam. |

#### Formalny framework

| Framework | Źródło | Opis |
|-----------|--------|------|
| **hybridGEOTABS** | EU Horizon 2020, KU Leuven/EnergyVille | Dwuwarstwowy MPC: supervisory (24–48h) + lokalne PI. Testowany w 32-strefowym budynku biurowym. |
| **TACO toolchain** | Jorissen, Boydens, Helsen 2018 | Linearyzacja modelu Modelica → SLP/SQP. Bolza optimal control problem. |

### 2.3 Kluczowe wnioski z literatury

1. **Model 2. rzędu (2R2C) wystarczy** — 4R4C nie daje proporcjonalnej poprawy w MPC (Sourbron & Verhelst 2013)
2. **Optymalny podział obciążenia maksymalizuje udział wolnego źródła** — split pokrywa tylko resztkowe szczyty (Sharifi et al. 2022)
3. **Horyzont predykcji 24h jest konieczny** dla wolnego źródła — krótszy traci zdolność pre-ładowania masy termicznej
4. **Zasada minimum Pontryagina daje wynik bang-bang** — ładuj wylewkę gdy przyszły koszt > koszt teraz, split tylko przy zagrożeniu komfortu
5. **Proste reguły heurystyczne przybliżają 80% optimum** — nie trzeba pełnego MPC żeby mieć duże korzyści
6. **Night setback jest kontrproduktywny** przy wysokiej bezwładności termicznej

---

## 3. Model matematyczny

### 3.1 Sieć RC — analogia elektryczna

Temperatura = napięcie, przepływ ciepła = prąd, opór termiczny R [K/W] = rezystancja, pojemność cieplna C [J/K] = kondensator.

Równanie węzła: **C_j · dT_j/dt = Σ (T_h − T_j)/R_{h,j} + Q_j**

### 3.2 Model 3R3C — minimalna struktura dla dwóch źródeł

Trzy zmienne stanu: T_air (powietrze), T_slab (wylewka), T_wall (powłoka).

```
C_air  · dT_air/dt  = (T_slab − T_air)/R_sf + (T_wall − T_air)/R_wi
                     + (T_out − T_air)/R_ve + Q_conv + Q_int + f_conv·Q_sol

C_slab · dT_slab/dt = (T_air − T_slab)/R_sf + (T_ground − T_slab)/R_ins + Q_floor

C_wall · dT_wall/dt = (T_air − T_wall)/R_wi + (T_out − T_wall)/R_wo + f_rad·Q_sol
```

### 3.3 Postać macierzowa ẋ = Ax + Bu + Ed

**x** = [T_air, T_slab, T_wall]ᵀ — zmienne stanu
**u** = [Q_conv, Q_floor]ᵀ — wejścia sterujące
**d** = [T_out, Q_sol, Q_int]ᵀ — zakłócenia

**Macierz B (3×2) — pokój z UFH + split:**

```
B = [ 1/C_air    0        ]   ← Q_conv wchodzi TYLKO do powietrza
    [ 0          1/C_slab  ]   ← Q_floor wchodzi TYLKO do wylewki
    [ 0          0         ]
```

**Macierz B (3×1) — pokój UFH only (bez splita):**

```
B = [ 0        ]
    [ 1/C_slab ]   ← jedyne wejście sterujące
    [ 0        ]
```

**To jest serce problemu** — dwa wejścia sterujące trafiają w strukturalnie różne węzły. W konfiguracji UFH-only model upraszcza się do SISO (single-input single-output), ale predykcja i pre-ładowanie wylewki stają się jeszcze ważniejsze — bo nie ma szybkiego fallbacku gdy model się pomyli.

### 3.4 Typowe wartości numeryczne (pokój 20 m²)

| Parametr | Wartość | Znaczenie |
|----------|---------|-----------|
| C_air | ~60 kJ/K | Masa powietrza (ρ·c·V) |
| C_slab | ~3250 kJ/K | Wylewka 80mm (2300 × 880 × 0.08 × 20) |
| C_wall | 500–5000 kJ/K | Masa powłoki (zależy od konstrukcji) |
| R_sf | 0.01 K/W | Konwekcja podłoga→powietrze |
| R_ins | 0.005–0.02 K/W | Izolacja pod wylewką |
| R_ve | 0.01–0.05 K/W | Wentylacja/infiltracja (w tym VTR300) |

**Stosunek C_slab/C_air ≈ 54:1** — źródło separacji skal czasowych.

### 3.5 Funkcje przenoszenia (domena częstotliwościowa)

**Podłogówka → T_room:** G_floor(s) ≈ K_f · e^(−θ_f·s) / [(τ₁s+1)(τ₂s+1)]
- τ₁ ≈ 3–6h, τ₂ ≈ 0.5–2h, θ_f ≈ 15–45 min, K_f ≈ 0.005–0.02 °C/W

**Split → T_room:** G_conv(s) ≈ K_c / (τ_c·s + 1)
- τ_c ≈ 5–15 min, K_c ≈ 0.003–0.01 °C/W

Różnica rzędu (2. vs 1.) i stałych czasowych (godziny vs minuty) to **matematyczna sygnatura problemu**.

---

## 4. Podejścia do sterowania

### 4.1 Kaskadowy PID

- Pętla zewnętrzna: T_room → setpoint T_slab
- Pętla wewnętrzna: T_slab → pozycja zaworu VdMot
- Split: równoległa korekta na błędzie T_room z histerezą

Problem: pętla wewnętrzna wolniejsza od zewnętrznej (odwrotność klasycznej kaskady). Split kompensuje tę inwersję.

### 4.2 MPC (Model Predictive Control)

```
min J = Σ [w_comfort · (T_room − T_set)² + c_elec · P_elec · Δt + w_Δu · ‖Δu‖²]
```

**Składniki funkcji kosztu:**
- Komfort — kwadratowa kara za odchylenie od setpointu
- Koszt energii — cena spot × zużycie (P_elec = Q/COP)
- Zużycie aktuatorów — kara za częste przełączanie

**Ograniczenia:**
- T_floor_surface ≤ 34°C (PumpAhead operational limit; EN 1264 specifies 29°C for normal conditions, but 34°C is acceptable at extreme outdoor temperatures)
- T_floor_surface ≥ T_dew + 2°C (cooling, ochrona przed kondensacją)
- 0 ≤ u_floor ≤ 1 (zawór 0–100%, kierunek heat/cool z trybu HP)
- Heating mode: u_conv ≥ 0 (split: tylko grzanie)
- Cooling mode: u_conv ≤ 0 (split: tylko chłodzenie)
- Deadband: u_conv = 0 gdy |T_room − T_set| < 0.5°C
- T_min ≤ T_room ≤ T_max (soft, ze zmienną slack ε)

**Horyzont:** 24h @ 15 min = 96 kroków × 2 wejścia = 192 zmienne decyzyjne → mały QP.

### 4.3 Zasada minimum Pontryagina

Sterowanie optymalne jest **bang-bang**:
- Podłogówka: ładuj masę termiczną gdy przyszły koszt braku ciepła > koszt energii teraz
- Split: włącz tylko gdy temperatura zaraz naruszy granicę komfortu

### 4.4 Dekompozycja perturbacji osobliwej

Stosunek ε = C_air/C_slab ≪ 1 definiuje naturalną separację skal. Wolny podsystem optymalizuje trajektorię wylewki. Szybki podsystem (boundary layer) koryguje przejściowe odchylenia przez split. Composite controller u = u_slow + u_fast przybliża optimum pełnego rzędu do O(ε).

---

## 5. Dane wejściowe algorytmu

### 5.1 Pomiary ciągłe (czujniki)

**Per pokój (×8):**
- T_room — temperatura powietrza (co 30–60s)
- RH_room — wilgotność względna (wymagana dla trybu cooling — constraint T_dew)
- T_floor_surface — opcjonalnie (ochrona 34°C / T_dew i lepsza identyfikacja RC)

**Podłogówka (HeishaMon + VdMot):**
- Pozycja zaworu per pętla (0–100%)
- T_supply, T_return — zasilanie/powrót
- Przepływ wody (jeśli dostępny)

**Pompa ciepła (HeishaMon):**
- T_outdoor
- Stan pracy: grzanie / CWU / idle / defrost
- P_electric [W]
- T_CWU (temperatura zasobnika)

**Splity Mitsubishi (CN105, ×6):**
- Stan: off / heat / idle
- T_setpoint aktualny
- P_electric (Shelly PM, opcjonalnie)

### 5.2 Dane zewnętrzne (API)

**Pogoda (Open-Meteo, co 1h, 48h ahead):**
- T_outdoor forecast
- GHI — promieniowanie słoneczne [W/m²]
- Zachmurzenie

**Taryfa (faza 6):**
- Cena spot PLN/kWh per godzina (energetycznykompas.pl)

### 5.3 Parametry statyczne (konfiguracja)

**Per pokój:**
- T_setpoint (input_number HA)
- Orientacja okien (N/S/E/W)
- Powierzchnia okien [m²]
- Powierzchnia podłogi [m²]
- Czy ma split (bool)

**Budynek:**
- Współczynnik g okien (~0.5–0.7)
- Grubość wylewki [mm]

**Sprzęt:**
- Q_max per split [kW]
- COP lookup table Aquarei = f(T_outdoor, T_supply)
- Pojemność zasobnika CWU [l]

### 5.4 Parametry identyfikowane (z danych historycznych)

Per pokój:
- R_sf, R_env, R_ins — opory termiczne
- C_air, C_slab — pojemności cieplne
- τ_slow, τ_fast — wynikowe stałe czasowe

### 5.5 Czego NIE potrzebujemy

- CO2 — sterowanie wentylacją, przezroczyste dla PumpAhead
- Obecność domowników — nice-to-have w przyszłości, nie w core

### 5.6 Minimum krytyczne

**T_room per pokój + HeishaMon + Open-Meteo** — reszta poprawia dokładność.

---

## 6. Architektura techniczna

### 6.1 Forma docelowa

Custom integration dla Home Assistant (HACS-dystrybutowalny).

```
custom_components/pumpahead/
├── manifest.json          # numpy, cvxpy w requirements
├── __init__.py            # async_setup, coordinator
├── climate.py             # climate entity per pokój
├── coordinator.py         # DataUpdateCoordinator — co 5 min
├── model.py               # 2R2C/3R3C state-space, predykcja
├── optimizer.py           # QP solver (cvxpy + OSQP)
├── identifier.py          # identyfikacja parametrów RC
├── weather.py             # Open-Meteo forecast client
├── config_flow.py         # UI konfiguracji
└── tests/
    ├── test_model.py
    ├── test_optimizer.py
    ├── test_identifier.py
    └── simulator/         # symulator budynku do integration testów
```

### 6.2 Cykl sterowania

```
Co 5–15 min (DataUpdateCoordinator):
  1. Zbierz stany: T_room[], RH_room[], T_slab, T_supply, T_outdoor, stan HP
  2. Określ tryb: heating / cooling / auto (na podstawie T_outdoor lub konfiguracji)
  3. Oblicz T_dew per pokój (jeśli cooling)
  4. Zaktualizuj estymator stanu (Kalman filter)
  5. Pobierz forecast: pogoda 48h, cena spot 24h (gdy G14)
  6. Rozwiąż QP: u_floor[], u_conv[] na horyzont 24h (z odpowiednimi constraints per tryb)
  7. Zastosuj pierwszy krok: VdMot valve %, split on/off + setpoint + hvac_mode
  8. Powtórz (receding horizon)
```

### 6.3 Safety layer (niezależny od algorytmu, YAML w HA)

- T_floor_surface > 34°C → zamknij zawór (hard override, heating)
- T_floor_surface < T_dew + 2°C → zamknij zawór (hard override, cooling)
- T_room < T_min_emergency → włącz split heat (fallback)
- T_room > T_max_emergency → włącz split cool (fallback)
- Python process nie odpowiada > 15 min → fallback na krzywą grzewczą HP
- Stan HP = CWU → nie licz na moc grzania (algorytm musi wiedzieć)

---

## 7. Plan budowy — fazy

### Faza 1 — UFH PID heating + zbieranie danych

**Cel:** Działające sterowanie podłogówką w trybie grzania, zbieranie danych do identyfikacji.

**Zakres:**
- PID per pokój: T_room → valve position (0–100%)
- Valve floor minimum (15–20%) w sezonie grzewczym
- Logowanie: T_room, RH_room, T_outdoor, valve_pos, T_supply, T_return co 1 min
- Brak splita, brak modelu, brak predykcji

**Czas:** 2–4 tygodnie eksploatacji (potrzeba zmienności danych)

### Faza 2 — Identyfikacja modelu RC per pokój

**Cel:** Parametry 2R2C dla każdego pokoju.

**Zakres:**
- Offline fit w Jupyter: scipy.optimize.minimize na zebranych danych
- Walidacja: predykcja 6h/12h/24h vs rzeczywistość
- Wynik: R_sf, R_env, C_air, C_slab per pokój

**Narzędzia:** numpy, scipy, matplotlib, opcjonalnie DarkGreyBox

### Faza 3 — Drugie źródło — splity heating

**Cel:** Koordynacja UFH + split w trybie grzania, bez priority inversion.

**Zakres:**
- Model 2R2C z dwoma wejściami (B matrix)
- Split wchodzi tylko gdy model przewiduje, że UFH sam nie dojedzie do setpointu
- Anti-takeover: jeśli split > 30 min/h → wymuś podniesienie UFH
- Opcjonalnie: prosty MPC (cvxpy) lub rule-based na bazie modelu

### Faza 4 — Koordynacja z CWU

**Cel:** Algorytm wie o przełączeniach HP między grzaniem a CWU.

**Zakres:**
- Monitorowanie stanu HP (HeishaMon: grzanie/CWU/idle/defrost)
- Planowanie cykli CWU (np. rano + wieczór) z uwzględnieniem zapotrzebowania grzania
- Algorytm nie odpala splita "na pomoc" gdy HP przeszła na CWU

### Faza 5 — Chłodzenie (UFH cool + splity cool)

**Cel:** Pełne sterowanie w trybie cooling z ochroną przed kondensacją.

**Zakres:**
- Odwrócona logika: UFH chłodzi bazę, split doraźna korekta
- Constraint T_dew: T_floor_surface ≥ T_dew + 2°C (wymaga RH_room)
- Asymetria mocy: floor cooling ~30–40 W/m² vs heating ~50–80 W/m²
- Deadband: split nie wchodzi gdy |T_room − T_set| < 0.5°C
- Tryb auto: przełączanie heat/cool na podstawie T_outdoor lub ręczne

### Faza 6 — Pogoda + nasłonecznienie (feedforward)

**Cel:** Predykcyjne ładowanie/rozładowywanie wylewki, antycypacja zysków solarnych.

**Zakres:**
- Open-Meteo API: T_outdoor + GHI (Global Horizontal Irradiance) 48h ahead
- Model zysków solarnych: Q_sol = g × A_okno × GHI × f(orientacja, godzina)
- Feedforward: przesunięcie setpointu wylewki w przód (pre-heating / pre-cooling)
- Ochrona przed przegrzaniem solarnym (reduce UFH / start floor cooling zanim słońce wejdzie)

### Faza 7 — Taryfy dynamiczne G14

**Cel:** Optymalizacja kosztów energii z ceną spot.

**Zakres:**
- Integracja energetycznykompas.pl (cena PLN/kWh per godzina)
- c_elec(t) w funkcji kosztu MPC
- Ładowanie/rozładowywanie wylewki w tanich godzinach
- CWU scheduling do tanich godzin
- Pełny MPC z cvxpy + OSQP

---

## 8. Roadmapa implementacji

Sekcja 7 opisuje **co** budujemy (fazy produktowe). Ta sekcja opisuje **jak** — od pierwszej linii kodu do produkcji. Każdy milestone dostarcza działającą wartość i jest testowalny niezależnie.

### Milestone 0 — Fundament: model RC + symulator

**Bez tego nie ruszysz dalej.** Symulator to test harness dla całego projektu.

**Deliverables:**
- `model.py` — klasa `RCModel` (2R2C i 3R3C), metody `step()`, `predict()`, `steady_state()`
- `simulator.py` — klasa `BuildingSimulator` z wieloma pokojami, weather input, CWU interrupts, sensor noise
- `weather.py` — `SyntheticWeather` (step, ramp, sinusoid) + `CSVWeather` (parsowanie plików)
- `scenarios.py` — dataclasses `RoomConfig`, `SimScenario`, `BuildingParams`
- `metrics.py` — `SimMetrics` (comfort_pct, split_runtime, energy_kwh...)
- Unit testy: model convergence, steady-state, energy conservation
- Scenario testy: `steady_state_heating` z known-good wynikiem (analitycznym)

**Zależności:** Brak. Czysty Python + numpy.
**Warunek ukończenia:** `pytest tests/` zielone, wykresy z matplotlib pokazują sensowne krzywe T_room/T_slab.

### Milestone 1 — Kontroler PID dla UFH-only

**Pierwszy algorytm sterowania — prosty PID na zawór podłogówki.** Testowany na symulatorze, nie na prawdziwym domu.

**Deliverables:**
- `controller.py` — klasa `PIDController` z anti-windup (back-calculation)
- `pumpahead.py` — klasa `PumpAheadController` opakowująca PID per pokój, z valve floor minimum
- Scenario testy: `ufh_only_steady`, `ufh_only_cold_snap`, `ufh_only_cwu_interrupt`
- Strojenie PID na symulatorze (parametric sweep po Kp, Ki)
- Wizualizacja: T_room, T_slab, valve_pos vs czas

**Zależności:** Milestone 0
**Warunek ukończenia:** Scenariusz `ufh_only_steady` → komfort >95%, `cold_snap` → T_room nie spada poniżej T_set − 1.5°C.

### Milestone 2 — Integracja z Home Assistant (read-only)

**Połączenie symulatora z prawdziwym światem — ale jeszcze bez sterowania.**

**Deliverables:**
- `custom_components/pumpahead/` — scaffold integracji HA
- `coordinator.py` — `DataUpdateCoordinator` czytający T_room, T_outdoor, T_supply, valve_pos, stan HP
- `manifest.json` z zależnościami (numpy)
- Shadow mode: algorytm liczy u_floor co 5 min, loguje do HA jako sensor (`sensor.pumpahead_salon_recommended_valve`), ale **nie steruje**
- Dashboard card: porównanie "co PumpAhead by zrobił" vs aktualny stan

**Zależności:** Milestone 1 + działające czujniki pokojowe + HeishaMon
**Warunek ukończenia:** Sensory PumpAhead w HA logują wartości 24/7 przez min. tydzień. Wykresy wyglądają sensownie.

### Milestone 3 — Identyfikacja parametrów RC

**Model uczy się domu z zebranych danych.**

**Deliverables:**
- `identifier.py` — fit 2R2C z danych HA (`scipy.optimize.minimize`, bound constraints na R i C)
- Jupyter notebook: eksploracja danych, wizualizacja fit, walidacja predykcji 6h/12h/24h
- Unit testy: syntetyczne dane z known R,C → identyfikacja odzyskuje parametry ±10%
- Wynik per pokój: `RCParams(R_sf, R_env, C_air, C_slab)` + raport jakości fitu

**Zależności:** Milestone 2 (min. 2–4 tygodnie danych z shadow mode)
**Warunek ukończenia:** Predykcja 12h z identified params ma RMSE < 0.5°C na danych walidacyjnych.

### Milestone 4 — PID z identified model → live UFH control

**Pierwszy moment gdy PumpAhead steruje prawdziwym domem.** Tylko podłogówka, tylko jeden pokój na start.

**Deliverables:**
- `climate.py` — climate entity per pokój (`ClimateEntity` z `HVACMode.HEAT`)
- PID z parametrami RC z Milestone 3 (lepiej dobrane Kp, Ki niż generic)
- Safety layer w YAML: T_floor > 34°C → override, fallback na krzywą HP jeśli Python padnie
- Rollout: jeden pokój → tydzień obserwacji → kolejne pokoje

**Zależności:** Milestone 3
**Warunek ukończenia:** Jeden pokój sterowany przez PumpAhead przez 7 dni, komfort ≥ 90%, zero safety overrides.

### Milestone 5 — Koordynacja ze splitem (wybrane pokoje)

**Dodanie szybkiego źródła — core problemu dual-source.**

**Deliverables:**
- Rozszerzenie `PumpAheadController` o moduł split coordination (aktywowany gdy `RoomConfig.has_split == True`)
- Logika boost: split wchodzi gdy model przewiduje że UFH sam nie dojedzie
- Anti-takeover: valve floor + runtime monitoring
- Deadband: split nie reaguje na |error| < 0.5°C
- Scenario testy: `cold_snap` (z split), `priority_inversion` (test że nie występuje), `ufh_only_vs_dual`

**Zależności:** Milestone 4
**Warunek ukończenia:** Scenariusz tygodniowy → split runtime < 15%, komfort > 95% w pokojach z dual source. Pokoje UFH-only nadal działają bez regresji.

### Milestone 6 — Koordynacja z CWU

**Algorytm wie że HP przełącza się na CWU i nie panikuje.**

**Deliverables:**
- Monitorowanie `sensor.heishamon_operating_mode` (heat/CWU/idle/defrost)
- Scheduler: planowanie CWU w oknach niskiego zapotrzebowania na grzanie
- Logika: gdy HP → CWU, nie włączaj splita jeśli T_room > T_set − 1.0°C
- Pre-charge wylewki przed planowanym CWU
- Scenario testy: `cwu_interrupt`, `cwu_no_unnecessary_split`

**Zależności:** Milestone 5
**Warunek ukończenia:** Podczas CWU → zero false-alarm split activations, T_room drop < 0.5°C.

### Milestone 7 — Upgrade PID → MPC (UFH)

**Przejście z reaktywnego PID na predykcyjny MPC.** Największy skok w jakości sterowania.

**Deliverables:**
- `optimizer.py` — QP solver (cvxpy + OSQP), horyzont 24h, krok 15 min
- Kalman filter do estymacji stanu (T_slab nie jest bezpośrednio mierzony)
- `weather.py` rozszerzony o Open-Meteo forecast API (48h ahead)
- Model zysków solarnych: Q_sol = g × A_okno × GHI × f(orientacja)
- Feedforward: pre-heating wylewki przed mrozem, pre-reduction przed słońcem
- Scenario testy: `solar_overshoot_south` → MPC redukuje overshoot vs PID, `cold_snap` → MPC pre-charges

**Zależności:** Milestone 6 + Open-Meteo API
**Warunek ukończenia:** A/B test na symulatorze: MPC vs PID na full_year_2025 → MPC lepsza comfort_pct LUB niższe energy_kwh (lub oba).

### Milestone 8 — Chłodzenie

**Odwrócona logika + constraint T_dew.**

**Deliverables:**
- Tryb cooling w modelu RC (Q_floor < 0, Q_conv < 0)
- Constraint T_dew w optimizerze: T_floor_surface ≥ T_dew + 2°C
- Czujnik wilgotności → T_dew calculation
- Tryb auto: przełączanie heat/cool na podstawie T_outdoor (z histerezą)
- Safety YAML: T_floor < T_dew + 2°C → zamknij zawór
- Scenario testy: `dew_point_stress`, `hot_july`, `spring_swing`

**Zależności:** Milestone 7
**Warunek ukończenia:** Scenariusz `hot_july` → zero condensation events, comfort > 90%.

### Milestone 9 — Taryfy dynamiczne G14

**Ostatni wymiar optymalizacji — koszt energii.**

**Deliverables:**
- Integracja energetycznykompas.pl → `sensor.electricity_price_spot`
- `c_elec(t)` w funkcji kosztu MPC
- Logika: ładuj wylewkę w tanich godzinach, CWU w tanich godzinach
- Constraint: komfort nadal priorytetem — taryfa nie może powodować T_room < T_min
- Scenario testy: `price_spike`, full year z realną ceną spot

**Zależności:** Milestone 8 + przejście na taryfę G14
**Warunek ukończenia:** Symulacja full_year z ceną spot → oszczędność ≥ 10% vs stała cena, bez pogorszenia komfortu.

### Milestone 10 — Produkcja: HACS release

**Wszystko spięte, udokumentowane, gotowe do udostępnienia.**

**Deliverables:**
- Config flow UI (dodawanie pokoi, parametrów, flag has_split)
- Dokumentacja użytkownika (README, setup guide)
- HACS manifest, CI/CD (GitHub Actions: pytest + linting)
- Dashboard cards: per-room temperatura, valve %, tryb, predicted vs actual
- Auto-identification: periodic re-fit parametrów RC z najnowszych danych

**Zależności:** Milestone 9
**Warunek ukończenia:** Cały dom Huberta działa na PumpAhead min. miesiąc. HACS instalowalny.

### Diagram zależności

```
M0 (model+symulator)
 └→ M1 (PID UFH)
     └→ M2 (HA read-only)
         └→ M3 (identyfikacja RC)
             └→ M4 (live UFH PID)
                 └→ M5 (split coordination)
                     └→ M6 (CWU)
                         └→ M7 (MPC)
                             └→ M8 (cooling)
                                 └→ M9 (G14 tariff)
                                     └→ M10 (HACS release)
```

Linia jest prosta — każdy milestone buduje na poprzednim. Nie ma rozgałęzień. To celowe: złożoność rośnie monotonicznie, a każdy krok dostarcza testowalną wartość.

### Co jest użyteczne po każdym milestone

| Po milestone | Co działa |
|---|---|
| M0 | Symulator do eksperymentów offline |
| M1 | Algorytm testowany na symulatorze — wiesz że PID działa zanim kupisz czujniki |
| M2 | Shadow mode w HA — widzisz co PumpAhead *by zrobił* |
| M3 | Znasz parametry termiczne swojego domu — wartość sama w sobie |
| M4 | **Podłogówka sterowana przez PumpAhead** — pierwszy real value |
| M5 | **Splity skoordynowane z podłogówką** — koniec priority inversion |
| M6 | HP nie traci ciepła na CWU w najgorszym momencie |
| M7 | **Predykcyjne sterowanie** — dom grzeje się zanim będzie zimno |
| M8 | Pełen cykl roczny heat+cool |
| M9 | Optymalizacja rachunków za prąd |
| M10 | Inni mogą tego użyć |

---

## 9. Podejście do developmentu

### 9.1 Hybrid: TDD na komponentach + symulator jako integration test

Czysty TDD sprawdza się na warstwie obliczeniowej, ale algorytm sterowania wymaga **symulacji budynku** jako test harness — nie da się unit-testować czy pokój się przegrzeje.

### 9.2 Warstwa 1: Unit testy (TDD, pytest)

Testowalne bez symulacji:

| Komponent | Przykładowe testy |
|-----------|-------------------|
| `model.py` (RC state-space) | Dany stan x₀ i wejście u, po Δt stan x₁ zgadza się z analitycznym rozwiązaniem |
| | Steady-state: stałe u → T_room konwerguje do poprawnej wartości |
| | Symetria: Q_floor i Q_conv tego samego W dają te same °C w steady-state (z dokładnością do R) |
| `optimizer.py` (QP solver) | Dany prosty scenariusz 2-krokowy → rozwiązanie = ręcznie obliczone optimum |
| | Constraint satisfaction: T_floor ≤ 34°C nigdy nie przekroczone |
| | Heat-only: u_conv ≥ 0 zawsze |
| | Przy zerowym koszcie energii → pełna moc, minimum dyskomfortu |
| | Przy nieskończonym koszcie energii → zero mocy |
| `identifier.py` | Syntetyczne dane z known R, C → identyfikacja odzyskuje parametry (±10%) |
| | Szum pomiarowy → parametry nadal sensowne |
| `weather.py` | Parsowanie odpowiedzi Open-Meteo → prawidłowe Q_sol per orientacja |

### 9.3 Warstwa 2: Symulator budynku (simulation-driven development)

**Symulator = "cyfrowy bliźniak" domu Huberta.** Model 3R3C z known ground-truth parametrami + dane pogodowe + generator zakłóceń. Kontroler steruje symulatorem zamiast prawdziwym domem. Tydzień symulacji z krokiem 1 min = 10 080 iteracji mnożenia macierzy 3×3 → **<1 sekundy** na OptiPlexie. Rok z MPC co 15 min → ~1 minuta.

#### Architektura symulatora

```python
# Core loop — cały test harness
sim = BuildingSimulator(
    rooms=scenario.rooms,
    params=scenario.building_params,
    weather=scenario.weather_source,
)
ctrl = PumpAheadController(config=scenario.controller_config)

log = SimulationLog()
for t in range(0, scenario.duration_minutes):
    measurements = sim.get_measurements(noise=scenario.sensor_noise)
    actions = ctrl.step(measurements, t)
    sim.apply(actions)
    log.append(t, measurements, actions)

return log  # → assercje, wykresy, metryki
```

#### Parametryzacja scenariuszy

Scenariusz = **budynek × pogoda × tryb × czas trwania**. Każdy wymiar wymienny niezależnie.

```python
@dataclass
class RoomConfig:
    name: str
    area_m2: float
    params: RCParams                   # R_sf, R_env, C_air, C_slab per pokój
    windows: list[WindowConfig]        # orientacja, powierzchnia, g-value
    has_split: bool = False            # ← kluczowe: split opcjonalny per pokój
    split_power_kw: float | None = None
    ufh_loops: int = 1

@dataclass
class SimScenario:
    name: str
    # Budynek
    rooms: list[RoomConfig]           # lista pokoi — każdy z has_split flag
    building_params: BuildingParams    # R_env, grubość wylewki, okna...
    # Pogoda
    weather_source: WeatherSource      # syntetyczna, plik CSV, lub API
    # Sterowanie
    controller_config: ControllerConfig
    mode: Literal["heating", "cooling", "auto"]
    # Czas
    duration: timedelta
    dt: timedelta = timedelta(minutes=1)
    # Zakłócenia
    sensor_noise: float = 0.1         # ±°C szum na czujnikach
    cwu_schedule: list[CWUCycle] | None = None
```

#### Profile budynków

```python
BUILDING_PROFILES = {
    "modern_bungalow": {
        "R_env": 0.05, "C_slab": 3250, "C_air": 60,
        "screed_mm": 80, "insulation": "good",
        "rooms": MODERN_BUNGALOW_ROOMS,  # 8 pokoi z rzeczywistymi parametrami
    },
    "well_insulated": {
        "R_env": 0.08, "C_slab": 3250, "C_air": 60,
        "screed_mm": 80, "insulation": "excellent",
    },
    "leaky_old_house": {
        "R_env": 0.02, "C_slab": 2000, "C_air": 60,
        "screed_mm": 50, "insulation": "poor",
    },
    "thin_screed": {
        "R_env": 0.05, "C_slab": 1600, "C_air": 60,
        "screed_mm": 40, "insulation": "good",
    },
    "heavy_construction": {
        "R_env": 0.05, "C_slab": 4800, "C_air": 60,
        "screed_mm": 120, "insulation": "good",
    },
}
```

#### Źródła pogody (wymienne)

```python
class WeatherSource(Protocol):
    def get(self, t_minutes: int) -> WeatherPoint:
        """Zwraca T_out, GHI, wind_speed, RH dla danej minuty."""
        ...

# 1. Syntetyczna — do unit-testów i edge case'ów
class SyntheticWeather(WeatherSource):
    """Generuje pogodę z parametrów: T_mean, T_amplitude, sunrise, GHI_peak..."""

# 2. Z pliku CSV — realne dane historyczne
class CSVWeather(WeatherSource):
    """Wczytuje CSV z kolumnami: timestamp, T_out, GHI, RH, wind."""

# 3. Open-Meteo Historical API — pobiera i cachuje
class OpenMeteoHistorical(WeatherSource):
    """Pobiera dane historyczne z Open-Meteo API dla podanych lat/lat."""
    def __init__(self, lat: float, lon: float, 
                 start: date, end: date, cache_dir: Path): ...
```

#### Biblioteka scenariuszy

**Heating:**

| Scenariusz | Budynek | Pogoda | Czas | Co testuje |
|---|---|---|---|---|
| `steady_state_heating` | modern_bungalow | synth: T_out=0°C, GHI=0 | 48h | Stabilizacja ±0.3°C, split nigdy nie wchodzi |
| `cold_snap` | modern_bungalow | synth: step T_out=0→−15°C | 5 dni | Split wchodzi i wychodzi, UFH przejmuje |
| `cwu_interrupt` | modern_bungalow | synth: T_out=−5°C | 24h | HP off 45 min, split nie panikuje |
| `january_real` | modern_bungalow | CSV: Lubcza styczeń 2026 | 31 dni | Pełny miesiąc zimowy |

**Cooling:**

| Scenariusz | Budynek | Pogoda | Czas | Co testuje |
|---|---|---|---|---|
| `steady_state_cooling` | modern_bungalow | synth: T_out=32°C, GHI=0 | 48h | Stabilizacja, split nie grzeje |
| `solar_overshoot_south` | modern_bungalow | synth: marzec słoneczny, okna S | 3 dni | UFH redukuje PRZED overshoot |
| `hot_july` | modern_bungalow | CSV: Lubcza lipiec 2025 | 31 dni | Pełny miesiąc letni |
| `dew_point_stress` | modern_bungalow | synth: T_out=30°C, RH=85% | 48h | T_floor nigdy < T_dew + 2°C |

**Transition (wiosna/jesień):**

| Scenariusz | Budynek | Pogoda | Czas | Co testuje |
|---|---|---|---|---|
| `spring_swing` | modern_bungalow | CSV: Lubcza marzec 2026 | 14 dni | Heat/cool switching w ciągu dnia |
| `autumn_transition` | modern_bungalow | CSV: Lubcza październik 2025 | 14 dni | Płynne przejście heat→cool→heat |

**Full year:**

| Scenariusz | Budynek | Pogoda | Czas | Co testuje |
|---|---|---|---|---|
| `full_year_2025` | modern_bungalow | historical: Lubcza 2025 | 365 dni | Cały cykl roczny, metryki agregowane |
| `full_year_extreme` | leaky_old_house | historical: Lubcza 2025 | 365 dni | Worst case: słaba izolacja, realna pogoda |

**Edge cases:**

| Scenariusz | Budynek | Pogoda | Czas | Co testuje |
|---|---|---|---|---|
| `sensor_dropout` | modern_bungalow | synth: T_out=−5°C | 24h | T_room = NaN przez 30 min → fallback |
| `split_failure` | modern_bungalow | synth: cold snap | 5 dni | Split niedostępny → UFH sam |
| `price_spike` | modern_bungalow | synth: T_out=−5°C | 48h | Cena 3× rano, 0.5× w nocy |
| `all_rooms_simultaneous` | modern_bungalow | CSV: styczeń mroźny | 7 dni | 8 pokoi naraz, HP capacity sharing |

**UFH-only (pokoje bez splita — kluczowe, bo to większość pomieszczeń):**

| Scenariusz | Budynek | Pogoda | Czas | Co testuje |
|---|---|---|---|---|
| `ufh_only_steady` | modern_bungalow (no split) | synth: T_out=0°C | 48h | Stabilizacja samą podłogówką |
| `ufh_only_cold_snap` | modern_bungalow (no split) | synth: step 0→−15°C | 5 dni | Jak głęboko spada T_room bez szybkiego fallbacku |
| `ufh_only_solar_gain` | modern_bungalow (no split) | synth: marzec, okna S | 3 dni | Overshoot bez możliwości aktywnego chłodzenia splitami |
| `ufh_only_cwu_interrupt` | modern_bungalow (no split) | synth: T_out=−5°C | 24h | HP na CWU → jedyne źródło offline, brak splita na ratunek |
| `ufh_only_full_year` | modern_bungalow (no split) | historical: Lubcza 2025 | 365 dni | Roczna wydajność samej podłogówki — baseline |
| `ufh_only_vs_dual` | modern_bungalow | historical: Lubcza 2025 | 365 dni | Porównanie: te same pokoje z i bez splita — ile zyskujemy |

**Parametric sweep (porównanie budynków):**

| Scenariusz | Budynki | Pogoda | Co testuje |
|---|---|---|---|
| `insulation_sweep` | well_insulated, modern_bungalow, leaky_old_house | synth: T_out=−10°C | Jak R_env wpływa na split runtime |
| `screed_sweep` | thin_screed, modern_bungalow, heavy_construction | synth: cold snap | Jak C_slab wpływa na τ i overshoot |

#### Kryteria sukcesu (assertions w pytest)

```python
def assert_comfort(log, setpoint, band=0.5, min_pct=0.95):
    """T_room w paśmie ±band przez >min_pct czasu."""
    in_band = [abs(r.T_room - setpoint) < band for r in log]
    assert sum(in_band) / len(in_band) >= min_pct

def assert_no_priority_inversion(log, max_split_pct=0.15):
    """Split runtime < max_split_pct w steady-state."""
    split_on = [r.u_conv != 0 for r in log]
    assert sum(split_on) / len(split_on) < max_split_pct

def assert_floor_temp_safe(log):
    """T_floor ≤ 34°C (heating) i T_floor ≥ T_dew + 2°C (cooling)."""
    for r in log:
        assert r.T_floor <= 34.0, f"Floor too hot: {r.T_floor}°C at t={r.t}"
        if r.mode == "cooling":
            T_dew = r.T_room - (100 - r.RH) / 5
            assert r.T_floor >= T_dew + 2.0, f"Condensation risk at t={r.t}"

def assert_no_opposing_action(log):
    """Split nigdy nie działa przeciwnie do trybu."""
    for r in log:
        if r.mode == "heating":
            assert r.u_conv >= 0, f"Split cooling in heat mode at t={r.t}"
        elif r.mode == "cooling":
            assert r.u_conv <= 0, f"Split heating in cool mode at t={r.t}"

def assert_energy_vs_baseline(log, baseline_log, max_ratio=1.0):
    """Zużycie energii ≤ baseline."""
    e = sum(abs(r.Q_total) for r in log)
    e_base = sum(abs(r.Q_total) for r in baseline_log)
    assert e / e_base <= max_ratio
```

#### Metryki per symulacja

```python
@dataclass
class SimMetrics:
    comfort_pct: float          # % czasu w paśmie ±0.5°C
    max_overshoot: float        # max T_room − T_set [°C]
    max_undershoot: float       # max T_set − T_room [°C]
    split_runtime_pct: float    # % czasu pracy splita
    total_energy_kwh: float     # suma Q_floor + Q_conv [kWh]
    floor_energy_pct: float     # udział UFH w całości [%]
    mean_cop: float             # średni COP pompy ciepła
    condensation_events: int    # ile razy T_floor < T_dew + 2°C
    mode_switches: int          # ile przełączeń heat↔cool
```

#### Historyczne dane pogodowe — plan na przyszłość

Open-Meteo Historical API daje godzinowe dane pogodowe za darmo dla dowolnej lokalizacji i zakresu dat. Docelowa integracja:

```python
# Pobierz i zcachuj historię pogody dla Lubczy
weather = OpenMeteoHistorical(
    lat=50.69, lon=17.38,        # Lubcza
    start=date(2024, 1, 1),
    end=date(2025, 12, 31),
    cache_dir=Path("tests/weather_cache"),
)

# Interpolacja z godzinowej do minutowej
# Kolumny: T_out, GHI, RH, wind_speed, precipitation

# Użycie w scenariuszu
SCENARIOS["full_year_2025"] = SimScenario(
    name="full_year_2025",
    rooms=MODERN_BUNGALOW_ROOMS,
    building_params=BUILDING_PROFILES["modern_bungalow"],
    weather_source=OpenMeteoHistorical(lat=50.69, lon=17.38,
                                        start=date(2025,1,1), 
                                        end=date(2025,12,31)),
    mode="auto",
    duration=timedelta(days=365),
)
```

Open-Meteo Historical endpoint: `https://archive-api.open-meteo.com/v1/archive`
Parametry: `temperature_2m`, `global_tilted_irradiance`, `relative_humidity_2m`, `wind_speed_10m`

### 9.4 Warstwa 3: Shadow mode na żywym systemie

Przed przejęciem sterowania — algorytm działa **read-only**: czyta czujniki, liczy wyjścia, loguje je, ale NIE steruje. Porównanie "co bym zrobił" vs "co robi obecny PID" daje confidence przed go-live.

### 9.5 Workflow developmentu

```
1. RED:   napisz test (unit lub scenario)
2. GREEN: zaimplementuj minimalnie żeby przeszedł
3. REFACTOR: oczyść
4. SIMULATE: uruchom scenario suite na symulatorze
5. SHADOW: deploy read-only na żywym HA
6. LIVE: przejmij sterowanie jednym pokojem
7. SCALE: dodaj kolejne pokoje
```

### 9.6 Stack technologiczny

| Narzędzie | Rola |
|-----------|------|
| Python 3.12+ | Język implementacji |
| numpy | Model RC, algebra macierzowa |
| scipy | Identyfikacja parametrów (minimize), integracja ODE |
| cvxpy + OSQP | Solver QP dla MPC |
| pytest | Unit testy |
| matplotlib | Wizualizacja wyników symulacji |
| Home Assistant API | Integracja z HA (websocket/REST) |
| Jupyter | Eksploracja danych, identyfikacja offline |

---

## 10. Otwarte pytania

- [ ] Pojemność zasobnika CWU?
- [ ] COP lookup table Aquarei — dane z dokumentacji vs pomiar przez HeishaMon?
- [ ] Grubość wylewki per pomieszczenie — czy jednolita?
- [ ] Czy HeishaMon daje T_supply i T_return osobno?
- [ ] Powierzchnie i orientacje okien per pokój — do zmierzenia
- [ ] Modele wewnętrzne Mitsubishi — do spisania z tabliczek (6JW, 2JZ)
- [ ] Czujniki wilgotności — czy termostaty (MOES/Beok) mierzą RH? Jeśli nie, osobne czujniki dla trybu cooling
- [ ] Aquarea — tryb cooling: minimalna T_supply, moc chłodzenia, konfiguracja HeishaMon

---

## 11. Linki i zasoby

### Kluczowe papery

- Drgoňa et al. (2020) — MPC for GEOTABS, Journal of Process Control
- Atienza-Márquez et al. (2017) — RF + FC comparison, Energy and Buildings
- Killian & Kozek (2018) — Hierarchical MIMO MPC, Applied Energy
- Rastegarpour et al. (2019) — MPC for A2W HP + radiant floor
- Oldewurtel et al. (2012) — Stochastic MPC, Energy and Buildings
- Liu et al. (2016) — RC model for pipe-embedded floors, Energy and Buildings
- Li et al. (2021) — MPC for radiant floor optimization, Energy
- Sourbron & Verhelst (2013) — 2nd-order model sufficiency for MPC
- Gupta et al. (2017) — Singular perturbation for building control

### Narzędzia / repozytoria

- [ha-dual-smart-thermostat](https://github.com/swingerman/ha-dual-smart-thermostat) — closest HA integration (staging, timeouts)
- [Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat) — TPI + auto-learning
- [SAT](https://github.com/Alexwijn/SAT) — Smart Autotune Thermostat, PID + outdoor reset
- [haos_mpc](https://github.com/sebzuddas/haos_mpc) — MIMO MPC via HA websocket
- [roommind](https://github.com/snazzybean/roommind) — self-learning MPC + EKF
- [DarkGreyBox](https://github.com/bsoucisse/DarkGreyBox) — grey-box RC identification
- Tekmar Essay E006 — [watts.com](https://www.watts.com/dfsmedia/0533dbba17714b1ab581ab07a4cbb521/35982-source)
- Ekinex floor radiant system — [ekinex.com](https://www.ekinex.com/en/application-examples-hvac/floor-radiant-system.html)

### Standardy

- EN 1264 — max temperatura powierzchni podłogi (29°C strefy przebywania w normalnych warunkach; PumpAhead używa 34°C jako limitu operacyjnego)
- ISO 13790 / EN ISO 52016-1 — 5R1C model budynku (rozszerzalny do 5R2C)

---

## Changelog

| Data | Zmiana |
|------|--------|
| 2026-03-29 | Dokument utworzony na podstawie konwersacji Claude ↔ Hubert |
| 2026-03-29 | v2: dodano tryb cooling (UFH + split), constraint T_dew, wilgotność jako wymagany pomiar |
| 2026-03-29 | v2: rozbudowana sekcja symulacji — parametryzowalne scenariusze, profile budynków, full-year, historical weather (Open-Meteo), assertions, metryki |
| 2026-03-29 | v2: faza 5 (chłodzenie) dodana przed pogodą, fazy przenumerowane (7 faz) |
| 2026-03-30 | v3: drugie źródło (split) jako opcjonalne per pokój. UFH jest priorytetem. Dodano scenariusze UFH-only, RoomConfig.has_split, macierz B w wariancie SISO |
| 2026-03-30 | v4: sekcja 8 — roadmapa implementacji (M0–M10), diagram zależności, tabela wartości po każdym milestone |
