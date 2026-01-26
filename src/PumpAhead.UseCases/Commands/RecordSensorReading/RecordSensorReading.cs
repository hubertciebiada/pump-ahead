using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Commands.RecordSensorReading;

public static class RecordSensorReading
{
    public sealed record Command(
        SensorId SensorId,
        Temperature Temperature,
        DateTimeOffset Timestamp);

    public sealed class Handler(
        ISensorRepository sensorRepository,
        ITemperatureRepository temperatureRepository) : ICommandHandler<Command>
    {
        public async Task HandleAsync(Command command, CancellationToken cancellationToken = default)
        {
            var sensor = await sensorRepository.GetByIdAsync(command.SensorId, cancellationToken);

            if (sensor is null)
            {
                var newSensor = new SensorInfo(
                    command.SensorId,
                    Name: command.SensorId.Value,
                    Label: null,
                    Address: string.Empty,
                    Type: "shelly",
                    IsActive: true,
                    LastSeenAt: command.Timestamp);

                await sensorRepository.SaveAsync(newSensor, cancellationToken);
            }
            else
            {
                await sensorRepository.UpdateLastSeenAsync(command.SensorId, command.Timestamp, cancellationToken);
            }

            var reading = new SensorReading(
                command.SensorId,
                command.Temperature,
                command.Timestamp);

            await temperatureRepository.SaveAsync(reading, cancellationToken);
        }
    }
}
