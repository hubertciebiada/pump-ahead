using FluentAssertions;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Tests.Common.Builders;
using PumpAhead.Tests.Common.Fixtures;

namespace PumpAhead.Adapters.Out.Tests.Repositories;

public class SqlServerTemperatureRepositoryTests : IntegrationTestBase
{
    private const string SensorId001 = "sensor-001";
    private const string SensorMulti = "sensor-multi";
    private const string OutdoorSensor = "outdoor-sensor";
    private const string SensorLatest = "sensor-latest";
    private const string NonExistentSensor = "non-existent-sensor";
    private const string SingleReadingSensor = "single-reading-sensor";
    private const string HistorySensor = "history-sensor";
    private const string OrderedSensor = "ordered-sensor";
    private const string NoReadingsSensor = "no-readings-sensor";
    private const string RequestedSensor = "requested-sensor";
    private const string OtherSensor = "other-sensor";
    private const string BoundarySensor = "boundary-sensor";
    private const string BatchSensor1 = "batch-sensor-1";
    private const string BatchSensor2 = "batch-sensor-2";
    private const string BatchSensor3 = "batch-sensor-3";
    private const string OrderedBatchSensor = "ordered-batch-sensor";
    private const string FilterBatchSensor = "filter-batch-sensor";
    private const decimal Temperature215 = 21.5m;
    private const decimal Temperature20 = 20.0m;
    private const decimal Temperature21 = 21.0m;
    private const decimal Temperature22 = 22.0m;
    private const decimal Temperature25 = 25.0m;
    private const decimal Temperature185 = 18.5m;
    private const decimal Temperature18 = 18.0m;
    private const decimal Temperature15 = 15.0m;
    private const decimal Temperature30 = 30.0m;
    private const decimal NegativeTemperature = -15.5m;

    #region SaveAsync

    [Fact]
    public async Task SaveAsync_GivenNewReading_WhenCalled_ThenReadingIsPersistedToDatabase()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorId = SensorId.From(SensorId001);
        var temperature = Temperature.FromCelsius(Temperature215);
        var timestamp = DateTimeOffset.UtcNow;

        var reading = new SensorReading(sensorId, temperature, timestamp);

