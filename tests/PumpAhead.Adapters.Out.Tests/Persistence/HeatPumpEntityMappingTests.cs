using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Tests.Common.Builders;
using PumpAhead.Tests.Common.Fixtures;

namespace PumpAhead.Adapters.Out.Tests.Persistence;

public class HeatPumpEntityMappingTests : IntegrationTestBase
{
    private const string DefaultModel = "Default Model";
    private const string PanasonicModel = "Panasonic WH-MDC09J3E5";
    private const string TestModel = "Test Model";
    private const string DefaultErrorCode = "H00";
    private const int DefaultOperatingMode = 4;
    private const int DefaultCompressorStarts = 250;
    private const decimal DefaultPumpFlow = 12.50m;
    private const decimal DefaultOutsideTemperature = 5.00m;
    private const decimal DefaultChInletTemperature = 32.00m;
    private const decimal DefaultChOutletTemperature = 35.00m;
    private const decimal DefaultChTargetTemperature = 40.00m;
    private const decimal DefaultDhwActualTemperature = 48.00m;
    private const decimal DefaultDhwTargetTemperature = 50.00m;
    private const decimal DefaultCompressorFrequency = 45.00m;
    private const decimal DefaultHeatPowerProduction = 3500.00m;
    private const decimal DefaultHeatPowerConsumption = 1000.00m;
    private const decimal DefaultCoolPowerProduction = 0.00m;
    private const decimal DefaultCoolPowerConsumption = 0.00m;
    private const decimal DefaultDhwPowerProduction = 2200.00m;
    private const decimal DefaultDhwPowerConsumption = 600.00m;
    private const decimal DefaultCompressorHours = 1500.00m;
    private const decimal MaxPowerPrecision = 99999.99m;
    private const decimal MaxCompressorHours = 999999.99m;
    private const decimal MaxPumpFlow = 9999.99m;
    private const decimal MaxTemperature = 99.99m;

    #region Save and Read preserves all values

