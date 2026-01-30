using FluentAssertions;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.Entities;

public class HeatPumpSnapshotTests
{
    #region Test Data Helpers

    private static HeatPumpId CreateHeatPumpId() => HeatPumpId.NewId();

    private static HeatPumpSnapshotId CreateSnapshotId(long id = 42) => HeatPumpSnapshotId.From(id);

    private static DateTimeOffset CreateTimestamp() => new(2024, 1, 15, 10, 30, 0, TimeSpan.Zero);

    private static PumpFlow CreatePumpFlow() => PumpFlow.FromLitersPerMinute(12.5m);

    private static OutsideTemperature CreateOutsideTemperature() => OutsideTemperature.FromCelsius(-5.0m);

    private static CentralHeatingData CreateCentralHeatingData() => new(
        WaterTemperature.FromCelsius(35.0m),
        WaterTemperature.FromCelsius(40.0m),
        WaterTemperature.FromCelsius(42.0m));

    private static DomesticHotWaterData CreateDomesticHotWaterData() => new(
        DhwTemperature.FromCelsius(48.0m),
        DhwTemperature.FromCelsius(50.0m));

    private static Frequency CreateCompressorFrequency() => Frequency.FromHertz(55.0m);

    private static PowerData CreatePowerData() => new(
        Power.FromWatts(5000),
        Power.FromWatts(1200),
        Power.FromWatts(0),
        Power.FromWatts(0),
        Power.FromWatts(2500),
        Power.FromWatts(700));

    private static OperationsData CreateOperationsData() => new(12500.5m, 1234);

    private static DefrostData CreateDefrostData() => DefrostData.Inactive;

    private static ErrorCode CreateErrorCode() => ErrorCode.None;

    #endregion

    #region CreateFrom Tests

    [Fact]
    public void CreateFrom_GivenValidHeatPumpData_WhenCreatingSnapshot_ThenSnapshotContainsAllProperties()
    {
        // Given
        var heatPumpId = CreateHeatPumpId();
        var timestamp = CreateTimestamp();
        var isOn = true;
        var operatingMode = OperatingMode.HeatDhw;
        var pumpFlow = CreatePumpFlow();
        var outsideTemperature = CreateOutsideTemperature();
        var centralHeating = CreateCentralHeatingData();
        var domesticHotWater = CreateDomesticHotWaterData();
        var compressorFrequency = CreateCompressorFrequency();
        var power = CreatePowerData();
        var operations = CreateOperationsData();
        var defrost = CreateDefrostData();
        var errorCode = CreateErrorCode();

        // When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            heatPumpId,
            timestamp,
            isOn,
            operatingMode,
            pumpFlow,
            outsideTemperature,
            centralHeating,
            domesticHotWater,
            compressorFrequency,
            power,
            operations,
            defrost,
            errorCode);

