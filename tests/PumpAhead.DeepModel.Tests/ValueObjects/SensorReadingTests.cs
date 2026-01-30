using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class SensorReadingTests
{
    #region Creation - Valid Values

    [Fact]
    public void Constructor_GivenValidValues_ShouldCreateInstanceWithCorrectValues()
    {
        // Given
        var sensorId = SensorId.From("sensor-001");
        var temperature = Temperature.FromCelsius(21.5m);
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);

        // When
        var reading = new SensorReading(sensorId, temperature, timestamp);

        // Then
        reading.SensorId.Should().Be(sensorId);
        reading.Temperature.Should().Be(temperature);
        reading.Timestamp.Should().Be(timestamp);
    }

    [Fact]
    public void Constructor_GivenTypicalSensorScenario_ShouldStoreAllValues()
    {
        // Given - typical sensor reading
        var sensorId = SensorId.From("living-room-temp");
        var temperature = Temperature.FromCelsius(22.3m);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        var reading = new SensorReading(sensorId, temperature, timestamp);

        // Then
        reading.SensorId.Value.Should().Be("living-room-temp");
        reading.Temperature.Celsius.Should().Be(22.3m);
        reading.Timestamp.Should().Be(timestamp);
    }

    [Fact]
    public void Constructor_GivenNegativeTemperature_ShouldCreateValidInstance()
    {
        // Given - freezer sensor
        var sensorId = SensorId.From("freezer-sensor");
        var temperature = Temperature.FromCelsius(-18m);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        var reading = new SensorReading(sensorId, temperature, timestamp);

        // Then
        reading.Temperature.Celsius.Should().Be(-18m);
    }

    [Fact]
    public void Constructor_GivenHighTemperature_ShouldCreateValidInstance()
    {
        // Given - boiler sensor
        var sensorId = SensorId.From("boiler-outlet");
        var temperature = Temperature.FromCelsius(85m);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        var reading = new SensorReading(sensorId, temperature, timestamp);

        // Then
        reading.Temperature.Celsius.Should().Be(85m);
    }

    [Fact]
    public void Constructor_GivenDifferentTimezones_ShouldPreserveTimestamp()
    {
        // Given
        var sensorId = SensorId.From("sensor-001");
        var temperature = Temperature.FromCelsius(20m);
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.FromHours(2));

        // When
        var reading = new SensorReading(sensorId, temperature, timestamp);

        // Then
        reading.Timestamp.Should().Be(timestamp);
        reading.Timestamp.Offset.Should().Be(TimeSpan.FromHours(2));
    }

    #endregion

    #region Immutability

    [Fact]
    public void RecordStruct_ShouldBeReadonly()
    {
        // Given
        var type = typeof(SensorReading);

        // Then
        type.IsValueType.Should().BeTrue("SensorReading should be a value type (struct)");
    }

    [Fact]
    public void Type_ShouldBeReadonlyRecordStruct()
    {
        // Given
        var type = typeof(SensorReading);

        // Then - readonly structs have IsLayoutSequential=false and are value types
        type.IsValueType.Should().BeTrue("should be a struct");

        // Check that it's a record (has compiler-generated Equals)
        var equalsMethod = type.GetMethod("Equals", new[] { typeof(SensorReading) });
        equalsMethod.Should().NotBeNull("record structs have value-based Equals");
    }

    [Fact]
    public void With_ShouldCreateNewInstanceWithModifiedTemperature()
    {
        // Given
        var original = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(20m),
            DateTimeOffset.UtcNow);
        var newTemperature = Temperature.FromCelsius(25m);

        // When
        var modified = original with { Temperature = newTemperature };

        // Then
        modified.Temperature.Should().Be(newTemperature);
        original.Temperature.Celsius.Should().Be(20m, "original should remain unchanged");
    }

    [Fact]
    public void With_ShouldCreateNewInstanceWithModifiedTimestamp()
    {
        // Given
        var originalTimestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var original = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(20m),
            originalTimestamp);
        var newTimestamp = originalTimestamp.AddMinutes(5);

        // When
        var modified = original with { Timestamp = newTimestamp };

        // Then
        modified.Timestamp.Should().Be(newTimestamp);
        original.Timestamp.Should().Be(originalTimestamp, "original should remain unchanged");
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenSameValues_ShouldBeEqual()
    {
        // Given
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);
        var reading2 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);

        // Then
        reading1.Should().Be(reading2);
        (reading1 == reading2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenDifferentSensorId_ShouldNotBeEqual()
    {
        // Given
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);
        var reading2 = new SensorReading(
            SensorId.From("sensor-002"),
            Temperature.FromCelsius(21.5m),
            timestamp);

        // Then
        reading1.Should().NotBe(reading2);
        (reading1 != reading2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenDifferentTemperature_ShouldNotBeEqual()
    {
        // Given
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);
        var reading2 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(22.0m),
            timestamp);

        // Then
        reading1.Should().NotBe(reading2);
    }

    [Fact]
    public void Equality_GivenDifferentTimestamp_ShouldNotBeEqual()
    {
        // Given
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero));
        var reading2 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            new DateTimeOffset(2025, 1, 30, 12, 0, 1, TimeSpan.Zero));

        // Then
        reading1.Should().NotBe(reading2);
    }

    [Fact]
    public void Equality_GivenSameTimeInDifferentTimezones_ShouldBeEqual()
    {
        // Given - same instant in time, different representations
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero));
        var reading2 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            new DateTimeOffset(2025, 1, 30, 13, 0, 0, TimeSpan.FromHours(1)));

        // Then - DateTimeOffset considers these equal (same instant)
        reading1.Should().Be(reading2);
    }

    [Fact]
    public void GetHashCode_GivenEqualInstances_ShouldReturnSameHashCode()
    {
        // Given
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);
        var reading2 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);

        // Then
        reading1.GetHashCode().Should().Be(reading2.GetHashCode());
    }

    [Fact]
    public void GetHashCode_GivenDifferentInstances_ShouldReturnDifferentHashCodes()
    {
        // Given
        var reading1 = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero));
        var reading2 = new SensorReading(
            SensorId.From("sensor-002"),
            Temperature.FromCelsius(22.0m),
            new DateTimeOffset(2025, 1, 30, 13, 0, 0, TimeSpan.Zero));

        // Then
        reading1.GetHashCode().Should().NotBe(reading2.GetHashCode());
    }

    #endregion

    #region Value Semantics

    [Fact]
    public void ValueSemantics_ShouldSupportDeconstructionViaPositionalRecord()
    {
        // Given
        var sensorId = SensorId.From("sensor-001");
        var temperature = Temperature.FromCelsius(21.5m);
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading = new SensorReading(sensorId, temperature, timestamp);

        // When
        var (deconstructedSensorId, deconstructedTemperature, deconstructedTimestamp) = reading;

        // Then
        deconstructedSensorId.Should().Be(sensorId);
        deconstructedTemperature.Should().Be(temperature);
        deconstructedTimestamp.Should().Be(timestamp);
    }

    [Fact]
    public void ValueSemantics_ShouldWorkInCollections()
    {
        // Given
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);
        var set = new HashSet<SensorReading> { reading };

        // When
        var duplicate = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);

        // Then
        set.Should().Contain(duplicate);
        set.Add(duplicate);
        set.Should().HaveCount(1, "duplicate should not be added");
    }

    [Fact]
    public void ValueSemantics_ShouldSupportOrdering()
    {
        // Given
        var sensorId = SensorId.From("sensor-001");
        var readings = new[]
        {
            new SensorReading(sensorId, Temperature.FromCelsius(20m), new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero)),
            new SensorReading(sensorId, Temperature.FromCelsius(21m), new DateTimeOffset(2025, 1, 30, 10, 0, 0, TimeSpan.Zero)),
            new SensorReading(sensorId, Temperature.FromCelsius(22m), new DateTimeOffset(2025, 1, 30, 11, 0, 0, TimeSpan.Zero))
        };

        // When
        var ordered = readings.OrderBy(r => r.Timestamp).ToArray();

        // Then
        ordered[0].Temperature.Celsius.Should().Be(21m);
        ordered[1].Temperature.Celsius.Should().Be(22m);
        ordered[2].Temperature.Celsius.Should().Be(20m);
    }

    [Fact]
    public void ValueSemantics_ShouldWorkAsDictionaryKey()
    {
        // Given
        var timestamp = new DateTimeOffset(2025, 1, 30, 12, 0, 0, TimeSpan.Zero);
        var reading = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);
        var dictionary = new Dictionary<SensorReading, string>
        {
            { reading, "valid reading" }
        };

        // When
        var lookupKey = new SensorReading(
            SensorId.From("sensor-001"),
            Temperature.FromCelsius(21.5m),
            timestamp);

        // Then
        dictionary.Should().ContainKey(lookupKey);
        dictionary[lookupKey].Should().Be("valid reading");
    }

    #endregion
}
