using System.Net.Http.Json;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Sensors.Shelly;

public class ShellySensorReader(HttpClient httpClient) : ISensorReader
{
    public async Task<Temperature> ReadTemperatureAsync(CancellationToken cancellationToken = default)
    {
        var response = await httpClient.GetFromJsonAsync<ShellyTemperatureResponse>(
            "/rpc/Temperature.GetStatus?id=0",
            cancellationToken);

        if (response is null)
            throw new InvalidOperationException("Failed to read temperature from Shelly sensor");

        return Temperature.FromCelsius(response.TemperatureCelsius);
    }
}
