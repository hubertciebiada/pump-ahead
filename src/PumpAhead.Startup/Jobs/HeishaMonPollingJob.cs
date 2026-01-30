using Microsoft.Extensions.Options;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Startup.Configuration;
using PumpAhead.UseCases.Commands.SaveHeatPumpSnapshot;
using PumpAhead.UseCases.Commands.SyncHeatPumpState;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;
using Quartz;

namespace PumpAhead.Startup.Jobs;

[DisallowConcurrentExecution]
public sealed class HeishaMonPollingJob(
    IHeishaMonProvider heishaMonProvider,
    IHeatPumpRepository heatPumpRepository,
    ICommandHandler<SyncHeatPumpState.Command> syncHandler,
    ICommandHandler<SaveHeatPumpSnapshot.Command> snapshotHandler,
    IHeatPumpNotificationService notificationService,
    IOptions<HeishaMonSettings> settings,
    ILogger<HeishaMonPollingJob> logger) : IJob
{
    public static readonly JobKey Key = new("heishamon-polling", "polling");

    // Note: Static fields are used because Quartz creates new job instances per execution.
    // [DisallowConcurrentExecution] ensures only one execution at a time.
    // For multi-instance deployment, consider using persistent storage instead.
    private static int _consecutiveFailures;
    private static DateTimeOffset _lastSnapshotTime = DateTimeOffset.MinValue;

    public async Task Execute(IJobExecutionContext context)
    {
        var config = settings.Value;
        var heatPumpId = HeatPumpId.From(config.HeatPumpId);

        try
        {
            var data = await heishaMonProvider.FetchDataAsync(context.CancellationToken);

            if (data == null)
            {
                await HandleFailureAsync();
                return;
            }

            // Reset failure counter on success
            if (_consecutiveFailures > 0)
            {
                logger.LogInformation("HeishaMon connection restored after {Count} failures", _consecutiveFailures);
                _consecutiveFailures = 0;
            }

            // Update aggregate state
            await syncHandler.HandleAsync(
                new SyncHeatPumpState.Command(data, heatPumpId),
                context.CancellationToken);

            // Save snapshot if interval has passed
            var now = DateTimeOffset.UtcNow;
            var snapshotInterval = TimeSpan.FromSeconds(config.SnapshotIntervalSeconds);

            if (now - _lastSnapshotTime >= snapshotInterval)
            {
                await SaveSnapshotAsync(heatPumpId, context.CancellationToken);
                _lastSnapshotTime = now;
            }

            logger.LogDebug("HeishaMon data synced successfully");
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unexpected error in HeishaMon polling job");
            await HandleFailureAsync();
        }
    }

    private async Task HandleFailureAsync()
    {
        _consecutiveFailures++;
        logger.LogWarning("HeishaMon fetch failed (consecutive failures: {Count})", _consecutiveFailures);

        if (_consecutiveFailures == 5)
        {
            logger.LogError("HeishaMon connection failed 5 times consecutively! Sending alert.");
            await notificationService.NotifyConnectionFailureAsync(_consecutiveFailures);
        }
        else if (_consecutiveFailures > 5 && _consecutiveFailures % 10 == 0)
        {
            // Continue alerting every 10 failures
            await notificationService.NotifyConnectionFailureAsync(_consecutiveFailures);
        }
    }

    private async Task SaveSnapshotAsync(HeatPumpId heatPumpId, CancellationToken cancellationToken)
    {
        var heatPump = await heatPumpRepository.GetByIdAsync(heatPumpId, cancellationToken);

        if (heatPump != null)
        {
            await snapshotHandler.HandleAsync(
                new SaveHeatPumpSnapshot.Command(heatPump),
                cancellationToken);

            logger.LogInformation("HeatPump snapshot saved");
        }
    }
}