        // When
        await sut.SaveAsync(reading);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntity = verifyContext.TemperatureReadings.FirstOrDefault(r => r.SensorId == SensorId001);
        savedEntity.Should().NotBeNull();
        savedEntity!.Temperature.Should().Be(Temperature215);
        savedEntity.Timestamp.Should().Be(timestamp);
    }

    [Fact]
    public async Task SaveAsync_GivenMultipleReadings_WhenCalled_ThenAllReadingsArePersisted()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorId = SensorId.From(SensorMulti);
        var baseTime = DateTimeOffset.UtcNow;

        // When
        await sut.SaveAsync(new SensorReading(sensorId, Temperature.FromCelsius(Temperature20), baseTime));
        await sut.SaveAsync(new SensorReading(sensorId, Temperature.FromCelsius(Temperature21), baseTime.AddMinutes(5)));
        await sut.SaveAsync(new SensorReading(sensorId, Temperature.FromCelsius(Temperature22), baseTime.AddMinutes(10)));

        // Then
        await using var verifyContext = CreateContext();
        var readings = verifyContext.TemperatureReadings.Where(r => r.SensorId == SensorMulti).ToList();
        readings.Should().HaveCount(3);
    }

    [Fact]
    public async Task SaveAsync_GivenNegativeTemperature_WhenCalled_ThenNegativeValueIsPersisted()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var reading = new SensorReading(
            SensorId.From(OutdoorSensor),
            Temperature.FromCelsius(NegativeTemperature),
            DateTimeOffset.UtcNow);

        // When
        await sut.SaveAsync(reading);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntity = verifyContext.TemperatureReadings.FirstOrDefault(r => r.SensorId == OutdoorSensor);
        savedEntity.Should().NotBeNull();
        savedEntity!.Temperature.Should().Be(NegativeTemperature);
    }

    #endregion

    #region GetLatestAsync

    [Fact]
    public async Task GetLatestAsync_GivenMultipleReadings_WhenCalled_ThenReturnsLatestReading()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx =>
        {
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = SensorLatest,
                Temperature = Temperature20,
                Timestamp = baseTime.AddMinutes(-10)
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = SensorLatest,
                Temperature = Temperature25,
                Timestamp = baseTime // Latest
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = SensorLatest,
                Temperature = Temperature22,
                Timestamp = baseTime.AddMinutes(-5)
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetLatestAsync(SensorId.From(SensorLatest));

        // Then
        result.Should().NotBeNull();
        result.Value.Temperature.Celsius.Should().Be(Temperature25);
        result.Value.Timestamp.Should().Be(baseTime);
    }

    [Fact]
    public async Task GetLatestAsync_GivenNoReadingsForSensor_WhenCalled_ThenReturnsNull()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetLatestAsync(SensorId.From(NonExistentSensor));

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetLatestAsync_GivenSingleReading_WhenCalled_ThenReturnsThatReading()
    {
        // Given
        var timestamp = DateTimeOffset.UtcNow;

        Given(ctx => ctx.TemperatureReadings.Add(new TemperatureReadingEntity
        {
            SensorId = SingleReadingSensor,
            Temperature = Temperature185,
            Timestamp = timestamp
        }));

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetLatestAsync(SensorId.From(SingleReadingSensor));

        // Then
        result.Should().NotBeNull();
        result.Value.SensorId.Value.Should().Be(SingleReadingSensor);
        result.Value.Temperature.Celsius.Should().Be(Temperature185);
    }

    #endregion

    #region GetHistoryAsync

    [Fact]
    public async Task GetHistoryAsync_GivenReadingsInRange_WhenCalled_ThenReturnsFilteredReadings()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx =>
        {
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = HistorySensor,
                Temperature = Temperature18,
                Timestamp = baseTime.AddHours(-3) // Before range
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = HistorySensor,
                Temperature = Temperature20,
                Timestamp = baseTime.AddHours(-2) // In range
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = HistorySensor,
                Temperature = Temperature21,
                Timestamp = baseTime.AddHours(-1) // In range
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = HistorySensor,
                Temperature = Temperature22,
                Timestamp = baseTime // In range
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = HistorySensor,
                Temperature = Temperature25,
                Timestamp = baseTime.AddHours(1) // After range
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var from = baseTime.AddHours(-2);
        var to = baseTime;

        // When
        var result = await sut.GetHistoryAsync(SensorId.From(HistorySensor), from, to);

        // Then
        result.Should().HaveCount(3);
        result.Should().OnlyContain(r => r.Temperature.Celsius >= Temperature20 && r.Temperature.Celsius <= Temperature22);
    }

    [Fact]
    public async Task GetHistoryAsync_GivenReadingsInRange_WhenCalled_ThenReturnsOrderedByTimestamp()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx =>
        {
            // Add in non-chronological order
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OrderedSensor,
                Temperature = Temperature22,
                Timestamp = baseTime // Third
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OrderedSensor,
                Temperature = Temperature20,
                Timestamp = baseTime.AddHours(-2) // First
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OrderedSensor,
                Temperature = Temperature21,
                Timestamp = baseTime.AddHours(-1) // Second
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetHistoryAsync(
            SensorId.From(OrderedSensor),
            baseTime.AddHours(-3),
            baseTime.AddHours(1));

        // Then
        result.Should().HaveCount(3);
        result.Should().BeInAscendingOrder(r => r.Timestamp);
        result[0].Temperature.Celsius.Should().Be(Temperature20);
        result[1].Temperature.Celsius.Should().Be(Temperature21);
        result[2].Temperature.Celsius.Should().Be(Temperature22);
    }

    [Fact]
    public async Task GetHistoryAsync_GivenNoReadingsInRange_WhenCalled_ThenReturnsEmptyList()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx => ctx.TemperatureReadings.Add(new TemperatureReadingEntity
        {
            SensorId = NoReadingsSensor,
            Temperature = Temperature20,
            Timestamp = baseTime.AddDays(-7) // Way before range
        }));

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetHistoryAsync(
            SensorId.From(NoReadingsSensor),
            baseTime.AddHours(-1),
            baseTime);

        // Then
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetHistoryAsync_GivenReadingsFromDifferentSensors_WhenCalled_ThenReturnsOnlyRequestedSensorReadings()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx =>
        {
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = RequestedSensor,
                Temperature = Temperature20,
                Timestamp = baseTime
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OtherSensor,
                Temperature = Temperature25,
                Timestamp = baseTime
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetHistoryAsync(
            SensorId.From(RequestedSensor),
            baseTime.AddHours(-1),
            baseTime.AddHours(1));

        // Then
        result.Should().HaveCount(1);
        result[0].SensorId.Value.Should().Be(RequestedSensor);
        result[0].Temperature.Celsius.Should().Be(Temperature20);
    }

    [Fact]
    public async Task GetHistoryAsync_GivenBoundaryTimestamps_WhenCalled_ThenIncludesBoundaryReadings()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var to = from.AddHours(2);

        Given(ctx =>
        {
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = BoundarySensor,
                Temperature = Temperature20,
                Timestamp = from // Exactly at from
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = BoundarySensor,
                Temperature = Temperature22,
                Timestamp = to // Exactly at to
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        // When
        var result = await sut.GetHistoryAsync(SensorId.From(BoundarySensor), from, to);

        // Then
        result.Should().HaveCount(2);
        result.Should().Contain(r => r.Temperature.Celsius == Temperature20);
        result.Should().Contain(r => r.Temperature.Celsius == Temperature22);
    }

    #endregion

    #region GetHistoryBatchAsync

    [Fact]
    public async Task GetHistoryBatchAsync_GivenMultipleSensors_WhenCalled_ThenReturnsGroupedReadings()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx =>
        {
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = BatchSensor1,
                Temperature = Temperature20,
                Timestamp = baseTime
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = BatchSensor1,
                Temperature = Temperature21,
                Timestamp = baseTime.AddMinutes(5)
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = BatchSensor2,
                Temperature = Temperature25,
                Timestamp = baseTime
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = BatchSensor3,
                Temperature = Temperature30,
                Timestamp = baseTime
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorIds = new List<SensorId>
        {
            SensorId.From(BatchSensor1),
            SensorId.From(BatchSensor2)
        };

        // When
        var result = await sut.GetHistoryBatchAsync(
            sensorIds,
            baseTime.AddHours(-1),
            baseTime.AddHours(1));

        // Then
        result.Should().HaveCount(2);
        result.Should().ContainKey(SensorId.From(BatchSensor1));
        result.Should().ContainKey(SensorId.From(BatchSensor2));
        result.Should().NotContainKey(SensorId.From(BatchSensor3));

        result[SensorId.From(BatchSensor1)].Should().HaveCount(2);
        result[SensorId.From(BatchSensor2)].Should().HaveCount(1);
    }

    [Fact]
    public async Task GetHistoryBatchAsync_GivenNoReadingsForRequestedSensors_WhenCalled_ThenReturnsEmptyDictionary()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx => ctx.TemperatureReadings.Add(new TemperatureReadingEntity
        {
            SensorId = OtherSensor,
            Temperature = Temperature20,
            Timestamp = baseTime
        }));

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorIds = new List<SensorId> { SensorId.From(RequestedSensor) };

        // When
        var result = await sut.GetHistoryBatchAsync(
            sensorIds,
            baseTime.AddHours(-1),
            baseTime.AddHours(1));

        // Then
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetHistoryBatchAsync_GivenEmptySensorIdList_WhenCalled_ThenReturnsEmptyDictionary()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorIds = new List<SensorId>();
        var baseTime = DateTimeOffset.UtcNow;

        // When
        var result = await sut.GetHistoryBatchAsync(
            sensorIds,
            baseTime.AddHours(-1),
            baseTime.AddHours(1));

        // Then
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetHistoryBatchAsync_GivenReadingsInRange_WhenCalled_ThenReadingsAreOrderedByTimestamp()
    {
        // Given
        var baseTime = DateTimeOffset.UtcNow;

        Given(ctx =>
        {
            // Add in non-chronological order
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OrderedBatchSensor,
                Temperature = Temperature22,
                Timestamp = baseTime // Third
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OrderedBatchSensor,
                Temperature = Temperature20,
                Timestamp = baseTime.AddMinutes(-20) // First
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = OrderedBatchSensor,
                Temperature = Temperature21,
                Timestamp = baseTime.AddMinutes(-10) // Second
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorIds = new List<SensorId> { SensorId.From(OrderedBatchSensor) };

        // When
        var result = await sut.GetHistoryBatchAsync(
            sensorIds,
            baseTime.AddHours(-1),
            baseTime.AddHours(1));

        // Then
        var readings = result[SensorId.From(OrderedBatchSensor)];
        readings.Should().HaveCount(3);
        readings.Should().BeInAscendingOrder(r => r.Timestamp);
    }

    [Fact]
    public async Task GetHistoryBatchAsync_GivenReadingsOutsideRange_WhenCalled_ThenFiltersCorrectly()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var to = from.AddHours(2);

        Given(ctx =>
        {
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = FilterBatchSensor,
                Temperature = Temperature15,
                Timestamp = from.AddHours(-1) // Before range
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = FilterBatchSensor,
                Temperature = Temperature20,
                Timestamp = from.AddHours(1) // In range
            });
            ctx.TemperatureReadings.Add(new TemperatureReadingEntity
            {
                SensorId = FilterBatchSensor,
                Temperature = Temperature25,
                Timestamp = to.AddHours(1) // After range
            });
        });

        await using var context = CreateContext();
        var sut = new SqlServerTemperatureRepository(context);

        var sensorIds = new List<SensorId> { SensorId.From(FilterBatchSensor) };

        // When
        var result = await sut.GetHistoryBatchAsync(sensorIds, from, to);

        // Then
        var readings = result[SensorId.From(FilterBatchSensor)];
        readings.Should().HaveCount(1);
        readings[0].Temperature.Celsius.Should().Be(Temperature20);
    }

    #endregion
}
