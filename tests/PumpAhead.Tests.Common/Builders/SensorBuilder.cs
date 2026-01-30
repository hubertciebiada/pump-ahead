using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.Tests.Common.Builders;

/// <summary>
/// Test Data Builder for Sensor entities.
/// Follows Object Mother / Test Data Builder pattern.
/// </summary>
public sealed class SensorBuilder
{
    private string _id = $"sensor-{Guid.NewGuid():N}";
    private string _name = "Temperature Sensor";
    private string? _label;
    private string _address = "28-000005e2fdc3";
    private string _type = "DS18B20";
    private bool _isActive = true;
    private DateTimeOffset? _lastSeenAt = DateTimeOffset.UtcNow;

    /// <summary>
    /// Creates a new builder with default valid values.
    /// </summary>
    public static SensorBuilder Valid() => new();

    /// <summary>
    /// Creates a builder for an indoor temperature sensor.
    /// </summary>
    public static SensorBuilder IndoorSensor() => new SensorBuilder()
        .WithName("Indoor Temperature")
        .WithLabel("Living Room")
        .WithType("DS18B20");

    /// <summary>
    /// Creates a builder for an outdoor temperature sensor.
    /// </summary>
    public static SensorBuilder OutdoorSensor() => new SensorBuilder()
        .WithName("Outdoor Temperature")
        .WithLabel("North Wall")
        .WithType("DS18B20");

    /// <summary>
    /// Creates a builder for a water temperature sensor.
    /// </summary>
    public static SensorBuilder WaterSensor() => new SensorBuilder()
        .WithName("Water Temperature")
        .WithLabel("Buffer Tank")
        .WithType("DS18B20");

    /// <summary>
    /// Creates a builder for an inactive sensor.
    /// </summary>
    public static SensorBuilder Inactive() => new SensorBuilder()
        .WithIsActive(false)
        .WithLastSeenAt(DateTimeOffset.UtcNow.AddDays(-7));

    public SensorBuilder WithId(string id)
    {
        _id = id;
        return this;
    }

    public SensorBuilder WithName(string name)
    {
        _name = name;
        return this;
    }

    public SensorBuilder WithLabel(string? label)
    {
        _label = label;
        return this;
    }

    public SensorBuilder WithAddress(string address)
    {
        _address = address;
        return this;
    }

    public SensorBuilder WithType(string type)
    {
        _type = type;
        return this;
    }

    public SensorBuilder WithIsActive(bool isActive)
    {
        _isActive = isActive;
        return this;
    }

    public SensorBuilder WithLastSeenAt(DateTimeOffset? lastSeenAt)
    {
        _lastSeenAt = lastSeenAt;
        return this;
    }

    /// <summary>
    /// Builds the SensorEntity.
    /// </summary>
    public SensorEntity Build()
    {
        return new SensorEntity
        {
            Id = _id,
            Name = _name,
            Label = _label,
            Address = _address,
            Type = _type,
            IsActive = _isActive,
            LastSeenAt = _lastSeenAt
        };
    }

    /// <summary>
    /// Implicit conversion to SensorEntity for convenient usage in tests.
    /// </summary>
    public static implicit operator SensorEntity(SensorBuilder builder) => builder.Build();
}

/// <summary>
/// Test Data Builder for SensorReading value objects.
/// </summary>
public sealed class SensorReadingBuilder
{
    private SensorId _sensorId = SensorId.From($"sensor-{Guid.NewGuid():N}");
    private Temperature _temperature = Temperature.FromCelsius(21.5m);
    private DateTimeOffset _timestamp = DateTimeOffset.UtcNow;

    /// <summary>
    /// Creates a new builder with default valid values.
    /// </summary>
    public static SensorReadingBuilder Valid() => new();

    /// <summary>
    /// Creates a builder for a room temperature reading.
    /// </summary>
    public static SensorReadingBuilder RoomTemperature() => new SensorReadingBuilder()
        .WithTemperature(Temperature.FromCelsius(21.0m));

    /// <summary>
    /// Creates a builder for an outdoor temperature reading.
    /// </summary>
    public static SensorReadingBuilder OutdoorTemperature(decimal celsius = 5.0m) =>
        new SensorReadingBuilder()
            .WithTemperature(Temperature.FromCelsius(celsius));

    /// <summary>
    /// Creates a series of readings with incrementing timestamps.
    /// </summary>
    public static IEnumerable<SensorReading> CreateSeries(
        SensorId sensorId,
        int count,
        TimeSpan interval,
        decimal baseTemperature = 20.0m,
        decimal variance = 2.0m,
        DateTimeOffset? startTime = null)
    {
        var time = startTime ?? DateTimeOffset.UtcNow.AddMinutes(-count * interval.TotalMinutes);
        var random = new Random(42); // Fixed seed for reproducibility

        for (int i = 0; i < count; i++)
        {
            var temp = baseTemperature + (decimal)(random.NextDouble() * (double)variance * 2 - (double)variance);

            yield return new SensorReadingBuilder()
                .WithSensorId(sensorId)
                .WithTimestamp(time)
                .WithTemperature(Temperature.FromCelsius(temp))
                .Build();

            time = time.Add(interval);
        }
    }

    public SensorReadingBuilder WithSensorId(SensorId sensorId)
    {
        _sensorId = sensorId;
        return this;
    }

    public SensorReadingBuilder WithSensorId(string id) => WithSensorId(SensorId.From(id));

    public SensorReadingBuilder WithTemperature(Temperature temperature)
    {
        _temperature = temperature;
        return this;
    }

    public SensorReadingBuilder WithTemperature(decimal celsius) =>
        WithTemperature(Temperature.FromCelsius(celsius));

    public SensorReadingBuilder WithTimestamp(DateTimeOffset timestamp)
    {
        _timestamp = timestamp;
        return this;
    }

    /// <summary>
    /// Builds the SensorReading value object.
    /// </summary>
    public SensorReading Build()
    {
        return new SensorReading(_sensorId, _temperature, _timestamp);
    }

    /// <summary>
    /// Implicit conversion to SensorReading for convenient usage in tests.
    /// </summary>
    public static implicit operator SensorReading(SensorReadingBuilder builder) => builder.Build();
}
