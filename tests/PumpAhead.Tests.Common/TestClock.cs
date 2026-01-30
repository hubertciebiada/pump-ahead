namespace PumpAhead.Tests.Common;

/// <summary>
/// A controllable clock for testing time-dependent logic.
/// Implements a simple time provider pattern for test isolation.
/// </summary>
public sealed class TestClock
{
    private DateTimeOffset _now;

    public TestClock() : this(DateTimeOffset.UtcNow)
    {
    }

    public TestClock(DateTimeOffset startTime)
    {
        _now = startTime;
    }

    /// <summary>
    /// Gets the current time.
    /// </summary>
    public DateTimeOffset Now => _now;

    /// <summary>
    /// Gets the current time as UTC DateTime.
    /// </summary>
    public DateTime UtcNow => _now.UtcDateTime;

    /// <summary>
    /// Sets the current time to a specific value.
    /// </summary>
    public TestClock SetTo(DateTimeOffset time)
    {
        _now = time;
        return this;
    }

    /// <summary>
    /// Advances the clock by a specified duration.
    /// </summary>
    public TestClock Advance(TimeSpan duration)
    {
        _now = _now.Add(duration);
        return this;
    }

    /// <summary>
    /// Advances the clock by a specified number of minutes.
    /// </summary>
    public TestClock AdvanceMinutes(double minutes) => Advance(TimeSpan.FromMinutes(minutes));

    /// <summary>
    /// Advances the clock by a specified number of hours.
    /// </summary>
    public TestClock AdvanceHours(double hours) => Advance(TimeSpan.FromHours(hours));

    /// <summary>
    /// Advances the clock by a specified number of days.
    /// </summary>
    public TestClock AdvanceDays(double days) => Advance(TimeSpan.FromDays(days));

    /// <summary>
    /// Rewinds the clock by a specified duration.
    /// </summary>
    public TestClock Rewind(TimeSpan duration) => Advance(-duration);

    /// <summary>
    /// Creates a clock set to a specific date at midnight UTC.
    /// </summary>
    public static TestClock AtDate(int year, int month, int day) =>
        new(new DateTimeOffset(year, month, day, 0, 0, 0, TimeSpan.Zero));

    /// <summary>
    /// Creates a clock set to a specific date and time in UTC.
    /// </summary>
    public static TestClock At(int year, int month, int day, int hour, int minute, int second = 0) =>
        new(new DateTimeOffset(year, month, day, hour, minute, second, TimeSpan.Zero));
}
