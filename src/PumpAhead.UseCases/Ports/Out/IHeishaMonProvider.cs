using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

/// <summary>
/// Raw data from HeishaMon /json endpoint.
/// Contains all parsed parameters needed for heat pump state synchronization.
/// </summary>
public sealed record HeishaMonData(
    // Core state
    bool IsOn,
    OperatingMode OperatingMode,
    decimal PumpFlowLitersPerMinute,
    decimal OutsideTemperatureCelsius,

    // Central Heating
    decimal CH_InletTemperatureCelsius,
    decimal CH_OutletTemperatureCelsius,
    decimal CH_TargetTemperatureCelsius,

    // Domestic Hot Water
    decimal DHW_ActualTemperatureCelsius,
    decimal DHW_TargetTemperatureCelsius,

    // Performance
    decimal CompressorFrequencyHertz,

    // Power (watts)
    decimal HeatPowerProductionWatts,
    decimal HeatPowerConsumptionWatts,
    decimal CoolPowerProductionWatts,
    decimal CoolPowerConsumptionWatts,
    decimal DhwPowerProductionWatts,
    decimal DhwPowerConsumptionWatts,

    // Operations
    decimal CompressorOperatingHours,
    int CompressorStartCount,

    // Defrost
    bool IsDefrosting,

    // Error
    string ErrorCode);

/// <summary>
/// Port for fetching heat pump data from HeishaMon device.
/// </summary>
public interface IHeishaMonProvider
{
    /// <summary>
    /// Fetches current data from HeishaMon /json endpoint.
    /// Returns null if connection fails or data cannot be parsed.
    /// </summary>
    Task<HeishaMonData?> FetchDataAsync(CancellationToken cancellationToken = default);
}
