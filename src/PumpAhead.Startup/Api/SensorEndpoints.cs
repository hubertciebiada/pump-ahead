using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.RecordSensorReading;
using PumpAhead.UseCases.Ports;

namespace PumpAhead.Startup.Api;

public static class SensorEndpoints
{
    public static IEndpointRouteBuilder MapSensorEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/sensors");

        group.MapGet("/{sensorId}/readings", RecordReadingFromQuery)
            .WithName("RecordSensorReadingGet");

        return app;
    }

    private static async Task<IResult> RecordReadingFromQuery(
        string sensorId,
        decimal tC,
        string? id,
        ICommandHandler<RecordSensorReading.Command> handler,
        ILogger<Program> logger,
        CancellationToken cancellationToken)
    {
        var effectiveSensorId = !string.IsNullOrEmpty(id) ? id : sensorId;

        return await ProcessReading(
            effectiveSensorId,
            tC,
            handler,
            logger,
            cancellationToken);
    }

    private static async Task<IResult> ProcessReading(
        string sensorId,
        decimal temperatureCelsius,
        ICommandHandler<RecordSensorReading.Command> handler,
        ILogger<Program> logger,
        CancellationToken cancellationToken)
    {
        try
        {
            var command = new RecordSensorReading.Command(
                SensorId.From(sensorId),
                Temperature.FromCelsius(temperatureCelsius),
                DateTimeOffset.UtcNow);

            await handler.HandleAsync(command, cancellationToken);

            logger.LogInformation(
                "Recorded reading from sensor {SensorId}: {Temperature}",
                sensorId, temperatureCelsius);

            return Results.Ok(new { status = "ok", sensorId, temperature = temperatureCelsius });
        }
        catch (ArgumentException ex)
        {
            logger.LogWarning(ex, "Invalid request for sensor {SensorId}", sensorId);
            return Results.BadRequest(new { error = ex.Message });
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Failed to record reading for sensor {SensorId}", sensorId);
            return Results.Problem("Failed to record sensor reading");
        }
    }
}
