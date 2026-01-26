using System.Text.Json.Serialization;

namespace PumpAhead.Startup.Api;

public sealed record SensorReadingRequest(
    [property: JsonPropertyName("id")] string? Id,
    [property: JsonPropertyName("tC")] decimal TemperatureCelsius);
