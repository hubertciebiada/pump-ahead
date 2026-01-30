namespace PumpAhead.UseCases.Ports.Out;

/// <summary>
/// Service for sending heat pump notifications to connected clients.
/// </summary>
public interface IHeatPumpNotificationService
{
    /// <summary>
    /// Notifies all connected clients that heat pump data has been updated.
    /// </summary>
    Task NotifyHeatPumpUpdatedAsync();

    /// <summary>
    /// Notifies all connected clients about HeishaMon connection failure.
    /// </summary>
    /// <param name="consecutiveFailures">Number of consecutive failed connection attempts.</param>
    Task NotifyConnectionFailureAsync(int consecutiveFailures);
}
