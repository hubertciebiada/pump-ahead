using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Commands.SaveHeatPumpSnapshot;

public static class SaveHeatPumpSnapshot
{
    public sealed record Command(HeatPump HeatPump);

    public sealed class Handler(IHeatPumpSnapshotRepository repository) : ICommandHandler<Command>
    {
        public async Task HandleAsync(Command command, CancellationToken cancellationToken = default)
        {
            var heatPump = command.HeatPump;

            var snapshot = HeatPumpSnapshot.CreateFrom(
                heatPump.Id,
                DateTimeOffset.UtcNow,
                heatPump.IsOn,
                heatPump.OperatingMode,
                heatPump.PumpFlow,
                heatPump.OutsideTemperature,
                heatPump.CentralHeating,
                heatPump.DomesticHotWater,
                heatPump.CompressorFrequency,
                heatPump.Power,
                heatPump.Operations,
                heatPump.Defrost,
                heatPump.ErrorCode);

            await repository.SaveSnapshotAsync(snapshot, cancellationToken);
        }
    }
}
