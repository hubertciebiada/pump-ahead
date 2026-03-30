# Analiza Shelly H&T (192.168.1.201)

**Data analizy:** 2026-01-24

## Test dostępności (ping co 5s przez 36 min)

### Okienka ONLINE:
| Czas | Odstęp od poprzedniego |
|------|------------------------|
| 19:29:11 | - |
| 19:35:11 | ~6 min |
| 19:41:10 | ~6 min |
| 19:47:10 | ~6 min |
| 19:53:09 | ~6 min |

### Wnioski:
- **Cykl budzenia:** co ~6 minut
- **Okienko dostępności:** <5 sekund (tylko 1 ping trafia)
- **Tryb pracy:** Deep sleep z okresowym budzeniem

## Informacje o urządzeniu

**Odpowiedź z /shelly:**
```json
{
  "name": null,
  "id": "shellyhtg3-b08184ee93a8",
  "mac": "B08184EE93A8",
  "slot": 1,
  "model": "S3SN-0U12A",
  "gen": 3,
  "fw_id": "20241011-121127/1.4.5-gbf870ca",
  "ver": "1.4.5",
  "app": "HTG3",
  "auth_en": false
}
```

**Model:** Shelly H&T Gen 3
**MAC:** B08184EE93A8
**Firmware:** 1.4.5

## Obsługiwane API (Gen 3)

Gen 3 używa nowego API RPC zamiast starego REST API:
- `/rpc/Shelly.GetStatus` - pełny status
- `/rpc/Temperature.GetStatus?id=0` - temperatura
- `/rpc/Humidity.GetStatus?id=0` - wilgotność
- `/rpc/DevicePower.GetStatus?id=0` - bateria

## Rekomendacje dla integracji

1. Nie można polegać na odpytywaniu HTTP - urządzenie śpi przez 99% czasu
2. Rozważyć użycie:
   - MQTT (Shelly wysyła dane przy budzeniu)
   - Shelly Cloud API
   - CoAP (jeśli obsługiwane)
3. Ewentualnie wyłączyć tryb uśpienia w ustawieniach Shelly (kosztem baterii)
