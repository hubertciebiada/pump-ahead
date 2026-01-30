using FluentAssertions;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Tests.Common.Builders;
using PumpAhead.Tests.Common.Fixtures;

namespace PumpAhead.Adapters.Out.Tests.Repositories;

public class SqlServerHeatPumpSnapshotRepositoryTests : IntegrationTestBase
{
    #region SaveSnapshotAsync

    [Fact]
    public async Task SaveSnapshotAsync_GivenValidSnapshot_WhenSaved_ThenPersistsToDatabase()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var snapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .Build();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(context);

        // When
        await sut.SaveSnapshotAsync(snapshot);

        // Then
        await using var verifyContext = CreateContext();
        var entity = verifyContext.HeatPumpSnapshots
            .FirstOrDefault(s => s.HeatPumpId == heatPumpId.Value);

        entity.Should().NotBeNull();
        entity!.HeatPumpId.Should().Be(heatPumpId.Value);
    }

    [Fact]
    public async Task SaveSnapshotAsync_GivenValidSnapshot_WhenSaved_ThenPersistsAllFields()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var timestamp = DateTimeOffset.UtcNow;

        var snapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(timestamp)
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.HeatDhw)
            .WithPumpFlow(14.5m)
            .WithOutsideTemperature(7.0m)
            .WithCentralHeating(32.0m, 36.0m, 42.0m)
            .WithDomesticHotWater(46.0m, 52.0m)
            .WithCompressorFrequency(58.0m)
            .WithHeatingPower(4200, 1100)
            .WithOperations(1800, 400)
            .WithDefrost(DefrostData.Active)
            .WithErrorCode(ErrorCode.From("H20"))
            .Build();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(context);

        // When
        await sut.SaveSnapshotAsync(snapshot);

        // Then
        await using var verifyContext = CreateContext();
        var entity = verifyContext.HeatPumpSnapshots
            .FirstOrDefault(s => s.HeatPumpId == heatPumpId.Value);

        entity.Should().NotBeNull();
        entity!.Timestamp.Should().Be(timestamp);
        entity.IsOn.Should().BeTrue();
        entity.OperatingMode.Should().Be((int)OperatingMode.HeatDhw);
        entity.PumpFlow.Should().Be(14.5m);
        entity.OutsideTemperature.Should().Be(7.0m);
        entity.CH_InletTemperature.Should().Be(32.0m);
        entity.CH_OutletTemperature.Should().Be(36.0m);
        entity.CH_TargetTemperature.Should().Be(42.0m);
        entity.DHW_ActualTemperature.Should().Be(46.0m);
        entity.DHW_TargetTemperature.Should().Be(52.0m);
        entity.Compressor_Frequency.Should().Be(58.0m);
        entity.Power_HeatProduction.Should().Be(4200);
        entity.Power_HeatConsumption.Should().Be(1100);
        entity.Operations_CompressorHours.Should().Be(1800);
        entity.Operations_CompressorStarts.Should().Be(400);
        entity.Defrost_IsActive.Should().BeTrue();
        entity.ErrorCode.Should().Be("H20");
    }

    [Fact]
    public async Task SaveSnapshotAsync_GivenMultipleSnapshots_WhenSaved_ThenAllArePersisted()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var snapshot1 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddMinutes(-10))
            .WithOutsideTemperature(5.0m)
            .Build();

        var snapshot2 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddMinutes(-5))
            .WithOutsideTemperature(6.0m)
            .Build();

        var snapshot3 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime)
            .WithOutsideTemperature(7.0m)
            .Build();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(context);

        // When
        await sut.SaveSnapshotAsync(snapshot1);
        await sut.SaveSnapshotAsync(snapshot2);
        await sut.SaveSnapshotAsync(snapshot3);

        // Then
        await using var verifyContext = CreateContext();
        var count = verifyContext.HeatPumpSnapshots
            .Count(s => s.HeatPumpId == heatPumpId.Value);

        count.Should().Be(3);
    }

    #endregion

    #region GetHistoryAsync - Returns Snapshots

    [Fact]
    public async Task GetHistoryAsync_GivenSnapshotsInRange_WhenQueried_ThenReturnsSnapshotsInRange()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var beforeRange = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddHours(-3))
            .WithOutsideTemperature(1.0m)
            .Build();

        var inRange1 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddHours(-2))
            .WithOutsideTemperature(2.0m)
            .Build();

        var inRange2 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddHours(-1))
            .WithOutsideTemperature(3.0m)
            .Build();

        var afterRange = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddMinutes(1))
            .WithOutsideTemperature(4.0m)
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(beforeRange);
            await setupRepo.SaveSnapshotAsync(inRange1);
            await setupRepo.SaveSnapshotAsync(inRange2);
            await setupRepo.SaveSnapshotAsync(afterRange);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetHistoryAsync(
            heatPumpId,
            from: baseTime.AddHours(-2),
            to: baseTime);

        // Then
        result.Should().HaveCount(2);
        result.Select(s => s.OutsideTemperature.Celsius)
            .Should().ContainInOrder(2.0m, 3.0m);
    }

    [Fact]
    public async Task GetHistoryAsync_GivenSnapshotsExist_WhenQueried_ThenReturnsCorrectlyMappedSnapshots()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var timestamp = DateTimeOffset.UtcNow.AddMinutes(-30);

        var snapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(timestamp)
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.CoolOnly)
            .WithPumpFlow(11.0m)
            .WithOutsideTemperature(28.0m)
            .WithCentralHeating(24.0m, 22.0m, 20.0m)
            .WithDomesticHotWater(50.0m, 55.0m)
            .WithCompressorFrequency(65.0m)
            .WithHeatingPower(0, 0)
            .WithOperations(2500, 600)
            .WithDefrost(DefrostData.Inactive)
            .WithErrorCode(ErrorCode.None)
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(snapshot);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetHistoryAsync(
            heatPumpId,
            from: timestamp.AddMinutes(-1),
            to: timestamp.AddMinutes(1));

        // Then
        result.Should().HaveCount(1);
        var retrieved = result.Single();

        retrieved.HeatPumpId.Should().Be(heatPumpId);
        retrieved.Timestamp.Should().Be(timestamp);
        retrieved.IsOn.Should().BeTrue();
        retrieved.OperatingMode.Should().Be(OperatingMode.CoolOnly);
        retrieved.PumpFlow.LitersPerMinute.Should().Be(11.0m);
        retrieved.OutsideTemperature.Celsius.Should().Be(28.0m);
        retrieved.CentralHeating.InletTemperature.Celsius.Should().Be(24.0m);
        retrieved.CentralHeating.OutletTemperature.Celsius.Should().Be(22.0m);
        retrieved.CentralHeating.TargetTemperature.Celsius.Should().Be(20.0m);
        retrieved.DomesticHotWater.ActualTemperature.Celsius.Should().Be(50.0m);
        retrieved.DomesticHotWater.TargetTemperature.Celsius.Should().Be(55.0m);
        retrieved.CompressorFrequency.Hertz.Should().Be(65.0m);
        retrieved.Power.HeatProduction.Watts.Should().Be(0);
        retrieved.Power.HeatConsumption.Watts.Should().Be(0);
        retrieved.Operations.CompressorHours.Should().Be(2500);
        retrieved.Operations.CompressorStarts.Should().Be(600);
        retrieved.Defrost.IsActive.Should().BeFalse();
        retrieved.ErrorCode.Should().Be(ErrorCode.None);
    }

    [Fact]
    public async Task GetHistoryAsync_GivenSnapshots_WhenQueried_ThenReturnsOrderedByTimestampAscending()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var snapshot3 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime)
            .WithOutsideTemperature(10.0m)
            .Build();

        var snapshot1 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddMinutes(-20))
            .WithOutsideTemperature(8.0m)
            .Build();

        var snapshot2 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddMinutes(-10))
            .WithOutsideTemperature(9.0m)
            .Build();

        // Save in non-chronological order
        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(snapshot3);
            await setupRepo.SaveSnapshotAsync(snapshot1);
            await setupRepo.SaveSnapshotAsync(snapshot2);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetHistoryAsync(
            heatPumpId,
            from: baseTime.AddMinutes(-25),
            to: baseTime.AddMinutes(5));

        // Then
        result.Should().HaveCount(3);
        result.Select(s => s.OutsideTemperature.Celsius)
            .Should().ContainInOrder(8.0m, 9.0m, 10.0m);
    }

    [Fact]
    public async Task GetHistoryAsync_GivenNoSnapshotsInRange_WhenQueried_ThenReturnsEmptyList()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var snapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddHours(-5))
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(snapshot);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetHistoryAsync(
            heatPumpId,
            from: baseTime.AddHours(-2),
            to: baseTime);

        // Then
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetHistoryAsync_GivenDifferentHeatPumpIds_WhenQueried_ThenReturnsOnlyMatchingSnapshots()
    {
        // Given
        var heatPumpId1 = HeatPumpId.NewId();
        var heatPumpId2 = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var snapshot1 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId1)
            .WithTimestamp(baseTime)
            .WithOutsideTemperature(5.0m)
            .Build();

        var snapshot2 = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId2)
            .WithTimestamp(baseTime)
            .WithOutsideTemperature(10.0m)
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(snapshot1);
            await setupRepo.SaveSnapshotAsync(snapshot2);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetHistoryAsync(
            heatPumpId1,
            from: baseTime.AddMinutes(-1),
            to: baseTime.AddMinutes(1));

        // Then
        result.Should().HaveCount(1);
        result.Single().HeatPumpId.Should().Be(heatPumpId1);
        result.Single().OutsideTemperature.Celsius.Should().Be(5.0m);
    }

    #endregion

    #region GetLatestSnapshotAsync

    [Fact]
    public async Task GetLatestSnapshotAsync_GivenMultipleSnapshots_WhenQueried_ThenReturnsMostRecent()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var oldSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddHours(-2))
            .WithOutsideTemperature(5.0m)
            .Build();

        var middleSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime.AddHours(-1))
            .WithOutsideTemperature(7.0m)
            .Build();

        var latestSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(baseTime)
            .WithOutsideTemperature(10.0m)
            .Build();

        // Save in non-chronological order
        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(middleSnapshot);
            await setupRepo.SaveSnapshotAsync(latestSnapshot);
            await setupRepo.SaveSnapshotAsync(oldSnapshot);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetLatestSnapshotAsync(heatPumpId);

        // Then
        result.Should().NotBeNull();
        result!.Timestamp.Should().Be(baseTime);
        result.OutsideTemperature.Celsius.Should().Be(10.0m);
    }

    [Fact]
    public async Task GetLatestSnapshotAsync_GivenNoSnapshots_WhenQueried_ThenReturnsNull()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();

        // When
        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(context);
        var result = await sut.GetLatestSnapshotAsync(heatPumpId);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetLatestSnapshotAsync_GivenSnapshotsForDifferentHeatPumps_WhenQueried_ThenReturnsLatestForSpecificHeatPump()
    {
        // Given
        var targetHeatPumpId = HeatPumpId.NewId();
        var otherHeatPumpId = HeatPumpId.NewId();
        var baseTime = DateTimeOffset.UtcNow;

        var targetOldSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(targetHeatPumpId)
            .WithTimestamp(baseTime.AddHours(-2))
            .WithOutsideTemperature(5.0m)
            .Build();

        var targetLatestSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(targetHeatPumpId)
            .WithTimestamp(baseTime.AddHours(-1))
            .WithOutsideTemperature(8.0m)
            .Build();

        var otherNewerSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(otherHeatPumpId)
            .WithTimestamp(baseTime)
            .WithOutsideTemperature(15.0m)
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(targetOldSnapshot);
            await setupRepo.SaveSnapshotAsync(targetLatestSnapshot);
            await setupRepo.SaveSnapshotAsync(otherNewerSnapshot);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetLatestSnapshotAsync(targetHeatPumpId);

        // Then
        result.Should().NotBeNull();
        result!.HeatPumpId.Should().Be(targetHeatPumpId);
        result.Timestamp.Should().Be(baseTime.AddHours(-1));
        result.OutsideTemperature.Celsius.Should().Be(8.0m);
    }

    [Fact]
    public async Task GetLatestSnapshotAsync_GivenSnapshot_WhenQueried_ThenReturnsCorrectlyMappedSnapshot()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var timestamp = DateTimeOffset.UtcNow;

        var snapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(timestamp)
            .WithIsOn(false)
            .WithOperatingMode(OperatingMode.DhwOnly)
            .WithPumpFlow(0m)
            .WithOutsideTemperature(-10.0m)
            .WithCentralHeating(20.0m, 19.0m, 18.0m)
            .WithDomesticHotWater(42.0m, 50.0m)
            .WithCompressorFrequency(0m)
            .WithHeatingPower(0, 0)
            .WithOperations(5000, 1200)
            .WithDefrost(DefrostData.Inactive)
            .WithErrorCode(ErrorCode.From("E01"))
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            await setupRepo.SaveSnapshotAsync(snapshot);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetLatestSnapshotAsync(heatPumpId);

        // Then
        result.Should().NotBeNull();
        result!.HeatPumpId.Should().Be(heatPumpId);
        result.Timestamp.Should().Be(timestamp);
        result.IsOn.Should().BeFalse();
        result.OperatingMode.Should().Be(OperatingMode.DhwOnly);
        result.PumpFlow.LitersPerMinute.Should().Be(0m);
        result.OutsideTemperature.Celsius.Should().Be(-10.0m);
        result.CentralHeating.InletTemperature.Celsius.Should().Be(20.0m);
        result.CentralHeating.OutletTemperature.Celsius.Should().Be(19.0m);
        result.CentralHeating.TargetTemperature.Celsius.Should().Be(18.0m);
        result.DomesticHotWater.ActualTemperature.Celsius.Should().Be(42.0m);
        result.DomesticHotWater.TargetTemperature.Celsius.Should().Be(50.0m);
        result.CompressorFrequency.Hertz.Should().Be(0m);
        result.Power.HeatProduction.Watts.Should().Be(0);
        result.Power.HeatConsumption.Watts.Should().Be(0);
        result.Operations.CompressorHours.Should().Be(5000);
        result.Operations.CompressorStarts.Should().Be(1200);
        result.Defrost.IsActive.Should().BeFalse();
        result.ErrorCode.Code.Should().Be("E01");
    }

    #endregion

    #region Integration - Using HeatPumpSnapshotBuilder.CreateSeries

    [Fact]
    public async Task GetHistoryAsync_GivenSnapshotSeries_WhenQueried_ThenReturnsCorrectCount()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var startTime = DateTimeOffset.UtcNow.AddHours(-2);
        var interval = TimeSpan.FromMinutes(5);
        var snapshotCount = 10;

        var snapshots = HeatPumpSnapshotBuilder
            .CreateSeries(heatPumpId, snapshotCount, interval, startTime)
            .ToList();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpSnapshotRepository(setupContext);
            foreach (var snapshot in snapshots)
            {
                await setupRepo.SaveSnapshotAsync(snapshot);
            }
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpSnapshotRepository(queryContext);
        var result = await sut.GetHistoryAsync(
            heatPumpId,
            from: startTime.AddMinutes(-1),
            to: startTime.AddMinutes(snapshotCount * interval.TotalMinutes + 1));

        // Then
        result.Should().HaveCount(snapshotCount);
    }

    #endregion
}
