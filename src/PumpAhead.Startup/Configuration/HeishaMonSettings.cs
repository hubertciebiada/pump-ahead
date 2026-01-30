namespace PumpAhead.Startup.Configuration;

public class HeishaMonSettings
{
    /// <summary>
    /// Base URL of the HeishaMon device (e.g., "http://192.168.1.100" or "http://heishamon.local").
    /// </summary>
    public string Address { get; set; } = "http://heishamon.local";

    /// <summary>
    /// Heat pump ID in the database. Should match an existing HeatPump record.
    /// </summary>
    public Guid HeatPumpId { get; set; }

    /// <summary>
    /// Polling interval in seconds. Recommended: 30 seconds.
    /// </summary>
    public int PollingIntervalSeconds { get; set; } = 30;

    /// <summary>
    /// Snapshot interval in seconds. Default: 300 (5 minutes).
    /// </summary>
    public int SnapshotIntervalSeconds { get; set; } = 300;

    /// <summary>
    /// HTTP request timeout in seconds.
    /// </summary>
    public int TimeoutSeconds { get; set; } = 10;
}
