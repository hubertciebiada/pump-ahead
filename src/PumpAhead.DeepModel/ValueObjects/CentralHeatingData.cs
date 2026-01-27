namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct CentralHeatingData
{
    public FlowTemperature FlowTemperature { get; }
    public ReturnTemperature ReturnTemperature { get; }
    public TemperatureOffset Offset { get; }

    private CentralHeatingData(
        FlowTemperature flowTemperature,
        ReturnTemperature returnTemperature,
        TemperatureOffset offset)
    {
        FlowTemperature = flowTemperature;
        ReturnTemperature = returnTemperature;
        Offset = offset;
    }

    public static CentralHeatingData Create(
        FlowTemperature flowTemperature,
        ReturnTemperature returnTemperature,
        TemperatureOffset offset) =>
        new(flowTemperature, returnTemperature, offset);
}
