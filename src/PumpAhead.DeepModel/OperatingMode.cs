namespace PumpAhead.DeepModel;

/// <summary>
/// Heishamon TOP4: Operating_Mode_State
/// </summary>
public enum OperatingMode
{
    HeatOnly = 0,
    CoolOnly = 1,
    AutoHeat = 2,
    DhwOnly = 3,
    HeatDhw = 4,
    CoolDhw = 5,
    AutoHeatDhw = 6,
    AutoCool = 7,
    AutoCoolDhw = 8
}
