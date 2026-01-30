using FluentAssertions;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Tests.Common.Builders;
using PumpAhead.Tests.Common.Fixtures;

namespace PumpAhead.Adapters.Out.Tests.Repositories;

public class SqlServerHeatPumpRepositoryTests : IntegrationTestBase
{
    #region SaveAsync

    [Fact]
    public async Task SaveAsync_GivenNewHeatPump_WhenSaved_ThenPersistsToDatabase()
    {
        // Given
        var heatPump = HeatPumpBuilder.Valid()
            .WithModel("Panasonic WH-MDC09J3E5")
            .Build();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);

        // When
        await sut.SaveAsync(heatPump);

        // Then
        await using var verifyContext = CreateContext();
        var entity = await verifyContext.HeatPumps.FindAsync(heatPump.Id.Value);
        entity.Should().NotBeNull();
        entity!.Model.Should().Be("Panasonic WH-MDC09J3E5");
    }

    [Fact]
    public async Task SaveAsync_GivenNewHeatPump_WhenSaved_ThenPersistsAllFields()
    {
        // Given
        var expectedModel = "Test Model XYZ";
        var expectedLastSyncTime = DateTimeOffset.UtcNow;
        var heatPump = HeatPumpBuilder.Valid()
            .WithModel(expectedModel)
            .WithLastSyncTime(expectedLastSyncTime)
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.HeatDhw)
            .WithPumpFlow(15.5m)
            .WithOutsideTemperature(8.0m)
            .WithCentralHeating(30.0m, 35.0m, 40.0m)
            .WithDomesticHotWater(45.0m, 50.0m)
            .WithCompressorFrequency(55.0m)
            .WithHeatingPower(4000, 1200)
            .WithOperations(2000, 500)
            .WithDefrost(DefrostData.Active)
            .WithErrorCode(ErrorCode.From("H15"))
            .Build();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);

        // When
        await sut.SaveAsync(heatPump);

        // Then
        await using var verifyContext = CreateContext();
        var entity = await verifyContext.HeatPumps.FindAsync(heatPump.Id.Value);

        entity.Should().NotBeNull();
        entity!.Model.Should().Be(expectedModel);
        entity.LastSyncTime.Should().Be(expectedLastSyncTime);
        entity.IsOn.Should().BeTrue();
        entity.OperatingMode.Should().Be((int)OperatingMode.HeatDhw);
        entity.PumpFlow.Should().Be(15.5m);
        entity.OutsideTemperature.Should().Be(8.0m);
        entity.CH_InletTemperature.Should().Be(30.0m);
        entity.CH_OutletTemperature.Should().Be(35.0m);
        entity.CH_TargetTemperature.Should().Be(40.0m);
        entity.DHW_ActualTemperature.Should().Be(45.0m);
        entity.DHW_TargetTemperature.Should().Be(50.0m);
        entity.Compressor_Frequency.Should().Be(55.0m);
        entity.Power_HeatProduction.Should().Be(4000);
        entity.Power_HeatConsumption.Should().Be(1200);
        entity.Operations_CompressorHours.Should().Be(2000);
        entity.Operations_CompressorStarts.Should().Be(500);
        entity.Defrost_IsActive.Should().BeTrue();
        entity.ErrorCode.Should().Be("H15");
    }

    #endregion

    #region GetByIdAsync - Not Found

    [Fact]
    public async Task GetByIdAsync_GivenNonExistentId_WhenQueried_ThenReturnsNull()
    {
        // Given
        var nonExistentId = HeatPumpId.NewId();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);

        // When
        var result = await sut.GetByIdAsync(nonExistentId);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetByIdAsync_GivenEmptyDatabase_WhenQueried_ThenReturnsNull()
    {
        // Given
        var anyId = HeatPumpId.NewId();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);

        // When
        var result = await sut.GetByIdAsync(anyId);

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region GetByIdAsync - Returns Correctly Mapped Aggregate

    [Fact]
    public async Task GetByIdAsync_GivenExistingHeatPump_WhenQueried_ThenReturnsCorrectlyMappedAggregate()
    {
        // Given
        var expectedModel = "Panasonic WH-MDC09J3E5";
        var expectedLastSyncTime = DateTimeOffset.UtcNow;
        var heatPump = HeatPumpBuilder.Valid()
            .WithModel(expectedModel)
            .WithLastSyncTime(expectedLastSyncTime)
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.CoolOnly)
            .WithPumpFlow(12.5m)
            .WithOutsideTemperature(25.0m)
            .WithCentralHeating(28.0m, 30.0m, 32.0m)
            .WithDomesticHotWater(48.0m, 50.0m)
            .WithCompressorFrequency(60.0m)
            .WithHeatingPower(3500, 1000)
            .WithOperations(1500, 250)
            .WithDefrost(DefrostData.Inactive)
            .WithErrorCode(ErrorCode.None)
            .Build();

        // Persist using one context
        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        // When - Query using separate context
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpRepository(queryContext);
        var result = await sut.GetByIdAsync(heatPump.Id);

        // Then
        result.Should().NotBeNull();
        result!.Id.Should().Be(heatPump.Id);
        result.Model.Should().Be(expectedModel);
        result.LastSyncTime.Should().Be(expectedLastSyncTime);
        result.IsOn.Should().BeTrue();
        result.OperatingMode.Should().Be(OperatingMode.CoolOnly);
        result.PumpFlow.LitersPerMinute.Should().Be(12.5m);
        result.OutsideTemperature.Celsius.Should().Be(25.0m);
        result.CentralHeating.InletTemperature.Celsius.Should().Be(28.0m);
        result.CentralHeating.OutletTemperature.Celsius.Should().Be(30.0m);
        result.CentralHeating.TargetTemperature.Celsius.Should().Be(32.0m);
        result.DomesticHotWater.ActualTemperature.Celsius.Should().Be(48.0m);
        result.DomesticHotWater.TargetTemperature.Celsius.Should().Be(50.0m);
        result.CompressorFrequency.Hertz.Should().Be(60.0m);
        result.Power.HeatProduction.Watts.Should().Be(3500);
        result.Power.HeatConsumption.Watts.Should().Be(1000);
        result.Operations.CompressorHours.Should().Be(1500);
        result.Operations.CompressorStarts.Should().Be(250);
        result.Defrost.IsActive.Should().BeFalse();
        result.ErrorCode.Should().Be(ErrorCode.None);
    }

    [Fact]
    public async Task GetByIdAsync_GivenHeatPumpWithError_WhenQueried_ThenMapsErrorCodeCorrectly()
    {
        // Given
        var heatPump = HeatPumpBuilder.WithError("H99")
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpRepository(queryContext);
        var result = await sut.GetByIdAsync(heatPump.Id);

        // Then
        result.Should().NotBeNull();
        result!.ErrorCode.Code.Should().Be("H99");
    }

    [Fact]
    public async Task GetByIdAsync_GivenDefrostingHeatPump_WhenQueried_ThenMapsDefrostCorrectly()
    {
        // Given
        var heatPump = HeatPumpBuilder.Defrosting()
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpRepository(queryContext);
        var result = await sut.GetByIdAsync(heatPump.Id);

        // Then
        result.Should().NotBeNull();
        result!.Defrost.IsActive.Should().BeTrue();
    }

    #endregion

    #region SaveAsync - Update Existing Record

    [Fact]
    public async Task SaveAsync_GivenExistingHeatPump_WhenUpdated_ThenUpdatesRecord()
    {
        // Given
        var heatPump = HeatPumpBuilder.Valid()
            .WithModel("Original Model")
            .WithOutsideTemperature(10.0m)
            .Build();

        // Save initial version
        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        // Create updated version with same ID
        var updatedHeatPump = HeatPumpBuilder.Valid()
            .WithId(heatPump.Id)
            .WithModel("Updated Model")
            .WithOutsideTemperature(20.0m)
            .Build();

        // When
        await using (var updateContext = CreateContext())
        {
            var sut = new SqlServerHeatPumpRepository(updateContext);
            await sut.SaveAsync(updatedHeatPump);
        }

        // Then
        await using var verifyContext = CreateContext();
        var entity = await verifyContext.HeatPumps.FindAsync(heatPump.Id.Value);
        entity.Should().NotBeNull();
        entity!.Model.Should().Be("Updated Model");
        entity.OutsideTemperature.Should().Be(20.0m);
    }

    [Fact]
    public async Task SaveAsync_GivenExistingHeatPump_WhenUpdated_ThenDoesNotCreateDuplicateRecord()
    {
        // Given
        var heatPump = HeatPumpBuilder.Valid().Build();

        // Save initial version
        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        // Update the same heat pump
        var updatedHeatPump = HeatPumpBuilder.Valid()
            .WithId(heatPump.Id)
            .WithModel("Updated Model")
            .Build();

        // When
        await using (var updateContext = CreateContext())
        {
            var sut = new SqlServerHeatPumpRepository(updateContext);
            await sut.SaveAsync(updatedHeatPump);
        }

        // Then
        await using var verifyContext = CreateContext();
        var count = verifyContext.HeatPumps.Count();
        count.Should().Be(1);
    }

    [Fact]
    public async Task SaveAsync_GivenExistingHeatPump_WhenUpdated_ThenUpdatesAllFields()
    {
        // Given
        var heatPump = HeatPumpBuilder.Valid()
            .WithIsOn(false)
            .WithOperatingMode(OperatingMode.HeatOnly)
            .WithPumpFlow(5.0m)
            .WithCompressorFrequency(0m)
            .WithDefrost(DefrostData.Inactive)
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        var updatedTime = DateTimeOffset.UtcNow.AddMinutes(5);
        var updatedHeatPump = HeatPumpBuilder.Valid()
            .WithId(heatPump.Id)
            .WithModel("New Model")
            .WithLastSyncTime(updatedTime)
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.HeatDhw)
            .WithPumpFlow(15.0m)
            .WithOutsideTemperature(-5.0m)
            .WithCentralHeating(35.0m, 40.0m, 45.0m)
            .WithDomesticHotWater(52.0m, 55.0m)
            .WithCompressorFrequency(70.0m)
            .WithHeatingPower(5000, 1500)
            .WithOperations(3000, 750)
            .WithDefrost(DefrostData.Active)
            .WithErrorCode(ErrorCode.From("F12"))
            .Build();

        // When
        await using (var updateContext = CreateContext())
        {
            var sut = new SqlServerHeatPumpRepository(updateContext);
            await sut.SaveAsync(updatedHeatPump);
        }

        // Then
        await using var verifyContext = CreateContext();
        var entity = await verifyContext.HeatPumps.FindAsync(heatPump.Id.Value);

        entity.Should().NotBeNull();
        entity!.Model.Should().Be("New Model");
        entity.LastSyncTime.Should().Be(updatedTime);
        entity.IsOn.Should().BeTrue();
        entity.OperatingMode.Should().Be((int)OperatingMode.HeatDhw);
        entity.PumpFlow.Should().Be(15.0m);
        entity.OutsideTemperature.Should().Be(-5.0m);
        entity.CH_InletTemperature.Should().Be(35.0m);
        entity.CH_OutletTemperature.Should().Be(40.0m);
        entity.CH_TargetTemperature.Should().Be(45.0m);
        entity.DHW_ActualTemperature.Should().Be(52.0m);
        entity.DHW_TargetTemperature.Should().Be(55.0m);
        entity.Compressor_Frequency.Should().Be(70.0m);
        entity.Power_HeatProduction.Should().Be(5000);
        entity.Power_HeatConsumption.Should().Be(1500);
        entity.Operations_CompressorHours.Should().Be(3000);
        entity.Operations_CompressorStarts.Should().Be(750);
        entity.Defrost_IsActive.Should().BeTrue();
        entity.ErrorCode.Should().Be("F12");
    }

    #endregion

    #region ExistsAsync

    [Fact]
    public async Task ExistsAsync_GivenExistingHeatPump_WhenChecked_ThenReturnsTrue()
    {
        // Given
        var heatPump = HeatPumpBuilder.Valid().Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpRepository(queryContext);
        var result = await sut.ExistsAsync(heatPump.Id);

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public async Task ExistsAsync_GivenNonExistentHeatPump_WhenChecked_ThenReturnsFalse()
    {
        // Given
        var nonExistentId = HeatPumpId.NewId();

        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);

        // When
        var result = await sut.ExistsAsync(nonExistentId);

        // Then
        result.Should().BeFalse();
    }

    #endregion

    #region GetAllAsync

    [Fact]
    public async Task GetAllAsync_GivenMultipleHeatPumps_WhenQueried_ThenReturnsAll()
    {
        // Given
        var heatPump1 = HeatPumpBuilder.Valid().WithModel("Model A").Build();
        var heatPump2 = HeatPumpBuilder.Valid().WithModel("Model B").Build();
        var heatPump3 = HeatPumpBuilder.Valid().WithModel("Model C").Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(heatPump1);
            await setupRepo.SaveAsync(heatPump2);
            await setupRepo.SaveAsync(heatPump3);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpRepository(queryContext);
        var result = await sut.GetAllAsync();

        // Then
        result.Should().HaveCount(3);
        result.Select(hp => hp.Model).Should().Contain(["Model A", "Model B", "Model C"]);
    }

    [Fact]
    public async Task GetAllAsync_GivenEmptyDatabase_WhenQueried_ThenReturnsEmptyList()
    {
        // Given - empty database

        // When
        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);
        var result = await sut.GetAllAsync();

        // Then
        result.Should().BeEmpty();
    }

    #endregion

    #region GetDefaultAsync

    [Fact]
    public async Task GetDefaultAsync_GivenMultipleHeatPumps_WhenQueried_ThenReturnsMostRecentlySynced()
    {
        // Given
        var oldSyncTime = DateTimeOffset.UtcNow.AddHours(-2);
        var newerSyncTime = DateTimeOffset.UtcNow.AddHours(-1);
        var newestSyncTime = DateTimeOffset.UtcNow;

        var oldestHeatPump = HeatPumpBuilder.Valid()
            .WithModel("Oldest")
            .WithLastSyncTime(oldSyncTime)
            .Build();
        var middleHeatPump = HeatPumpBuilder.Valid()
            .WithModel("Middle")
            .WithLastSyncTime(newerSyncTime)
            .Build();
        var newestHeatPump = HeatPumpBuilder.Valid()
            .WithModel("Newest")
            .WithLastSyncTime(newestSyncTime)
            .Build();

        await using (var setupContext = CreateContext())
        {
            var setupRepo = new SqlServerHeatPumpRepository(setupContext);
            await setupRepo.SaveAsync(oldestHeatPump);
            await setupRepo.SaveAsync(middleHeatPump);
            await setupRepo.SaveAsync(newestHeatPump);
        }

        // When
        await using var queryContext = CreateContext();
        var sut = new SqlServerHeatPumpRepository(queryContext);
        var result = await sut.GetDefaultAsync();

        // Then
        result.Should().NotBeNull();
        result!.Model.Should().Be("Newest");
        result.Id.Should().Be(newestHeatPump.Id);
    }

    [Fact]
    public async Task GetDefaultAsync_GivenEmptyDatabase_WhenQueried_ThenReturnsNull()
    {
        // Given - empty database

        // When
        await using var context = CreateContext();
        var sut = new SqlServerHeatPumpRepository(context);
        var result = await sut.GetDefaultAsync();

        // Then
        result.Should().BeNull();
    }

    #endregion
}
