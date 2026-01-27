using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Aggregates;

public class HeatPump
{
    public HeatPumpId Id { get; private set; }
    public string Model { get; private set; }
    public DateTimeOffset LastSyncTime { get; private set; }
    public OperatingMode OperatingMode { get; private set; }

    public CentralHeatingData CentralHeating { get; private set; }
    public DomesticHotWaterData DomesticHotWater { get; private set; }
    public CompressorData Compressor { get; private set; }

    private HeatPump(
        HeatPumpId id,
        string model,
        DateTimeOffset lastSyncTime,
        OperatingMode operatingMode,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        CompressorData compressor)
    {
        if (string.IsNullOrWhiteSpace(model))
            throw new ArgumentException("Model cannot be empty", nameof(model));

        Id = id;
        Model = model;
        LastSyncTime = lastSyncTime;
        OperatingMode = operatingMode;
        CentralHeating = centralHeating;
        DomesticHotWater = domesticHotWater;
        Compressor = compressor;
    }

    public static HeatPump Create(
        HeatPumpId id,
        string model,
        OperatingMode operatingMode,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        CompressorData compressor)
    {
        return new HeatPump(
            id,
            model,
            DateTimeOffset.UtcNow,
            operatingMode,
            centralHeating,
            domesticHotWater,
            compressor);
    }

    public void UpdateOperatingMode(OperatingMode mode)
    {
        OperatingMode = mode;
        UpdateSyncTime();
    }

    public void UpdateCentralHeating(CentralHeatingData data)
    {
        CentralHeating = data;
        UpdateSyncTime();
    }

    public void UpdateDomesticHotWater(DomesticHotWaterData data)
    {
        DomesticHotWater = data;
        UpdateSyncTime();
    }

    public void UpdateCompressor(CompressorData data)
    {
        Compressor = data;
        UpdateSyncTime();
    }

    public void SyncFrom(
        OperatingMode operatingMode,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        CompressorData compressor)
    {
        OperatingMode = operatingMode;
        CentralHeating = centralHeating;
        DomesticHotWater = domesticHotWater;
        Compressor = compressor;
        UpdateSyncTime();
    }

    private void UpdateSyncTime()
    {
        LastSyncTime = DateTimeOffset.UtcNow;
    }

    public static HeatPump Reconstitute(
        HeatPumpId id,
        string model,
        DateTimeOffset lastSyncTime,
        OperatingMode operatingMode,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        CompressorData compressor)
    {
        return new HeatPump(
            id,
            model,
            lastSyncTime,
            operatingMode,
            centralHeating,
            domesticHotWater,
            compressor);
    }
}