    [Fact]
    public async Task SaveAndRead_GivenValidHeatPumpEntity_WhenSavedAndRetrieved_ThenAllValuesArePreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var lastSyncTime = DateTimeOffset.UtcNow;
        var entity = new HeatPumpEntity
        {
            Id = id,
            Model = "Panasonic WH-MDC09J3E5",
            LastSyncTime = lastSyncTime,
            IsOn = true,
            OperatingMode = 4,
            PumpFlow = 12.55m,
            OutsideTemperature = 5.75m,
            CH_InletTemperature = 32.25m,
            CH_OutletTemperature = 35.50m,
            CH_TargetTemperature = 40.00m,
            DHW_ActualTemperature = 48.50m,
            DHW_TargetTemperature = 50.00m,
            Compressor_Frequency = 45.25m,
            Power_HeatProduction = 3500.50m,
            Power_HeatConsumption = 1000.25m,
            Power_CoolProduction = 0.00m,
            Power_CoolConsumption = 0.00m,
            Power_DhwProduction = 2200.75m,
            Power_DhwConsumption = 600.00m,
            Operations_CompressorHours = 1500.50m,
            Operations_CompressorStarts = 250,
            Defrost_IsActive = false,
            ErrorCode = "H00"
        };

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Id.Should().Be(id);
        retrievedEntity.Model.Should().Be(PanasonicModel);
        retrievedEntity.LastSyncTime.Should().Be(lastSyncTime);
        retrievedEntity.IsOn.Should().BeTrue();
        retrievedEntity.OperatingMode.Should().Be(DefaultOperatingMode);
        retrievedEntity.PumpFlow.Should().Be(12.55m);
        retrievedEntity.OutsideTemperature.Should().Be(5.75m);
        retrievedEntity.CH_InletTemperature.Should().Be(32.25m);
        retrievedEntity.CH_OutletTemperature.Should().Be(35.50m);
        retrievedEntity.CH_TargetTemperature.Should().Be(DefaultChTargetTemperature);
        retrievedEntity.DHW_ActualTemperature.Should().Be(48.50m);
        retrievedEntity.DHW_TargetTemperature.Should().Be(DefaultDhwTargetTemperature);
        retrievedEntity.Compressor_Frequency.Should().Be(45.25m);
        retrievedEntity.Power_HeatProduction.Should().Be(3500.50m);
        retrievedEntity.Power_HeatConsumption.Should().Be(1000.25m);
        retrievedEntity.Power_CoolProduction.Should().Be(DefaultCoolPowerProduction);
        retrievedEntity.Power_CoolConsumption.Should().Be(DefaultCoolPowerConsumption);
        retrievedEntity.Power_DhwProduction.Should().Be(2200.75m);
        retrievedEntity.Power_DhwConsumption.Should().Be(DefaultDhwPowerConsumption);
        retrievedEntity.Operations_CompressorHours.Should().Be(1500.50m);
        retrievedEntity.Operations_CompressorStarts.Should().Be(DefaultCompressorStarts);
        retrievedEntity.Defrost_IsActive.Should().BeFalse();
        retrievedEntity.ErrorCode.Should().Be(DefaultErrorCode);
    }

    [Fact]
    public async Task SaveAndRead_GivenHeatPumpWithDefrostActive_WhenSavedAndRetrieved_ThenDefrostStateIsPreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.Defrost_IsActive = true;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Defrost_IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task SaveAndRead_GivenHeatPumpTurnedOff_WhenSavedAndRetrieved_ThenIsOnStateIsPreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.IsOn = false;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.IsOn.Should().BeFalse();
    }

    [Fact]
    public async Task SaveAndRead_GivenHeatPumpWithErrorCode_WhenSavedAndRetrieved_ThenErrorCodeIsPreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.ErrorCode = "H15";

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.ErrorCode.Should().Be("H15");
    }

    #endregion

    #region Power data values preserved

    [Fact]
    public async Task SaveAndRead_GivenPowerDataWithAllValues_WhenSavedAndRetrieved_ThenAllPowerValuesArePreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.Power_HeatProduction = 5000.00m;
        entity.Power_HeatConsumption = 1500.00m;
        entity.Power_CoolProduction = 3000.00m;
        entity.Power_CoolConsumption = 900.00m;
        entity.Power_DhwProduction = 2500.00m;
        entity.Power_DhwConsumption = 750.00m;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Power_HeatProduction.Should().Be(5000.00m);
        retrievedEntity.Power_HeatConsumption.Should().Be(1500.00m);
        retrievedEntity.Power_CoolProduction.Should().Be(3000.00m);
        retrievedEntity.Power_CoolConsumption.Should().Be(900.00m);
        retrievedEntity.Power_DhwProduction.Should().Be(2500.00m);
        retrievedEntity.Power_DhwConsumption.Should().Be(750.00m);
    }

    [Fact]
    public async Task SaveAndRead_GivenPowerDataWithMaxPrecision_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.Power_HeatProduction = 99999.99m;
        entity.Power_HeatConsumption = 99999.99m;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Power_HeatProduction.Should().Be(MaxPowerPrecision);
        retrievedEntity.Power_HeatConsumption.Should().Be(MaxPowerPrecision);
    }

    #endregion

    #region Operations data values preserved

    [Fact]
    public async Task SaveAndRead_GivenOperationsDataWithHighValues_WhenSavedAndRetrieved_ThenValuesArePreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.Operations_CompressorHours = MaxCompressorHours;
        entity.Operations_CompressorStarts = int.MaxValue;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Operations_CompressorHours.Should().Be(MaxCompressorHours);
        retrievedEntity.Operations_CompressorStarts.Should().Be(int.MaxValue);
    }

    #endregion

    #region Temperature precision

    [Fact]
    public async Task SaveAndRead_GivenTemperaturesWithTwoDecimalPlaces_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.OutsideTemperature = -15.55m;
        entity.CH_InletTemperature = 32.12m;
        entity.CH_OutletTemperature = 35.67m;
        entity.CH_TargetTemperature = 40.89m;
        entity.DHW_ActualTemperature = 48.23m;
        entity.DHW_TargetTemperature = 50.45m;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.OutsideTemperature.Should().Be(-15.55m);
        retrievedEntity.CH_InletTemperature.Should().Be(32.12m);
        retrievedEntity.CH_OutletTemperature.Should().Be(35.67m);
        retrievedEntity.CH_TargetTemperature.Should().Be(40.89m);
        retrievedEntity.DHW_ActualTemperature.Should().Be(48.23m);
        retrievedEntity.DHW_TargetTemperature.Should().Be(50.45m);
    }

    [Fact]
    public async Task SaveAndRead_GivenTemperatureAtMaxRange_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given - Temperature precision is (5,2), so max is 999.99
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.OutsideTemperature = 99.99m;
        entity.CH_InletTemperature = 99.99m;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.OutsideTemperature.Should().Be(MaxTemperature);
        retrievedEntity.CH_InletTemperature.Should().Be(MaxTemperature);
    }

    #endregion

    #region PumpFlow precision

    [Fact]
    public async Task SaveAndRead_GivenPumpFlowWithTwoDecimalPlaces_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given - PumpFlow precision is (6,2), so max is 9999.99
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.PumpFlow = 123.45m;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.PumpFlow.Should().Be(123.45m);
    }

    [Fact]
    public async Task SaveAndRead_GivenPumpFlowAtMaxRange_WhenSavedAndRetrieved_ThenValueIsPreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.PumpFlow = MaxPumpFlow;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.PumpFlow.Should().Be(MaxPumpFlow);
    }

    #endregion

    #region Compressor frequency precision

    [Fact]
    public async Task SaveAndRead_GivenCompressorFrequencyWithTwoDecimalPlaces_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given - Compressor_Frequency precision is (6,2)
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.Compressor_Frequency = 87.65m;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Compressor_Frequency.Should().Be(87.65m);
    }

    #endregion

    #region Operating mode values

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(5)]
    [InlineData(6)]
    [InlineData(7)]
    [InlineData(8)]
    public async Task SaveAndRead_GivenDifferentOperatingModes_WhenSavedAndRetrieved_ThenModeIsPreserved(int operatingMode)
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);
        entity.OperatingMode = operatingMode;

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.OperatingMode.Should().Be(operatingMode);
    }

    #endregion

    #region Update entity

    [Fact]
    public async Task Update_GivenExistingEntity_WhenUpdated_ThenChangesArePreserved()
    {
        // Given
        var id = Guid.NewGuid();
        var entity = CreateDefaultEntity(id);

        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When
        await using (var context = CreateContext())
        {
            var existingEntity = await context.HeatPumps.FirstAsync(hp => hp.Id == id);
            existingEntity.IsOn = false;
            existingEntity.OutsideTemperature = -10.00m;
            existingEntity.Power_HeatProduction = 0.00m;
            existingEntity.ErrorCode = "H99";
            await context.SaveChangesAsync();
        }

        // Then
        await using (var context = CreateContext())
        {
            var retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == id);
            retrievedEntity.Should().NotBeNull();
            retrievedEntity!.IsOn.Should().BeFalse();
            retrievedEntity.OutsideTemperature.Should().Be(-10.00m);
            retrievedEntity.Power_HeatProduction.Should().Be(0.00m);
            retrievedEntity.ErrorCode.Should().Be("H99");
        }
    }

    #endregion

    #region Multiple entities

    [Fact]
    public async Task SaveAndRead_GivenMultipleEntities_WhenSavedAndRetrieved_ThenAllEntitiesArePreserved()
    {
        // Given
        var ids = new[] { Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid() };
        var entities = ids.Select((id, index) =>
        {
            var entity = CreateDefaultEntity(id);
            entity.Model = $"HeatPump-{index}";
            entity.OutsideTemperature = 5.0m + index;
            return entity;
        }).ToList();

        await using (var context = CreateContext())
        {
            context.HeatPumps.AddRange(entities);
            await context.SaveChangesAsync();
        }

        // When
        List<HeatPumpEntity> retrievedEntities;
        await using (var context = CreateContext())
        {
            retrievedEntities = await context.HeatPumps
                .Where(hp => ids.Contains(hp.Id))
                .OrderBy(hp => hp.Model)
                .ToListAsync();
        }

        // Then
        retrievedEntities.Should().HaveCount(3);
        retrievedEntities[0].Model.Should().Be("HeatPump-0");
        retrievedEntities[0].OutsideTemperature.Should().Be(5.0m);
        retrievedEntities[1].Model.Should().Be("HeatPump-1");
        retrievedEntities[1].OutsideTemperature.Should().Be(6.0m);
        retrievedEntities[2].Model.Should().Be("HeatPump-2");
        retrievedEntities[2].OutsideTemperature.Should().Be(7.0m);
    }

    #endregion

    #region Entity to domain mapping

    [Fact]
    public void EntityToDomain_GivenValidEntity_WhenMapped_ThenDomainObjectHasCorrectValues()
    {
        // Given
        var entity = new HeatPumpEntity
        {
            Id = Guid.NewGuid(),
            Model = "Panasonic WH-MDC09J3E5",
            LastSyncTime = DateTimeOffset.UtcNow,
            IsOn = true,
            OperatingMode = (int)OperatingMode.HeatDhw,
            PumpFlow = 12.50m,
            OutsideTemperature = 5.00m,
            CH_InletTemperature = 32.00m,
            CH_OutletTemperature = 35.00m,
            CH_TargetTemperature = 40.00m,
            DHW_ActualTemperature = 48.00m,
            DHW_TargetTemperature = 50.00m,
            Compressor_Frequency = 45.00m,
            Power_HeatProduction = 3500.00m,
            Power_HeatConsumption = 1000.00m,
            Power_CoolProduction = 0.00m,
            Power_CoolConsumption = 0.00m,
            Power_DhwProduction = 2200.00m,
            Power_DhwConsumption = 600.00m,
            Operations_CompressorHours = 1500.00m,
            Operations_CompressorStarts = 250,
            Defrost_IsActive = false,
            ErrorCode = "H00"
        };

        // When - Manual mapping to domain (simulating what the repository does)
        var centralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(entity.CH_InletTemperature),
            WaterTemperature.FromCelsius(entity.CH_OutletTemperature),
            WaterTemperature.FromCelsius(entity.CH_TargetTemperature));

        var domesticHotWater = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(entity.DHW_ActualTemperature),
            DhwTemperature.FromCelsius(entity.DHW_TargetTemperature));

        var power = new PowerData(
            Power.FromWatts(entity.Power_HeatProduction),
            Power.FromWatts(entity.Power_HeatConsumption),
            Power.FromWatts(entity.Power_CoolProduction),
            Power.FromWatts(entity.Power_CoolConsumption),
            Power.FromWatts(entity.Power_DhwProduction),
            Power.FromWatts(entity.Power_DhwConsumption));

        var operations = new OperationsData(
            entity.Operations_CompressorHours,
            entity.Operations_CompressorStarts);

        var defrost = new DefrostData(entity.Defrost_IsActive);
        var errorCode = ErrorCode.From(entity.ErrorCode);

        // Then
        centralHeating.InletTemperature.Celsius.Should().Be(32.00m);
        centralHeating.OutletTemperature.Celsius.Should().Be(35.00m);
        centralHeating.TargetTemperature.Celsius.Should().Be(40.00m);

        domesticHotWater.ActualTemperature.Celsius.Should().Be(48.00m);
        domesticHotWater.TargetTemperature.Celsius.Should().Be(50.00m);

        power.HeatProduction.Watts.Should().Be(3500.00m);
        power.HeatConsumption.Watts.Should().Be(1000.00m);
        power.CoolProduction.Watts.Should().Be(0.00m);
        power.CoolConsumption.Watts.Should().Be(0.00m);
        power.DhwProduction.Watts.Should().Be(2200.00m);
        power.DhwConsumption.Watts.Should().Be(600.00m);

        operations.CompressorHours.Should().Be(1500.00m);
        operations.CompressorStarts.Should().Be(250);

        defrost.IsActive.Should().BeFalse();
        errorCode.Code.Should().Be("H00");
    }

    #endregion

    #region Domain to entity mapping

    [Fact]
    public void DomainToEntity_GivenValidDomainObject_WhenMapped_ThenEntityHasCorrectValues()
    {
        // Given
        var heatPump = HeatPumpBuilder.Valid()
            .WithId(Guid.NewGuid())
            .WithModel("Test Model")
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.HeatDhw)
            .WithPumpFlow(15.50m)
            .WithOutsideTemperature(8.00m)
            .WithCentralHeating(30.00m, 33.00m, 38.00m)
            .WithDomesticHotWater(45.00m, 48.00m)
            .WithCompressorFrequency(50.00m)
            .WithOperations(2000.00m, 500)
            .Build();

        // When - Manual mapping to entity (simulating what the repository does)
        var entity = new HeatPumpEntity
        {
            Id = heatPump.Id.Value,
            Model = heatPump.Model,
            LastSyncTime = heatPump.LastSyncTime,
            IsOn = heatPump.IsOn,
            OperatingMode = (int)heatPump.OperatingMode,
            PumpFlow = heatPump.PumpFlow.LitersPerMinute,
            OutsideTemperature = heatPump.OutsideTemperature.Celsius,
            CH_InletTemperature = heatPump.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = heatPump.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = heatPump.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = heatPump.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = heatPump.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = heatPump.CompressorFrequency.Hertz,
            Power_HeatProduction = heatPump.Power.HeatProduction.Watts,
            Power_HeatConsumption = heatPump.Power.HeatConsumption.Watts,
            Power_CoolProduction = heatPump.Power.CoolProduction.Watts,
            Power_CoolConsumption = heatPump.Power.CoolConsumption.Watts,
            Power_DhwProduction = heatPump.Power.DhwProduction.Watts,
            Power_DhwConsumption = heatPump.Power.DhwConsumption.Watts,
            Operations_CompressorHours = heatPump.Operations.CompressorHours,
            Operations_CompressorStarts = heatPump.Operations.CompressorStarts,
            Defrost_IsActive = heatPump.Defrost.IsActive,
            ErrorCode = heatPump.ErrorCode.Code
        };

        // Then
        entity.Id.Should().Be(heatPump.Id.Value);
        entity.Model.Should().Be("Test Model");
        entity.IsOn.Should().BeTrue();
        entity.OperatingMode.Should().Be((int)OperatingMode.HeatDhw);
        entity.PumpFlow.Should().Be(15.50m);
        entity.OutsideTemperature.Should().Be(8.00m);
        entity.CH_InletTemperature.Should().Be(30.00m);
        entity.CH_OutletTemperature.Should().Be(33.00m);
        entity.CH_TargetTemperature.Should().Be(38.00m);
        entity.DHW_ActualTemperature.Should().Be(45.00m);
        entity.DHW_TargetTemperature.Should().Be(48.00m);
        entity.Compressor_Frequency.Should().Be(50.00m);
        entity.Operations_CompressorHours.Should().Be(2000.00m);
        entity.Operations_CompressorStarts.Should().Be(500);
    }

    #endregion

    #region Roundtrip domain -> entity -> domain

    [Fact]
    public async Task Roundtrip_GivenDomainObject_WhenSavedAndRetrieved_ThenDomainObjectIsEquivalent()
    {
        // Given
        var originalDomain = HeatPumpBuilder.Valid()
            .WithId(Guid.NewGuid())
            .WithModel("Roundtrip Test")
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.HeatOnly)
            .WithPumpFlow(18.75m)
            .WithOutsideTemperature(-5.50m)
            .WithCentralHeating(28.00m, 31.50m, 35.00m)
            .WithDomesticHotWater(42.50m, 45.00m)
            .WithCompressorFrequency(65.25m)
            .WithOperations(3500.75m, 750)
            .WithDefrost(DefrostData.Active)
            .WithErrorCode(ErrorCode.None)
            .Build();

        // Map to entity
        var entity = new HeatPumpEntity
        {
            Id = originalDomain.Id.Value,
            Model = originalDomain.Model,
            LastSyncTime = originalDomain.LastSyncTime,
            IsOn = originalDomain.IsOn,
            OperatingMode = (int)originalDomain.OperatingMode,
            PumpFlow = originalDomain.PumpFlow.LitersPerMinute,
            OutsideTemperature = originalDomain.OutsideTemperature.Celsius,
            CH_InletTemperature = originalDomain.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = originalDomain.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = originalDomain.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = originalDomain.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = originalDomain.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = originalDomain.CompressorFrequency.Hertz,
            Power_HeatProduction = originalDomain.Power.HeatProduction.Watts,
            Power_HeatConsumption = originalDomain.Power.HeatConsumption.Watts,
            Power_CoolProduction = originalDomain.Power.CoolProduction.Watts,
            Power_CoolConsumption = originalDomain.Power.CoolConsumption.Watts,
            Power_DhwProduction = originalDomain.Power.DhwProduction.Watts,
            Power_DhwConsumption = originalDomain.Power.DhwConsumption.Watts,
            Operations_CompressorHours = originalDomain.Operations.CompressorHours,
            Operations_CompressorStarts = originalDomain.Operations.CompressorStarts,
            Defrost_IsActive = originalDomain.Defrost.IsActive,
            ErrorCode = originalDomain.ErrorCode.Code
        };

        // Save to database
        await using (var context = CreateContext())
        {
            context.HeatPumps.Add(entity);
            await context.SaveChangesAsync();
        }

        // When - Retrieve and map back to domain
        HeatPumpEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumps.FirstOrDefaultAsync(hp => hp.Id == originalDomain.Id.Value);
        }

        // Map retrieved entity back to domain
        var centralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(retrievedEntity!.CH_InletTemperature),
            WaterTemperature.FromCelsius(retrievedEntity.CH_OutletTemperature),
            WaterTemperature.FromCelsius(retrievedEntity.CH_TargetTemperature));

        var domesticHotWater = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(retrievedEntity.DHW_ActualTemperature),
            DhwTemperature.FromCelsius(retrievedEntity.DHW_TargetTemperature));

        var power = new PowerData(
            Power.FromWatts(retrievedEntity.Power_HeatProduction),
            Power.FromWatts(retrievedEntity.Power_HeatConsumption),
            Power.FromWatts(retrievedEntity.Power_CoolProduction),
            Power.FromWatts(retrievedEntity.Power_CoolConsumption),
            Power.FromWatts(retrievedEntity.Power_DhwProduction),
            Power.FromWatts(retrievedEntity.Power_DhwConsumption));

        var operations = new OperationsData(
            retrievedEntity.Operations_CompressorHours,
            retrievedEntity.Operations_CompressorStarts);

        // Then - Verify all values match
        retrievedEntity.Id.Should().Be(originalDomain.Id.Value);
        retrievedEntity.Model.Should().Be(originalDomain.Model);
        retrievedEntity.IsOn.Should().Be(originalDomain.IsOn);
        retrievedEntity.OperatingMode.Should().Be((int)originalDomain.OperatingMode);
        retrievedEntity.PumpFlow.Should().Be(originalDomain.PumpFlow.LitersPerMinute);
        retrievedEntity.OutsideTemperature.Should().Be(originalDomain.OutsideTemperature.Celsius);

        centralHeating.InletTemperature.Celsius.Should().Be(originalDomain.CentralHeating.InletTemperature.Celsius);
        centralHeating.OutletTemperature.Celsius.Should().Be(originalDomain.CentralHeating.OutletTemperature.Celsius);
        centralHeating.TargetTemperature.Celsius.Should().Be(originalDomain.CentralHeating.TargetTemperature.Celsius);

        domesticHotWater.ActualTemperature.Celsius.Should().Be(originalDomain.DomesticHotWater.ActualTemperature.Celsius);
        domesticHotWater.TargetTemperature.Celsius.Should().Be(originalDomain.DomesticHotWater.TargetTemperature.Celsius);

        retrievedEntity.Compressor_Frequency.Should().Be(originalDomain.CompressorFrequency.Hertz);

        power.HeatProduction.Watts.Should().Be(originalDomain.Power.HeatProduction.Watts);
        power.HeatConsumption.Watts.Should().Be(originalDomain.Power.HeatConsumption.Watts);
        power.CoolProduction.Watts.Should().Be(originalDomain.Power.CoolProduction.Watts);
        power.CoolConsumption.Watts.Should().Be(originalDomain.Power.CoolConsumption.Watts);
        power.DhwProduction.Watts.Should().Be(originalDomain.Power.DhwProduction.Watts);
        power.DhwConsumption.Watts.Should().Be(originalDomain.Power.DhwConsumption.Watts);

        operations.CompressorHours.Should().Be(originalDomain.Operations.CompressorHours);
        operations.CompressorStarts.Should().Be(originalDomain.Operations.CompressorStarts);

        retrievedEntity.Defrost_IsActive.Should().Be(originalDomain.Defrost.IsActive);
        retrievedEntity.ErrorCode.Should().Be(originalDomain.ErrorCode.Code);
    }

    #endregion

    #region Helper methods

    private static HeatPumpEntity CreateDefaultEntity(Guid id) => new()
    {
        Id = id,
        Model = DefaultModel,
        LastSyncTime = DateTimeOffset.UtcNow,
        IsOn = true,
        OperatingMode = DefaultOperatingMode,
        PumpFlow = DefaultPumpFlow,
        OutsideTemperature = DefaultOutsideTemperature,
        CH_InletTemperature = DefaultChInletTemperature,
        CH_OutletTemperature = DefaultChOutletTemperature,
        CH_TargetTemperature = DefaultChTargetTemperature,
        DHW_ActualTemperature = DefaultDhwActualTemperature,
        DHW_TargetTemperature = DefaultDhwTargetTemperature,
        Compressor_Frequency = DefaultCompressorFrequency,
        Power_HeatProduction = DefaultHeatPowerProduction,
        Power_HeatConsumption = DefaultHeatPowerConsumption,
        Power_CoolProduction = DefaultCoolPowerProduction,
        Power_CoolConsumption = DefaultCoolPowerConsumption,
        Power_DhwProduction = DefaultDhwPowerProduction,
        Power_DhwConsumption = DefaultDhwPowerConsumption,
        Operations_CompressorHours = DefaultCompressorHours,
        Operations_CompressorStarts = DefaultCompressorStarts,
        Defrost_IsActive = false,
        ErrorCode = DefaultErrorCode
    };

    #endregion
}
