using Microsoft.Extensions.Options;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Startup.Configuration;
using PumpAhead.UseCases.Commands.SaveTemperature;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;
using Quartz;

namespace PumpAhead.Startup.Jobs;

public class ShellyPollingJob(
    ISensorReader sensorReader,
    ICommandHandler<SaveTemperature.Command> saveTemperatureHandler,
    IOptions<DeviceSettings> deviceSettings,
    ILogger<ShellyPollingJob> logger) : IJob
{
    public async Task Execute(IJobExecutionContext context)
    {
        try
        {
            logger.LogInformation("Polling Shelly sensor for temperature");

            var temperature = await sensorReader.ReadTemperatureAsync(context.CancellationToken);

            var sensorId = deviceSettings.Value.Shelly.SensorId;
            if (sensorId == Guid.Empty)
            {
                logger.LogWarning("Shelly SensorId is not configured");
                return;
            }

            var command = new SaveTemperature.Command(
                SensorId.From(sensorId),
                temperature,
                DateTimeOffset.UtcNow);

            await saveTemperatureHandler.HandleAsync(command, context.CancellationToken);

            logger.LogInformation("Temperature {Temperature} saved for sensor {SensorId}",
                temperature, sensorId);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Failed to poll Shelly sensor");
        }
    }
}