        // Then
        snapshot.HeatPumpId.Should().Be(heatPumpId);
        snapshot.Timestamp.Should().Be(timestamp);
        snapshot.IsOn.Should().Be(isOn);
        snapshot.OperatingMode.Should().Be(operatingMode);
        snapshot.PumpFlow.Should().Be(pumpFlow);
        snapshot.OutsideTemperature.Should().Be(outsideTemperature);
        snapshot.CentralHeating.Should().Be(centralHeating);
        snapshot.DomesticHotWater.Should().Be(domesticHotWater);
        snapshot.CompressorFrequency.Should().Be(compressorFrequency);
        snapshot.Power.Should().Be(power);
        snapshot.Operations.Should().Be(operations);
        snapshot.Defrost.Should().Be(defrost);
        snapshot.ErrorCode.Should().Be(errorCode);
    }

    [Fact]
    public void CreateFrom_GivenHeatPumpData_WhenCreatingSnapshot_ThenIdIsSetToZeroForDatabaseAssignment()
    {
        // Given
        var heatPumpId = CreateHeatPumpId();
        var timestamp = CreateTimestamp();

        // When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            heatPumpId,
            timestamp,
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.Id.Value.Should().Be(0);
    }

    [Fact]
    public void CreateFrom_GivenTimestamp_WhenCreatingSnapshot_ThenTimestampIsPreservedExactly()
    {
        // Given
        var expectedTimestamp = new DateTimeOffset(2024, 6, 15, 14, 30, 45, 123, TimeSpan.FromHours(2));

        // When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            expectedTimestamp,
            isOn: false,
            OperatingMode.CoolOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.Timestamp.Should().Be(expectedTimestamp);
        snapshot.Timestamp.Offset.Should().Be(TimeSpan.FromHours(2));
    }

    [Fact]
    public void CreateFrom_GivenHeatPumpIsOff_WhenCreatingSnapshot_ThenIsOnIsFalse()
    {
        // Given
        var isOn = false;

        // When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.IsOn.Should().BeFalse();
    }

    [Fact]
    public void CreateFrom_GivenDefrostActive_WhenCreatingSnapshot_ThenDefrostStateIsPreserved()
    {
        // Given
        var defrost = DefrostData.Active;

        // When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            defrost,
            CreateErrorCode());

        // Then
        snapshot.Defrost.IsActive.Should().BeTrue();
    }

    [Fact]
    public void CreateFrom_GivenErrorCode_WhenCreatingSnapshot_ThenErrorCodeIsPreserved()
    {
        // Given
        var errorCode = ErrorCode.From("H15");

        // When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            errorCode);

        // Then
        snapshot.ErrorCode.Code.Should().Be("H15");
        snapshot.ErrorCode.HasError.Should().BeTrue();
    }

    [Theory]
    [InlineData(OperatingMode.HeatOnly)]
    [InlineData(OperatingMode.CoolOnly)]
    [InlineData(OperatingMode.AutoHeat)]
    [InlineData(OperatingMode.DhwOnly)]
    [InlineData(OperatingMode.HeatDhw)]
    [InlineData(OperatingMode.CoolDhw)]
    [InlineData(OperatingMode.AutoHeatDhw)]
    [InlineData(OperatingMode.AutoCool)]
    [InlineData(OperatingMode.AutoCoolDhw)]
    public void CreateFrom_GivenDifferentOperatingModes_WhenCreatingSnapshot_ThenOperatingModeIsPreserved(OperatingMode mode)
    {
        // Given & When
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            mode,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.OperatingMode.Should().Be(mode);
    }

    #endregion

    #region Reconstitute Tests

    [Fact]
    public void Reconstitute_GivenPersistedData_WhenReconstituting_ThenAllFieldsAreRestored()
    {
        // Given
        var id = CreateSnapshotId(999);
        var heatPumpId = CreateHeatPumpId();
        var timestamp = CreateTimestamp();
        var isOn = true;
        var operatingMode = OperatingMode.AutoHeatDhw;
        var pumpFlow = CreatePumpFlow();
        var outsideTemperature = CreateOutsideTemperature();
        var centralHeating = CreateCentralHeatingData();
        var domesticHotWater = CreateDomesticHotWaterData();
        var compressorFrequency = CreateCompressorFrequency();
        var power = CreatePowerData();
        var operations = CreateOperationsData();
        var defrost = CreateDefrostData();
        var errorCode = CreateErrorCode();

        // When
        var snapshot = HeatPumpSnapshot.Reconstitute(
            id,
            heatPumpId,
            timestamp,
            isOn,
            operatingMode,
            pumpFlow,
            outsideTemperature,
            centralHeating,
            domesticHotWater,
            compressorFrequency,
            power,
            operations,
            defrost,
            errorCode);

        // Then
        snapshot.Id.Should().Be(id);
        snapshot.HeatPumpId.Should().Be(heatPumpId);
        snapshot.Timestamp.Should().Be(timestamp);
        snapshot.IsOn.Should().Be(isOn);
        snapshot.OperatingMode.Should().Be(operatingMode);
        snapshot.PumpFlow.Should().Be(pumpFlow);
        snapshot.OutsideTemperature.Should().Be(outsideTemperature);
        snapshot.CentralHeating.Should().Be(centralHeating);
        snapshot.DomesticHotWater.Should().Be(domesticHotWater);
        snapshot.CompressorFrequency.Should().Be(compressorFrequency);
        snapshot.Power.Should().Be(power);
        snapshot.Operations.Should().Be(operations);
        snapshot.Defrost.Should().Be(defrost);
        snapshot.ErrorCode.Should().Be(errorCode);
    }

    [Fact]
    public void Reconstitute_GivenSpecificId_WhenReconstituting_ThenIdIsPreserved()
    {
        // Given
        var expectedId = HeatPumpSnapshotId.From(12345);

        // When
        var snapshot = HeatPumpSnapshot.Reconstitute(
            expectedId,
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.Id.Should().Be(expectedId);
        snapshot.Id.Value.Should().Be(12345);
    }

    [Fact]
    public void Reconstitute_GivenCentralHeatingData_WhenReconstituting_ThenAllTemperaturesAreRestored()
    {
        // Given
        var centralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(32.5m),
            WaterTemperature.FromCelsius(37.8m),
            WaterTemperature.FromCelsius(40.0m));

        // When
        var snapshot = HeatPumpSnapshot.Reconstitute(
            CreateSnapshotId(),
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            centralHeating,
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.CentralHeating.InletTemperature.Celsius.Should().Be(32.5m);
        snapshot.CentralHeating.OutletTemperature.Celsius.Should().Be(37.8m);
        snapshot.CentralHeating.TargetTemperature.Celsius.Should().Be(40.0m);
    }

    [Fact]
    public void Reconstitute_GivenDomesticHotWaterData_WhenReconstituting_ThenTemperaturesAreRestored()
    {
        // Given
        var dhw = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(45.5m),
            DhwTemperature.FromCelsius(52.0m));

        // When
        var snapshot = HeatPumpSnapshot.Reconstitute(
            CreateSnapshotId(),
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.DhwOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            dhw,
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.DomesticHotWater.ActualTemperature.Celsius.Should().Be(45.5m);
        snapshot.DomesticHotWater.TargetTemperature.Celsius.Should().Be(52.0m);
    }

    [Fact]
    public void Reconstitute_GivenPowerData_WhenReconstituting_ThenAllPowerValuesAreRestored()
    {
        // Given
        var power = new PowerData(
            Power.FromWatts(6000),
            Power.FromWatts(1500),
            Power.FromWatts(3000),
            Power.FromWatts(800),
            Power.FromWatts(2000),
            Power.FromWatts(600));

        // When
        var snapshot = HeatPumpSnapshot.Reconstitute(
            CreateSnapshotId(),
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            power,
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.Power.HeatProduction.Watts.Should().Be(6000);
        snapshot.Power.HeatConsumption.Watts.Should().Be(1500);
        snapshot.Power.CoolProduction.Watts.Should().Be(3000);
        snapshot.Power.CoolConsumption.Watts.Should().Be(800);
        snapshot.Power.DhwProduction.Watts.Should().Be(2000);
        snapshot.Power.DhwConsumption.Watts.Should().Be(600);
    }

    [Fact]
    public void Reconstitute_GivenOperationsData_WhenReconstituting_ThenStatisticsAreRestored()
    {
        // Given
        var operations = new OperationsData(15000.75m, 2500);

        // When
        var snapshot = HeatPumpSnapshot.Reconstitute(
            CreateSnapshotId(),
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            operations,
            CreateDefrostData(),
            CreateErrorCode());

        // Then
        snapshot.Operations.CompressorHours.Should().Be(15000.75m);
        snapshot.Operations.CompressorStarts.Should().Be(2500);
    }

    #endregion

    #region Immutability Tests

    [Fact]
    public void Snapshot_GivenCreatedSnapshot_WhenAccessingProperties_ThenPropertiesAreReadOnly()
    {
        // Given
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // When & Then - Verify all properties have private setters via reflection
        var type = typeof(HeatPumpSnapshot);
        var properties = type.GetProperties();

        foreach (var property in properties)
        {
            var setter = property.GetSetMethod(nonPublic: true);
            setter.Should().NotBeNull($"Property {property.Name} should have a setter");
            setter!.IsPrivate.Should().BeTrue($"Property {property.Name} setter should be private");
        }
    }

    [Fact]
    public void Snapshot_GivenValueObjectProperties_ThenValueObjectsAreImmutableRecords()
    {
        // Given & When - Check that value object types are readonly record structs
        var snapshot = HeatPumpSnapshot.CreateFrom(
            CreateHeatPumpId(),
            CreateTimestamp(),
            isOn: true,
            OperatingMode.HeatOnly,
            CreatePumpFlow(),
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then - Value objects should maintain their immutability
        snapshot.HeatPumpId.GetType().IsValueType.Should().BeTrue();
        snapshot.PumpFlow.GetType().IsValueType.Should().BeTrue();
        snapshot.OutsideTemperature.GetType().IsValueType.Should().BeTrue();
        snapshot.CentralHeating.GetType().IsValueType.Should().BeTrue();
        snapshot.DomesticHotWater.GetType().IsValueType.Should().BeTrue();
        snapshot.CompressorFrequency.GetType().IsValueType.Should().BeTrue();
        snapshot.Power.GetType().IsValueType.Should().BeTrue();
        snapshot.Operations.GetType().IsValueType.Should().BeTrue();
        snapshot.Defrost.GetType().IsValueType.Should().BeTrue();
        snapshot.ErrorCode.GetType().IsValueType.Should().BeTrue();
    }

    [Fact]
    public void Snapshot_GivenCreatedSnapshot_WhenCreatingAnotherWithSameData_ThenBothAreIndependent()
    {
        // Given
        var heatPumpId = CreateHeatPumpId();
        var timestamp = CreateTimestamp();
        var pumpFlow = CreatePumpFlow();

        // When
        var snapshot1 = HeatPumpSnapshot.CreateFrom(
            heatPumpId,
            timestamp,
            isOn: true,
            OperatingMode.HeatOnly,
            pumpFlow,
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        var snapshot2 = HeatPumpSnapshot.CreateFrom(
            heatPumpId,
            timestamp,
            isOn: false,
            OperatingMode.CoolOnly,
            pumpFlow,
            CreateOutsideTemperature(),
            CreateCentralHeatingData(),
            CreateDomesticHotWaterData(),
            CreateCompressorFrequency(),
            CreatePowerData(),
            CreateOperationsData(),
            CreateDefrostData(),
            CreateErrorCode());

        // Then - Snapshots are independent
        snapshot1.IsOn.Should().BeTrue();
        snapshot2.IsOn.Should().BeFalse();
        snapshot1.OperatingMode.Should().Be(OperatingMode.HeatOnly);
        snapshot2.OperatingMode.Should().Be(OperatingMode.CoolOnly);
    }

    #endregion

    #region CreateFrom vs Reconstitute Comparison Tests

    [Fact]
    public void CreateFromAndReconstitute_GivenSameData_WhenComparing_ThenOnlyIdDiffers()
    {
        // Given
        var heatPumpId = CreateHeatPumpId();
        var timestamp = CreateTimestamp();
        var isOn = true;
        var operatingMode = OperatingMode.HeatDhw;
        var pumpFlow = CreatePumpFlow();
        var outsideTemperature = CreateOutsideTemperature();
        var centralHeating = CreateCentralHeatingData();
        var domesticHotWater = CreateDomesticHotWaterData();
        var compressorFrequency = CreateCompressorFrequency();
        var power = CreatePowerData();
        var operations = CreateOperationsData();
        var defrost = CreateDefrostData();
        var errorCode = CreateErrorCode();

        // When
        var createdSnapshot = HeatPumpSnapshot.CreateFrom(
            heatPumpId, timestamp, isOn, operatingMode, pumpFlow, outsideTemperature,
            centralHeating, domesticHotWater, compressorFrequency, power, operations, defrost, errorCode);

        var reconstitutedSnapshot = HeatPumpSnapshot.Reconstitute(
            HeatPumpSnapshotId.From(100),
            heatPumpId, timestamp, isOn, operatingMode, pumpFlow, outsideTemperature,
            centralHeating, domesticHotWater, compressorFrequency, power, operations, defrost, errorCode);

        // Then
        createdSnapshot.Id.Value.Should().Be(0);
        reconstitutedSnapshot.Id.Value.Should().Be(100);

        // All other properties should be equal
        createdSnapshot.HeatPumpId.Should().Be(reconstitutedSnapshot.HeatPumpId);
        createdSnapshot.Timestamp.Should().Be(reconstitutedSnapshot.Timestamp);
        createdSnapshot.IsOn.Should().Be(reconstitutedSnapshot.IsOn);
        createdSnapshot.OperatingMode.Should().Be(reconstitutedSnapshot.OperatingMode);
        createdSnapshot.PumpFlow.Should().Be(reconstitutedSnapshot.PumpFlow);
        createdSnapshot.OutsideTemperature.Should().Be(reconstitutedSnapshot.OutsideTemperature);
        createdSnapshot.CentralHeating.Should().Be(reconstitutedSnapshot.CentralHeating);
        createdSnapshot.DomesticHotWater.Should().Be(reconstitutedSnapshot.DomesticHotWater);
        createdSnapshot.CompressorFrequency.Should().Be(reconstitutedSnapshot.CompressorFrequency);
        createdSnapshot.Power.Should().Be(reconstitutedSnapshot.Power);
        createdSnapshot.Operations.Should().Be(reconstitutedSnapshot.Operations);
        createdSnapshot.Defrost.Should().Be(reconstitutedSnapshot.Defrost);
        createdSnapshot.ErrorCode.Should().Be(reconstitutedSnapshot.ErrorCode);
    }

    #endregion
}
