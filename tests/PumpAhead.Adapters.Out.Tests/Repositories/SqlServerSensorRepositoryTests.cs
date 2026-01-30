using FluentAssertions;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Tests.Common.Builders;
using PumpAhead.Tests.Common.Fixtures;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Tests.Repositories;

public class SqlServerSensorRepositoryTests : IntegrationTestBase
{
    private const string SensorId001 = "sensor-001";
    private const string SensorNoLabel = "sensor-no-label";
    private const string NonExistent = "non-existent";
    private const string ActiveSensor1 = "active-1";
    private const string ActiveSensor2 = "active-2";
    private const string InactiveSensor1 = "inactive-1";
    private const string NewSensor = "new-sensor";
    private const string ExistingSensor = "existing-sensor";
    private const string SensorNullLabel = "sensor-null-label";
    private const string SensorToUpdate = "sensor-to-update";
    private const string TestSensorName = "Test Sensor";
    private const string LivingRoomLabel = "Living Room";
    private const string SensorAddress = "28-000005e2fdc3";
    private const string SensorTypeDS18B20 = "DS18B20";
    private const string NewSensorName = "New Temperature Sensor";
    private const string KitchenLabel = "Kitchen";
    private const string NewSensorAddress = "28-000005e2fdc4";
    private const string OldName = "Old Name";
    private const string OldLabel = "Old Label";
    private const string UpdatedName = "Updated Name";
    private const string UpdatedLabel = "Updated Label";
    private const string OriginalName = "Original Name";
    private const string SensorWithoutLabel = "Sensor Without Label";
    private const string NullLabelAddress = "28-000005e2fdc5";

    #region GetByIdAsync

    [Fact]
    public async Task GetByIdAsync_GivenExistingSensor_WhenCalled_ThenReturnsSensorInfo()
    {
        // Given
        var sensorEntity = SensorBuilder.Valid()
            .WithId(SensorId001)
            .WithName(TestSensorName)
            .WithLabel(LivingRoomLabel)
            .WithAddress(SensorAddress)
            .WithType(SensorTypeDS18B20)
            .WithIsActive(true)
            .WithLastSeenAt(DateTimeOffset.UtcNow)
            .Build();

        Given(ctx => ctx.Sensors.Add(sensorEntity));

        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var result = await sut.GetByIdAsync(SensorId.From(SensorId001));

        // Then
        result.Should().NotBeNull();
        result!.Id.Value.Should().Be(SensorId001);
        result.Name.Should().Be(TestSensorName);
        result.Label.Should().Be(LivingRoomLabel);
        result.Address.Should().Be(SensorAddress);
        result.Type.Should().Be(SensorTypeDS18B20);
        result.IsActive.Should().BeTrue();
        result.LastSeenAt.Should().NotBeNull();
    }

    [Fact]
    public async Task GetByIdAsync_GivenNonExistentSensor_WhenCalled_ThenReturnsNull()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var result = await sut.GetByIdAsync(SensorId.From(NonExistent));

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetByIdAsync_GivenSensorWithNullLabel_WhenCalled_ThenReturnsNullLabel()
    {
        // Given
        var sensorEntity = SensorBuilder.Valid()
            .WithId(SensorNoLabel)
            .WithLabel(null)
            .Build();

        Given(ctx => ctx.Sensors.Add(sensorEntity));

        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var result = await sut.GetByIdAsync(SensorId.From(SensorNoLabel));

        // Then
        result.Should().NotBeNull();
        result!.Label.Should().BeNull();
    }

    #endregion

    #region GetAllActiveAsync

    [Fact]
    public async Task GetAllActiveAsync_GivenMultipleSensors_WhenCalled_ThenReturnsOnlyActiveSensors()
    {
        // Given
        var activeSensor1 = SensorBuilder.Valid()
            .WithId(ActiveSensor1)
            .WithIsActive(true)
            .Build();
        var activeSensor2 = SensorBuilder.Valid()
            .WithId(ActiveSensor2)
            .WithIsActive(true)
            .Build();
        var inactiveSensor = SensorBuilder.Inactive()
            .WithId(InactiveSensor1)
            .Build();

        Given(ctx =>
        {
            ctx.Sensors.Add(activeSensor1);
            ctx.Sensors.Add(activeSensor2);
            ctx.Sensors.Add(inactiveSensor);
        });

        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var result = await sut.GetAllActiveAsync();

        // Then
        result.Should().HaveCount(2);
        result.Should().OnlyContain(s => s.IsActive);
        result.Select(s => s.Id.Value).Should().Contain([ActiveSensor1, ActiveSensor2]);
    }

    [Fact]
    public async Task GetAllActiveAsync_GivenNoActiveSensors_WhenCalled_ThenReturnsEmptyList()
    {
        // Given
        var inactiveSensor = SensorBuilder.Inactive()
            .WithId(InactiveSensor1)
            .Build();

        Given(ctx => ctx.Sensors.Add(inactiveSensor));

        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var result = await sut.GetAllActiveAsync();

        // Then
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetAllActiveAsync_GivenEmptyDatabase_WhenCalled_ThenReturnsEmptyList()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var result = await sut.GetAllActiveAsync();

        // Then
        result.Should().BeEmpty();
    }

