using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Commands.SaveTemperature;

public static class SaveTemperature
{
    public sealed record Command(
        SensorId SensorId,
        Temperature Temperature,
        DateTimeOffset Timestamp);

    public sealed class Handler(ITemperatureRepository repository) : ICommandHandler<Command>
    {
        public async Task HandleAsync(Command command, CancellationToken cancellationToken = default)
        {
            var reading = new SensorReading(
                command.SensorId,
                command.Temperature,
                command.Timestamp);

            await repository.SaveAsync(reading, cancellationToken);
        }
    }
}
