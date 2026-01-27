namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class HeatPumpEntity
{
    public Guid Id { get; set; }
    public string Model { get; set; } = string.Empty;
    public DateTimeOffset LastSyncTime { get; set; }

    // TOP0
    public bool IsOn { get; set; }

    // TOP4
    public int OperatingMode { get; set; }

    // TOP1
    public decimal PumpFlow { get; set; }

    // TOP14
    public decimal OutsideTemperature { get; set; }

    // TOP5, TOP6, TOP7
    public decimal CH_InletTemperature { get; set; }
    public decimal CH_OutletTemperature { get; set; }
    public decimal CH_TargetTemperature { get; set; }

    // TOP10, TOP9
    public decimal DHW_ActualTemperature { get; set; }
    public decimal DHW_TargetTemperature { get; set; }

    // TOP8
    public decimal Compressor_Frequency { get; set; }
}
