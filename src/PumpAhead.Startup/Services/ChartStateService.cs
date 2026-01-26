namespace PumpAhead.Startup.Services;

public sealed class ChartStateService
{
    private TimeSpan _timeRange = TimeSpan.FromHours(24);

    public event Action? TimeRangeChanged;

    public TimeSpan TimeRange => _timeRange;

    public void SetTimeRange(TimeSpan range)
    {
        if (_timeRange != range)
        {
            _timeRange = range;
            TimeRangeChanged?.Invoke();
        }
    }

    public DateTimeOffset GetStartTime() => DateTimeOffset.UtcNow - _timeRange;

    public DateTimeOffset GetEndTime() => DateTimeOffset.UtcNow;

    public static readonly TimeSpan[] AvailableRanges =
    [
        TimeSpan.FromHours(6),
        TimeSpan.FromHours(12),
        TimeSpan.FromHours(24),
        TimeSpan.FromDays(7),
    ];

    public static string FormatRange(TimeSpan range)
    {
        if (range.TotalDays >= 1)
            return $"{(int)range.TotalDays}d";
        return $"{(int)range.TotalHours}h";
    }
}
