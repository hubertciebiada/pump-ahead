using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Tests.Common.Builders;
using PumpAhead.Tests.Common.Fixtures;

namespace PumpAhead.Adapters.Out.Tests.Persistence;

public class HeatPumpSnapshotEntityMappingTests : IntegrationTestBase
{
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
    private const int SnapshotCount = 5;

    private static readonly DateTimeOffset BaseTestTime = new(2024, 1, 15, 12, 0, 0, TimeSpan.Zero);

    #region Save and Read preserves all values

    [Fact]
    public async Task SaveAndRead_GivenValidSnapshotEntity_WhenSavedAndRetrieved_ThenAllValuesArePreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var timestamp = DateTimeOffset.UtcNow;
        var entity = new HeatPumpSnapshotEntity
        {
            HeatPumpId = heatPumpId,
            Timestamp = timestamp,
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

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Id.Should().Be(savedId);
        retrievedEntity.HeatPumpId.Should().Be(heatPumpId);
        retrievedEntity.Timestamp.Should().Be(timestamp);
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
    public async Task SaveAndRead_GivenSnapshotWithAutoGeneratedId_WhenSaved_ThenIdIsGenerated()
    {
        // Given
        var entity = CreateDefaultSnapshotEntity(Guid.NewGuid());

        // When
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
        }

        // Then
        entity.Id.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task SaveAndRead_GivenSnapshotWithDefrostActive_WhenSavedAndRetrieved_ThenDefrostStateIsPreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.Defrost_IsActive = true;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Defrost_IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task SaveAndRead_GivenSnapshotWithHeatPumpOff_WhenSavedAndRetrieved_ThenIsOnStateIsPreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.IsOn = false;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.IsOn.Should().BeFalse();
    }

    #endregion

    #region Power data values preserved

