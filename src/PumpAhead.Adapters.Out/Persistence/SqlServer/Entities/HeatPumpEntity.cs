namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class HeatPumpEntity
{
    public Guid Id { get; set; }
    public string Model { get; set; } = string.Empty;
    public DateTimeOffset LastSyncTime { get; set; }
    public int OperatingMode { get; set; }

    public decimal CH_FlowTemperature { get; set; }
    public decimal CH_ReturnTemperature { get; set; }
    public decimal CH_Offset { get; set; }

    public decimal DHW_ActualTemperature { get; set; }
    public decimal DHW_TargetTemperature { get; set; }
    public decimal DHW_Delta { get; set; }

    public decimal Compressor_Frequency { get; set; }
}
