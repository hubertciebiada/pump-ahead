using System.Globalization;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;
using PumpAhead.DeepModel;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.HeishaMon;

public class HeishaMonProvider(
    HttpClient httpClient,
    ILogger<HeishaMonProvider> logger) : IHeishaMonProvider
{
    public async Task<HeishaMonData?> FetchDataAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await httpClient.GetFromJsonAsync<HeishaMonJsonResponse>(
                "/json",
                cancellationToken);

            if (response?.Heatpump == null || response.Heatpump.Count == 0)
            {
                logger.LogWarning("HeishaMon returned null or empty response");
                return null;
            }

            var data = MapToDomain(response);
            logger.LogDebug("HeishaMon data fetched: {IsOn}, {Freq}Hz, {OutsideTemp}°C",
                data.IsOn, data.CompressorFrequencyHertz, data.OutsideTemperatureCelsius);

            return data;
        }
        catch (HttpRequestException ex)
        {
            logger.LogWarning(ex, "Failed to connect to HeishaMon");
            return null;
        }
        catch (TaskCanceledException ex) when (ex.CancellationToken != cancellationToken)
        {
            logger.LogWarning("HeishaMon request timed out");
            return null;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unexpected error fetching HeishaMon data");
            return null;
        }
    }

    private HeishaMonData MapToDomain(HeishaMonJsonResponse response)
    {
        var values = response.Heatpump.ToDictionary(
            p => p.Name,
            p => p.Value,
            StringComparer.OrdinalIgnoreCase);

        return new HeishaMonData(
            // Core state
            IsOn: ParseInt(values, "Heatpump_State") == 1,
            OperatingMode: (OperatingMode)ParseInt(values, "Operating_Mode_State"),
            PumpFlowLitersPerMinute: ParseDecimal(values, "Pump_Flow"),
            OutsideTemperatureCelsius: ParseDecimal(values, "Outside_Temp"),

            // Central Heating
            CH_InletTemperatureCelsius: ParseDecimal(values, "Main_Inlet_Temp"),
            CH_OutletTemperatureCelsius: ParseDecimal(values, "Main_Outlet_Temp"),
            CH_TargetTemperatureCelsius: ParseDecimal(values, "Main_Target_Temp"),

            // Domestic Hot Water
            DHW_ActualTemperatureCelsius: ParseDecimal(values, "DHW_Temp"),
            DHW_TargetTemperatureCelsius: ParseDecimal(values, "DHW_Target_Temp"),

            // Performance
            CompressorFrequencyHertz: ParseDecimal(values, "Compressor_Freq"),

            // Power
            HeatPowerProductionWatts: ParseDecimal(values, "Heat_Power_Production"),
            HeatPowerConsumptionWatts: ParseDecimal(values, "Heat_Power_Consumption"),
            CoolPowerProductionWatts: ParseDecimal(values, "Cool_Power_Production"),
            CoolPowerConsumptionWatts: ParseDecimal(values, "Cool_Power_Consumption"),
            DhwPowerProductionWatts: ParseDecimal(values, "DHW_Power_Production"),
            DhwPowerConsumptionWatts: ParseDecimal(values, "DHW_Power_Consumption"),

            // Operations
            CompressorOperatingHours: ParseDecimal(values, "Operations_Hours"),
            CompressorStartCount: ParseInt(values, "Operations_Counter"),

            // Defrost
            IsDefrosting: ParseInt(values, "Defrosting_State") == 1,

            // Error
            ErrorCode: GetValue(values, "Error") ?? string.Empty);
    }

    private static string? GetValue(Dictionary<string, string> values, string key)
    {
        return values.GetValueOrDefault(key);
    }

    private static decimal ParseDecimal(Dictionary<string, string> values, string key)
    {
        if (values.TryGetValue(key, out var value) &&
            decimal.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out var result))
        {
            return result;
        }
        return 0m;
    }

    private static int ParseInt(Dictionary<string, string> values, string key)
    {
        if (values.TryGetValue(key, out var value) &&
            int.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out var result))
        {
            return result;
        }
        return 0;
    }

    /// <summary>
    /// HeishaMon /json endpoint response structure.
    /// </summary>
    private sealed class HeishaMonJsonResponse
    {
        [JsonPropertyName("heatpump")]
        public List<HeishaMonParameter> Heatpump { get; set; } = [];

        [JsonPropertyName("1wire")]
        public List<HeishaMonParameter> OneWire { get; set; } = [];

        [JsonPropertyName("s0")]
        public List<HeishaMonParameter> S0 { get; set; } = [];
    }

    private sealed class HeishaMonParameter
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("value")]
        public string Value { get; set; } = string.Empty;

        [JsonPropertyName("description")]
        public string? Description { get; set; }
    }
}
