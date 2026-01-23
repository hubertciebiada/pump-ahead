using System.Text.Json.Serialization;

namespace PumpAhead.Adapters.Out.Sensors.Shelly;

public record ShellyTemperatureResponse(
    [property: JsonPropertyName("id")] int Id,
    [property: JsonPropertyName("tC")] decimal TemperatureCelsius,
    [property: JsonPropertyName("tF")] decimal TemperatureFahrenheit);