    [Fact]
    public async Task SaveAndRead_GivenSnapshotPowerDataWithAllValues_WhenSavedAndRetrieved_ThenAllPowerValuesArePreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.Power_HeatProduction = 5000.00m;
        entity.Power_HeatConsumption = 1500.00m;
        entity.Power_CoolProduction = 3000.00m;
        entity.Power_CoolConsumption = 900.00m;
        entity.Power_DhwProduction = 2500.00m;
        entity.Power_DhwConsumption = 750.00m;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
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
    public async Task SaveAndRead_GivenSnapshotPowerDataWithMaxPrecision_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.Power_HeatProduction = 99999.99m;
        entity.Power_HeatConsumption = 99999.99m;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Power_HeatProduction.Should().Be(MaxPowerPrecision);
        retrievedEntity.Power_HeatConsumption.Should().Be(MaxPowerPrecision);
    }

    #endregion

    #region Operations data values preserved

    [Fact]
    public async Task SaveAndRead_GivenSnapshotOperationsDataWithHighValues_WhenSavedAndRetrieved_ThenValuesArePreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.Operations_CompressorHours = MaxCompressorHours;
        entity.Operations_CompressorStarts = int.MaxValue;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.Operations_CompressorHours.Should().Be(MaxCompressorHours);
        retrievedEntity.Operations_CompressorStarts.Should().Be(int.MaxValue);
    }

    #endregion

    #region Temperature precision

    [Fact]
    public async Task SaveAndRead_GivenSnapshotTemperaturesWithTwoDecimalPlaces_WhenSavedAndRetrieved_ThenPrecisionIsPreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.OutsideTemperature = -15.55m;
        entity.CH_InletTemperature = 32.12m;
        entity.CH_OutletTemperature = 35.67m;
        entity.CH_TargetTemperature = 40.89m;
        entity.DHW_ActualTemperature = 48.23m;
        entity.DHW_TargetTemperature = 50.45m;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
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

    #endregion

    #region Multiple snapshots for same HeatPump

    [Fact]
    public async Task SaveAndRead_GivenMultipleSnapshotsForSameHeatPump_WhenSavedAndRetrieved_ThenAllSnapshotsArePreserved()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var baseTimestamp = DateTimeOffset.UtcNow.AddHours(-2);

        var snapshots = new List<HeatPumpSnapshotEntity>();
        for (int i = 0; i < SnapshotCount; i++)
        {
            var snapshot = CreateDefaultSnapshotEntity(heatPumpId);
            snapshot.Timestamp = baseTimestamp.AddMinutes(i * 15);
            snapshot.OutsideTemperature = DefaultOutsideTemperature + i;
            snapshot.Power_HeatProduction = 3000.0m + (i * 100);
            snapshots.Add(snapshot);
        }

        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.AddRange(snapshots);
            await context.SaveChangesAsync();
        }

        // When
        List<HeatPumpSnapshotEntity> retrievedSnapshots;
        await using (var context = CreateContext())
        {
            retrievedSnapshots = await context.HeatPumpSnapshots
                .Where(s => s.HeatPumpId == heatPumpId)
                .OrderBy(s => s.Timestamp)
                .ToListAsync();
        }

        // Then
        retrievedSnapshots.Should().HaveCount(SnapshotCount);
        for (int i = 0; i < SnapshotCount; i++)
        {
            retrievedSnapshots[i].OutsideTemperature.Should().Be(DefaultOutsideTemperature + i);
            retrievedSnapshots[i].Power_HeatProduction.Should().Be(3000.0m + (i * 100));
        }
    }

    [Fact]
    public async Task SaveAndRead_GivenSnapshotsForDifferentHeatPumps_WhenRetrievedByHeatPumpId_ThenOnlyMatchingSnapshotsAreReturned()
    {
        // Given
        var heatPumpId1 = Guid.NewGuid();
        var heatPumpId2 = Guid.NewGuid();

        var snapshot1 = CreateDefaultSnapshotEntity(heatPumpId1);
        snapshot1.OutsideTemperature = 10.0m;

        var snapshot2 = CreateDefaultSnapshotEntity(heatPumpId1);
        snapshot2.OutsideTemperature = 11.0m;

        var snapshot3 = CreateDefaultSnapshotEntity(heatPumpId2);
        snapshot3.OutsideTemperature = 20.0m;

        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.AddRange(snapshot1, snapshot2, snapshot3);
            await context.SaveChangesAsync();
        }

        // When
        List<HeatPumpSnapshotEntity> retrievedSnapshots;
        await using (var context = CreateContext())
        {
            retrievedSnapshots = await context.HeatPumpSnapshots
                .Where(s => s.HeatPumpId == heatPumpId1)
                .ToListAsync();
        }

        // Then
        retrievedSnapshots.Should().HaveCount(2);
        retrievedSnapshots.Should().AllSatisfy(s => s.HeatPumpId.Should().Be(heatPumpId1));
    }

    #endregion

    #region Timestamp queries

    [Fact]
    public async Task Query_GivenSnapshotsInTimeRange_WhenQueriedByTimestamp_ThenCorrectSnapshotsAreReturned()
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var baseTime = BaseTestTime;

        var snapshots = new[]
        {
            CreateSnapshotWithTimestamp(heatPumpId, baseTime.AddHours(-2)),
            CreateSnapshotWithTimestamp(heatPumpId, baseTime.AddHours(-1)),
            CreateSnapshotWithTimestamp(heatPumpId, baseTime),
            CreateSnapshotWithTimestamp(heatPumpId, baseTime.AddHours(1)),
            CreateSnapshotWithTimestamp(heatPumpId, baseTime.AddHours(2))
        };

        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.AddRange(snapshots);
            await context.SaveChangesAsync();
        }

        // When - Query for snapshots in the last hour (baseTime - 1 hour to baseTime)
        var from = baseTime.AddHours(-1);
        var to = baseTime;

        List<HeatPumpSnapshotEntity> retrievedSnapshots;
        await using (var context = CreateContext())
        {
            retrievedSnapshots = await context.HeatPumpSnapshots
                .Where(s => s.HeatPumpId == heatPumpId && s.Timestamp >= from && s.Timestamp <= to)
                .OrderBy(s => s.Timestamp)
                .ToListAsync();
        }

        // Then
        retrievedSnapshots.Should().HaveCount(2);
        retrievedSnapshots[0].Timestamp.Should().Be(baseTime.AddHours(-1));
        retrievedSnapshots[1].Timestamp.Should().Be(baseTime);
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
    public async Task SaveAndRead_GivenSnapshotWithDifferentOperatingModes_WhenSavedAndRetrieved_ThenModeIsPreserved(int operatingMode)
    {
        // Given
        var heatPumpId = Guid.NewGuid();
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.OperatingMode = operatingMode;

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.OperatingMode.Should().Be(operatingMode);
    }

    #endregion

    #region Entity to domain mapping

    [Fact]
    public void EntityToDomain_GivenValidSnapshotEntity_WhenMapped_ThenDomainObjectHasCorrectValues()
    {
        // Given
        var entity = new HeatPumpSnapshotEntity
        {
            Id = 1,
            HeatPumpId = Guid.NewGuid(),
            Timestamp = DateTimeOffset.UtcNow,
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

        operations.CompressorHours.Should().Be(1500.00m);
        operations.CompressorStarts.Should().Be(250);

        defrost.IsActive.Should().BeFalse();
        errorCode.Code.Should().Be("H00");
    }

    #endregion

    #region Domain to entity mapping

    [Fact]
    public void DomainToEntity_GivenValidDomainSnapshot_WhenMapped_ThenEntityHasCorrectValues()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var snapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
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
        var entity = new HeatPumpSnapshotEntity
        {
            HeatPumpId = snapshot.HeatPumpId.Value,
            Timestamp = snapshot.Timestamp,
            IsOn = snapshot.IsOn,
            OperatingMode = (int)snapshot.OperatingMode,
            PumpFlow = snapshot.PumpFlow.LitersPerMinute,
            OutsideTemperature = snapshot.OutsideTemperature.Celsius,
            CH_InletTemperature = snapshot.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = snapshot.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = snapshot.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = snapshot.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = snapshot.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = snapshot.CompressorFrequency.Hertz,
            Power_HeatProduction = snapshot.Power.HeatProduction.Watts,
            Power_HeatConsumption = snapshot.Power.HeatConsumption.Watts,
            Power_CoolProduction = snapshot.Power.CoolProduction.Watts,
            Power_CoolConsumption = snapshot.Power.CoolConsumption.Watts,
            Power_DhwProduction = snapshot.Power.DhwProduction.Watts,
            Power_DhwConsumption = snapshot.Power.DhwConsumption.Watts,
            Operations_CompressorHours = snapshot.Operations.CompressorHours,
            Operations_CompressorStarts = snapshot.Operations.CompressorStarts,
            Defrost_IsActive = snapshot.Defrost.IsActive,
            ErrorCode = snapshot.ErrorCode.Code
        };

        // Then
        entity.HeatPumpId.Should().Be(heatPumpId.Value);
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
    public async Task Roundtrip_GivenDomainSnapshot_WhenSavedAndRetrieved_ThenDomainSnapshotIsEquivalent()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var originalSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
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
        var entity = new HeatPumpSnapshotEntity
        {
            HeatPumpId = originalSnapshot.HeatPumpId.Value,
            Timestamp = originalSnapshot.Timestamp,
            IsOn = originalSnapshot.IsOn,
            OperatingMode = (int)originalSnapshot.OperatingMode,
            PumpFlow = originalSnapshot.PumpFlow.LitersPerMinute,
            OutsideTemperature = originalSnapshot.OutsideTemperature.Celsius,
            CH_InletTemperature = originalSnapshot.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = originalSnapshot.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = originalSnapshot.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = originalSnapshot.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = originalSnapshot.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = originalSnapshot.CompressorFrequency.Hertz,
            Power_HeatProduction = originalSnapshot.Power.HeatProduction.Watts,
            Power_HeatConsumption = originalSnapshot.Power.HeatConsumption.Watts,
            Power_CoolProduction = originalSnapshot.Power.CoolProduction.Watts,
            Power_CoolConsumption = originalSnapshot.Power.CoolConsumption.Watts,
            Power_DhwProduction = originalSnapshot.Power.DhwProduction.Watts,
            Power_DhwConsumption = originalSnapshot.Power.DhwConsumption.Watts,
            Operations_CompressorHours = originalSnapshot.Operations.CompressorHours,
            Operations_CompressorStarts = originalSnapshot.Operations.CompressorStarts,
            Defrost_IsActive = originalSnapshot.Defrost.IsActive,
            ErrorCode = originalSnapshot.ErrorCode.Code
        };

        // Save to database
        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When - Retrieve and verify
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Map retrieved entity back to domain value objects
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
        retrievedEntity.HeatPumpId.Should().Be(originalSnapshot.HeatPumpId.Value);
        retrievedEntity.IsOn.Should().Be(originalSnapshot.IsOn);
        retrievedEntity.OperatingMode.Should().Be((int)originalSnapshot.OperatingMode);
        retrievedEntity.PumpFlow.Should().Be(originalSnapshot.PumpFlow.LitersPerMinute);
        retrievedEntity.OutsideTemperature.Should().Be(originalSnapshot.OutsideTemperature.Celsius);

        centralHeating.InletTemperature.Celsius.Should().Be(originalSnapshot.CentralHeating.InletTemperature.Celsius);
        centralHeating.OutletTemperature.Celsius.Should().Be(originalSnapshot.CentralHeating.OutletTemperature.Celsius);
        centralHeating.TargetTemperature.Celsius.Should().Be(originalSnapshot.CentralHeating.TargetTemperature.Celsius);

        domesticHotWater.ActualTemperature.Celsius.Should().Be(originalSnapshot.DomesticHotWater.ActualTemperature.Celsius);
        domesticHotWater.TargetTemperature.Celsius.Should().Be(originalSnapshot.DomesticHotWater.TargetTemperature.Celsius);

        retrievedEntity.Compressor_Frequency.Should().Be(originalSnapshot.CompressorFrequency.Hertz);

        power.HeatProduction.Watts.Should().Be(originalSnapshot.Power.HeatProduction.Watts);
        power.HeatConsumption.Watts.Should().Be(originalSnapshot.Power.HeatConsumption.Watts);
        power.CoolProduction.Watts.Should().Be(originalSnapshot.Power.CoolProduction.Watts);
        power.CoolConsumption.Watts.Should().Be(originalSnapshot.Power.CoolConsumption.Watts);
        power.DhwProduction.Watts.Should().Be(originalSnapshot.Power.DhwProduction.Watts);
        power.DhwConsumption.Watts.Should().Be(originalSnapshot.Power.DhwConsumption.Watts);

        operations.CompressorHours.Should().Be(originalSnapshot.Operations.CompressorHours);
        operations.CompressorStarts.Should().Be(originalSnapshot.Operations.CompressorStarts);

        retrievedEntity.Defrost_IsActive.Should().Be(originalSnapshot.Defrost.IsActive);
        retrievedEntity.ErrorCode.Should().Be(originalSnapshot.ErrorCode.Code);
    }

    #endregion

    #region Using HeatPumpSnapshotBuilder

    [Fact]
    public async Task SaveAndRead_GivenSnapshotCreatedFromBuilder_WhenSavedAndRetrieved_ThenAllValuesArePreserved()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var timestamp = DateTimeOffset.UtcNow;

        var domainSnapshot = HeatPumpSnapshotBuilder.Valid()
            .WithHeatPumpId(heatPumpId)
            .WithTimestamp(timestamp)
            .WithIsOn(true)
            .WithOperatingMode(OperatingMode.CoolDhw)
            .WithPumpFlow(20.00m)
            .WithOutsideTemperature(25.00m)
            .WithCentralHeating(18.00m, 15.00m, 16.00m)
            .WithDomesticHotWater(55.00m, 58.00m)
            .WithCompressorFrequency(70.00m)
            .WithHeatingPower(0.00m, 0.00m)
            .WithOperations(5000.00m, 1000)
            .WithDefrost(DefrostData.Inactive)
            .WithErrorCode(ErrorCode.None)
            .Build();

        var entity = new HeatPumpSnapshotEntity
        {
            HeatPumpId = domainSnapshot.HeatPumpId.Value,
            Timestamp = domainSnapshot.Timestamp,
            IsOn = domainSnapshot.IsOn,
            OperatingMode = (int)domainSnapshot.OperatingMode,
            PumpFlow = domainSnapshot.PumpFlow.LitersPerMinute,
            OutsideTemperature = domainSnapshot.OutsideTemperature.Celsius,
            CH_InletTemperature = domainSnapshot.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = domainSnapshot.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = domainSnapshot.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = domainSnapshot.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = domainSnapshot.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = domainSnapshot.CompressorFrequency.Hertz,
            Power_HeatProduction = domainSnapshot.Power.HeatProduction.Watts,
            Power_HeatConsumption = domainSnapshot.Power.HeatConsumption.Watts,
            Power_CoolProduction = domainSnapshot.Power.CoolProduction.Watts,
            Power_CoolConsumption = domainSnapshot.Power.CoolConsumption.Watts,
            Power_DhwProduction = domainSnapshot.Power.DhwProduction.Watts,
            Power_DhwConsumption = domainSnapshot.Power.DhwConsumption.Watts,
            Operations_CompressorHours = domainSnapshot.Operations.CompressorHours,
            Operations_CompressorStarts = domainSnapshot.Operations.CompressorStarts,
            Defrost_IsActive = domainSnapshot.Defrost.IsActive,
            ErrorCode = domainSnapshot.ErrorCode.Code
        };

        long savedId;
        await using (var context = CreateContext())
        {
            context.HeatPumpSnapshots.Add(entity);
            await context.SaveChangesAsync();
            savedId = entity.Id;
        }

        // When
        HeatPumpSnapshotEntity? retrievedEntity;
        await using (var context = CreateContext())
        {
            retrievedEntity = await context.HeatPumpSnapshots.FirstOrDefaultAsync(s => s.Id == savedId);
        }

        // Then
        retrievedEntity.Should().NotBeNull();
        retrievedEntity!.HeatPumpId.Should().Be(heatPumpId.Value);
        retrievedEntity.OperatingMode.Should().Be((int)OperatingMode.CoolDhw);
        retrievedEntity.PumpFlow.Should().Be(20.00m);
        retrievedEntity.OutsideTemperature.Should().Be(25.00m);
        retrievedEntity.CH_InletTemperature.Should().Be(18.00m);
        retrievedEntity.CH_OutletTemperature.Should().Be(15.00m);
        retrievedEntity.CH_TargetTemperature.Should().Be(16.00m);
        retrievedEntity.DHW_ActualTemperature.Should().Be(55.00m);
        retrievedEntity.DHW_TargetTemperature.Should().Be(58.00m);
        retrievedEntity.Compressor_Frequency.Should().Be(70.00m);
        retrievedEntity.Operations_CompressorHours.Should().Be(5000.00m);
        retrievedEntity.Operations_CompressorStarts.Should().Be(1000);
    }

    #endregion

    #region Helper methods

    private static HeatPumpSnapshotEntity CreateDefaultSnapshotEntity(Guid heatPumpId) => new()
    {
        HeatPumpId = heatPumpId,
        Timestamp = DateTimeOffset.UtcNow,
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

    private static HeatPumpSnapshotEntity CreateSnapshotWithTimestamp(Guid heatPumpId, DateTimeOffset timestamp)
    {
        var entity = CreateDefaultSnapshotEntity(heatPumpId);
        entity.Timestamp = timestamp;
        return entity;
    }

    #endregion
}