    #endregion

    #region SaveAsync

    [Fact]
    public async Task SaveAsync_GivenNewSensor_WhenCalled_ThenSensorIsPersistedToDatabase()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        var sensorInfo = new SensorInfo(
            SensorId.From(NewSensor),
            NewSensorName,
            KitchenLabel,
            NewSensorAddress,
            SensorTypeDS18B20,
            true,
            DateTimeOffset.UtcNow);

        // When
        await sut.SaveAsync(sensorInfo);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntity = verifyContext.Sensors.FirstOrDefault(s => s.Id == NewSensor);
        savedEntity.Should().NotBeNull();
        savedEntity!.Name.Should().Be(NewSensorName);
        savedEntity.Label.Should().Be(KitchenLabel);
        savedEntity.Address.Should().Be(NewSensorAddress);
        savedEntity.Type.Should().Be(SensorTypeDS18B20);
        savedEntity.IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task SaveAsync_GivenExistingSensor_WhenCalled_ThenSensorIsUpdated()
    {
        // Given
        var existingSensor = SensorBuilder.Valid()
            .WithId(ExistingSensor)
            .WithName(OldName)
            .WithLabel(OldLabel)
            .Build();

        Given(ctx => ctx.Sensors.Add(existingSensor));

        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        var updatedSensorInfo = new SensorInfo(
            SensorId.From(ExistingSensor),
            UpdatedName,
            UpdatedLabel,
            existingSensor.Address,
            existingSensor.Type,
            false,
            DateTimeOffset.UtcNow);

        // When
        await sut.SaveAsync(updatedSensorInfo);

        // Then
        await using var verifyContext = CreateContext();
        var updatedEntity = verifyContext.Sensors.FirstOrDefault(s => s.Id == ExistingSensor);
        updatedEntity.Should().NotBeNull();
        updatedEntity!.Name.Should().Be(UpdatedName);
        updatedEntity.Label.Should().Be(UpdatedLabel);
        updatedEntity.IsActive.Should().BeFalse();
    }

    [Fact]
    public async Task SaveAsync_GivenSensorWithNullLabel_WhenCalled_ThenNullLabelIsPersisted()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        var sensorInfo = new SensorInfo(
            SensorId.From(SensorNullLabel),
            SensorWithoutLabel,
            null,
            NullLabelAddress,
            SensorTypeDS18B20,
            true,
            null);

        // When
        await sut.SaveAsync(sensorInfo);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntity = verifyContext.Sensors.FirstOrDefault(s => s.Id == SensorNullLabel);
        savedEntity.Should().NotBeNull();
        savedEntity!.Label.Should().BeNull();
        savedEntity.LastSeenAt.Should().BeNull();
    }

    #endregion

    #region UpdateLastSeenAsync

    // Note: ExecuteUpdateAsync is not supported by InMemory provider.
    // These tests require a real database (SQL Server) to run.
    // For integration tests with real DB, consider using Testcontainers.

    [Fact(Skip = "ExecuteUpdateAsync is not supported by InMemory database provider")]
    public async Task UpdateLastSeenAsync_GivenExistingSensor_WhenCalled_ThenOnlyLastSeenAtIsUpdated()
    {
        // Given
        var originalTimestamp = DateTimeOffset.UtcNow.AddDays(-1);
        var existingSensor = SensorBuilder.Valid()
            .WithId(SensorToUpdate)
            .WithName(OriginalName)
            .WithLastSeenAt(originalTimestamp)
            .Build();

        Given(ctx => ctx.Sensors.Add(existingSensor));

        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        var newTimestamp = DateTimeOffset.UtcNow;

        // When
        await sut.UpdateLastSeenAsync(SensorId.From(SensorToUpdate), newTimestamp);

        // Then
        await using var verifyContext = CreateContext();
        var updatedEntity = verifyContext.Sensors.FirstOrDefault(s => s.Id == SensorToUpdate);
        updatedEntity.Should().NotBeNull();
        updatedEntity!.LastSeenAt.Should().Be(newTimestamp);
        updatedEntity.Name.Should().Be(OriginalName); // Other fields unchanged
    }

    [Fact(Skip = "ExecuteUpdateAsync is not supported by InMemory database provider")]
    public async Task UpdateLastSeenAsync_GivenNonExistentSensor_WhenCalled_ThenNoExceptionThrown()
    {
        // Given
        await using var context = CreateContext();
        var sut = new SqlServerSensorRepository(context);

        // When
        var act = async () => await sut.UpdateLastSeenAsync(
            SensorId.From(NonExistent),
            DateTimeOffset.UtcNow);

        // Then
        await act.Should().NotThrowAsync();
    }

    #endregion
}
