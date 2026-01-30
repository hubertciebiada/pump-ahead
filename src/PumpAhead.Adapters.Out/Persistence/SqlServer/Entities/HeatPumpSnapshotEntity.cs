namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class HeatPumpSnapshotEntity
{
    public long Id { get; set; }
    public Guid HeatPumpId { get; set; }
    public DateTimeOffset Timestamp { get; set; }

    // Core state
    public bool IsOn { get; set; }
    public int OperatingMode { get; set; }
    public decimal PumpFlow { get; set; }
    public decimal OutsideTemperature { get; set; }

    // Central Heating
    public decimal CH_InletTemperature { get; set; }
    public decimal CH_OutletTemperature { get; set; }
    public decimal CH_TargetTemperature { get; set; }

    // Domestic Hot Water
    public decimal DHW_ActualTemperature { get; set; }
    public decimal DHW_TargetTemperature { get; set; }

    // Performance
    public decimal Compressor_Frequency { get; set; }

    // Power data
    public decimal Power_HeatProduction { get; set; }
    public decimal Power_HeatConsumption { get; set; }
    public decimal Power_CoolProduction { get; set; }
    public decimal Power_CoolConsumption { get; set; }
    public decimal Power_DhwProduction { get; set; }
    public decimal Power_DhwConsumption { get; set; }

    // Operations
    public decimal Operations_CompressorHours { get; set; }
    public int Operations_CompressorStarts { get; set; }

    // Defrost
    public bool Defrost_IsActive { get; set; }

    // Error
    public string ErrorCode { get; set; } = string.Empty;
}
