using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Entities;

/// <summary>
/// Historical snapshot of heat pump state, captured periodically.
/// Immutable record of heat pump parameters at a specific point in time.
/// </summary>
public class HeatPumpSnapshot
{
    public HeatPumpSnapshotId Id { get; private set; }
    public HeatPumpId HeatPumpId { get; private set; }
    public DateTimeOffset Timestamp { get; private set; }

    // Core state
    public bool IsOn { get; private set; }
    public OperatingMode OperatingMode { get; private set; }
    public PumpFlow PumpFlow { get; private set; }
    public OutsideTemperature OutsideTemperature { get; private set; }

    // Temperatures
    public CentralHeatingData CentralHeating { get; private set; }
    public DomesticHotWaterData DomesticHotWater { get; private set; }

    // Performance
    public Frequency CompressorFrequency { get; private set; }
    public PowerData Power { get; private set; }

    // Operations & Status
    public OperationsData Operations { get; private set; }
    public DefrostData Defrost { get; private set; }
    public ErrorCode ErrorCode { get; private set; }

    private HeatPumpSnapshot() { } // EF Core

    /// <summary>
    /// Creates a new snapshot from current heat pump state.
    /// </summary>
    public static HeatPumpSnapshot CreateFrom(
        HeatPumpId heatPumpId,
        DateTimeOffset timestamp,
        bool isOn,
        OperatingMode operatingMode,
        PumpFlow pumpFlow,
        OutsideTemperature outsideTemperature,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        Frequency compressorFrequency,
        PowerData power,
        OperationsData operations,
        DefrostData defrost,
        ErrorCode errorCode)
    {
        return new HeatPumpSnapshot
        {
            Id = HeatPumpSnapshotId.From(0), // DB will assign
            HeatPumpId = heatPumpId,
            Timestamp = timestamp,
            IsOn = isOn,
            OperatingMode = operatingMode,
            PumpFlow = pumpFlow,
            OutsideTemperature = outsideTemperature,
            CentralHeating = centralHeating,
            DomesticHotWater = domesticHotWater,
            CompressorFrequency = compressorFrequency,
            Power = power,
            Operations = operations,
            Defrost = defrost,
            ErrorCode = errorCode
        };
    }

    /// <summary>
    /// Reconstitutes a snapshot from persistence.
    /// </summary>
    public static HeatPumpSnapshot Reconstitute(
        HeatPumpSnapshotId id,
        HeatPumpId heatPumpId,
        DateTimeOffset timestamp,
        bool isOn,
        OperatingMode operatingMode,
        PumpFlow pumpFlow,
        OutsideTemperature outsideTemperature,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        Frequency compressorFrequency,
        PowerData power,
        OperationsData operations,
        DefrostData defrost,
        ErrorCode errorCode)
    {
        return new HeatPumpSnapshot
        {
            Id = id,
            HeatPumpId = heatPumpId,
            Timestamp = timestamp,
            IsOn = isOn,
            OperatingMode = operatingMode,
            PumpFlow = pumpFlow,
            OutsideTemperature = outsideTemperature,
            CentralHeating = centralHeating,
            DomesticHotWater = domesticHotWater,
            CompressorFrequency = compressorFrequency,
            Power = power,
            Operations = operations,
            Defrost = defrost,
            ErrorCode = errorCode
        };
    }
}
