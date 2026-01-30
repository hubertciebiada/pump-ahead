using FluentAssertions;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.Aggregates;

public class HeatPumpSyncTests
{
    private const string DefaultHeatPumpModel = "Panasonic WH-MDC09J3E5";
    private const decimal ZeroLitersPerMinute = 0m;
    private const decimal ZeroFrequencyHertz = 0m;
    private const decimal FiveOutsideTemperatureCelsius = 5m;
    private const decimal TwentyFiveWaterTemperatureCelsius = 25m;
    private const decimal ThirtyFiveWaterTemperatureCelsius = 35m;
    private const decimal FortyDhwTemperatureCelsius = 40m;
    private const decimal FortyEightDhwTemperatureCelsius = 48m;
    private const decimal FortyFiveFrequencyHertz = 45m;
    private const decimal FiftyFiveFrequencyHertz = 55m;
    private const decimal ThirtyWaterTemperatureCelsius = 30m;
    private const decimal FortyFrequencyHertz = 40m;
    private const decimal TenLitersPerMinute = 10m;
    private const decimal TwelvePointFiveLitersPerMinute = 12.5m;
    private const decimal EightOutsideTemperatureCelsius = 8m;
    private const decimal TwentyEightWaterTemperatureCelsius = 28m;
    private const decimal FiftyDhwTemperatureCelsius = 50m;

    #region Test Helpers

    private static HeatPump CreateHeatPumpWithInitialState()
    {
        return HeatPump.Reconstitute(
            HeatPumpId.NewId(),
            DefaultHeatPumpModel,
            DateTimeOffset.UtcNow.AddHours(-1),
            isOn: false,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
            OutsideTemperature.FromCelsius(FiveOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(TwentyFiveWaterTemperatureCelsius),
                WaterTemperature.FromCelsius(TwentyFiveWaterTemperatureCelsius),
                WaterTemperature.FromCelsius(ThirtyFiveWaterTemperatureCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(FortyDhwTemperatureCelsius),
                DhwTemperature.FromCelsius(FortyEightDhwTemperatureCelsius)),
            Frequency.FromHertz(ZeroFrequencyHertz),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);
    }

    #endregion

    #region Given: existing HeatPump, When: SyncFrom with data, Then: properties updated

    [Fact]
    public void SyncFrom_WithValidData_UpdatesIsOnProperty()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        heatPump.IsOn.Should().BeFalse();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(TwelvePointFiveLitersPerMinute),
            OutsideTemperature.FromCelsius(EightOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(TwentyEightWaterTemperatureCelsius),
                WaterTemperature.FromCelsius(ThirtyFiveWaterTemperatureCelsius),
                WaterTemperature.FromCelsius(38)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(FiftyDhwTemperatureCelsius)),
            Frequency.FromHertz(FiftyFiveFrequencyHertz),
            new PowerData(
                Power.FromWatts(5000), Power.FromWatts(1200),
                Power.Zero, Power.Zero,
                Power.Zero, Power.Zero),
            new OperationsData(1500.5m, 2500),
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.IsOn.Should().BeTrue();
    }

    [Fact]
    public void SyncFrom_WithValidData_UpdatesLastSyncTime()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var originalSyncTime = heatPump.LastSyncTime;
        var beforeSync = DateTimeOffset.UtcNow;

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(TenLitersPerMinute),
            OutsideTemperature.FromCelsius(FiveOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(TwentyFiveWaterTemperatureCelsius),
                WaterTemperature.FromCelsius(ThirtyWaterTemperatureCelsius),
                WaterTemperature.FromCelsius(ThirtyFiveWaterTemperatureCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(FortyEightDhwTemperatureCelsius)),
            Frequency.FromHertz(FortyFrequencyHertz),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        var afterSync = DateTimeOffset.UtcNow;

        // Then
        heatPump.LastSyncTime.Should().BeOnOrAfter(beforeSync);
        heatPump.LastSyncTime.Should().BeOnOrBefore(afterSync);
        heatPump.LastSyncTime.Should().BeAfter(originalSyncTime);
    }

    [Fact]
    public void SyncFrom_PreservesIdAndModel()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var originalId = heatPump.Id;
        var originalModel = heatPump.Model;

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.CoolOnly,
            PumpFlow.FromLitersPerMinute(15),
            OutsideTemperature.FromCelsius(ThirtyWaterTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(20),
                WaterTemperature.FromCelsius(15),
                WaterTemperature.FromCelsius(12)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(FortyEightDhwTemperatureCelsius)),
            Frequency.FromHertz(60),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.Id.Should().Be(originalId);
        heatPump.Model.Should().Be(originalModel);
    }

    #endregion

    #region Mapping all fields

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void SyncFrom_MapsIsOnCorrectly(bool expectedIsOn)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: expectedIsOn,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.IsOn.Should().Be(expectedIsOn);
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
    public void SyncFrom_MapsOperatingModeCorrectly(OperatingMode expectedMode)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            operatingMode: expectedMode,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.OperatingMode.Should().Be(expectedMode);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(10.5)]
    [InlineData(25.0)]
    public void SyncFrom_MapsPumpFlowCorrectly(decimal expectedFlow)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            pumpFlow: PumpFlow.FromLitersPerMinute(expectedFlow),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.PumpFlow.LitersPerMinute.Should().Be(expectedFlow);
    }

    [Theory]
    [InlineData(-20)]
    [InlineData(0)]
    [InlineData(35)]
    public void SyncFrom_MapsOutsideTemperatureCorrectly(decimal expectedTemp)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            outsideTemperature: OutsideTemperature.FromCelsius(expectedTemp),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.OutsideTemperature.Celsius.Should().Be(expectedTemp);
    }

    [Fact]
    public void SyncFrom_MapsCentralHeatingDataCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var expectedCentralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(28.5m),
            WaterTemperature.FromCelsius(35.2m),
            WaterTemperature.FromCelsius(38.0m));

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            centralHeating: expectedCentralHeating,
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.CentralHeating.InletTemperature.Celsius.Should().Be(28.5m);
        heatPump.CentralHeating.OutletTemperature.Celsius.Should().Be(35.2m);
        heatPump.CentralHeating.TargetTemperature.Celsius.Should().Be(38.0m);
    }

    [Fact]
    public void SyncFrom_MapsDomesticHotWaterDataCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var expectedDhw = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(52.3m),
            DhwTemperature.FromCelsius(55.0m));

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.DhwOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            domesticHotWater: expectedDhw,
            Frequency.FromHertz(50),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.DomesticHotWater.ActualTemperature.Celsius.Should().Be(52.3m);
        heatPump.DomesticHotWater.TargetTemperature.Celsius.Should().Be(55.0m);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(55)]
    [InlineData(120)]
    public void SyncFrom_MapsCompressorFrequencyCorrectly(decimal expectedFrequency)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            compressorFrequency: Frequency.FromHertz(expectedFrequency),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.CompressorFrequency.Hertz.Should().Be(expectedFrequency);
    }

    [Fact]
    public void SyncFrom_MapsPowerDataCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var expectedPower = new PowerData(
            Power.FromWatts(5500),
            Power.FromWatts(1300),
            Power.FromWatts(0),
            Power.FromWatts(0),
            Power.FromWatts(3200),
            Power.FromWatts(800));

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(12),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(28),
                WaterTemperature.FromCelsius(35),
                WaterTemperature.FromCelsius(38)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(50)),
            Frequency.FromHertz(55),
            power: expectedPower,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.Power.HeatProduction.Watts.Should().Be(5500);
        heatPump.Power.HeatConsumption.Watts.Should().Be(1300);
        heatPump.Power.CoolProduction.Watts.Should().Be(0);
        heatPump.Power.CoolConsumption.Watts.Should().Be(0);
        heatPump.Power.DhwProduction.Watts.Should().Be(3200);
        heatPump.Power.DhwConsumption.Watts.Should().Be(800);
    }

    [Fact]
    public void SyncFrom_MapsOperationsDataCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var expectedOperations = new OperationsData(12500.75m, 5420);

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            operations: expectedOperations,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.Operations.CompressorHours.Should().Be(12500.75m);
        heatPump.Operations.CompressorStarts.Should().Be(5420);
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void SyncFrom_MapsDefrostDataCorrectly(bool isDefrosting)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var expectedDefrost = new DefrostData(isDefrosting);

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(-5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            defrost: expectedDefrost,
            ErrorCode.None);

        // Then
        heatPump.Defrost.IsActive.Should().Be(isDefrosting);
    }

    [Theory]
    [InlineData("")]
    [InlineData("H00")]
    [InlineData("H15")]
    [InlineData("F12")]
    public void SyncFrom_MapsErrorCodeCorrectly(string errorCodeValue)
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var expectedErrorCode = ErrorCode.From(errorCodeValue);

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(40),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            errorCode: expectedErrorCode);

        // Then
        heatPump.ErrorCode.Code.Should().Be(errorCodeValue);
    }

    #endregion

    #region Edge cases - extreme values

    [Fact]
    public void SyncFrom_WithExtremelyLowTemperature_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(8),
            OutsideTemperature.FromCelsius(-40m),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(20),
                WaterTemperature.FromCelsius(45),
                WaterTemperature.FromCelsius(50)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(40),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(120),
            new PowerData(
                Power.FromWatts(10000), Power.FromWatts(3000),
                Power.Zero, Power.Zero,
                Power.Zero, Power.Zero),
            OperationsData.Zero,
            DefrostData.Active,
            ErrorCode.None);

        // Then
        heatPump.OutsideTemperature.Celsius.Should().Be(-40m);
    }

    [Fact]
    public void SyncFrom_WithExtremelyHighTemperature_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.CoolOnly,
            PumpFlow.FromLitersPerMinute(20),
            OutsideTemperature.FromCelsius(50m),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(15),
                WaterTemperature.FromCelsius(7),
                WaterTemperature.FromCelsius(5)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(100),
            new PowerData(
                Power.Zero, Power.Zero,
                Power.FromWatts(8000), Power.FromWatts(2500),
                Power.Zero, Power.Zero),
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.OutsideTemperature.Celsius.Should().Be(50m);
    }

    [Fact]
    public void SyncFrom_WithMaximumCompressorFrequency_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(15),
            OutsideTemperature.FromCelsius(-15),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(50),
                WaterTemperature.FromCelsius(55)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(50),
                DhwTemperature.FromCelsius(55)),
            Frequency.FromHertz(165m),
            new PowerData(
                Power.FromWatts(14000), Power.FromWatts(4000),
                Power.Zero, Power.Zero,
                Power.Zero, Power.Zero),
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.CompressorFrequency.Hertz.Should().Be(165m);
    }

    [Fact]
    public void SyncFrom_WithZeroCompressorFrequency_WhenOff_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: false,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(0),
            OutsideTemperature.FromCelsius(10),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(22),
                WaterTemperature.FromCelsius(22),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(0),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.CompressorFrequency.Hertz.Should().Be(0);
        heatPump.PumpFlow.LitersPerMinute.Should().Be(0);
    }

    [Fact]
    public void SyncFrom_WithVeryHighOperationHours_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var highOperations = new OperationsData(100000.5m, 50000);

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(50),
            PowerData.Zero,
            operations: highOperations,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.Operations.CompressorHours.Should().Be(100000.5m);
        heatPump.Operations.CompressorStarts.Should().Be(50000);
    }

    [Fact]
    public void SyncFrom_WithVeryHighPowerValues_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();
        var highPower = new PowerData(
            Power.FromWatts(20000),
            Power.FromWatts(6000),
            Power.FromWatts(15000),
            Power.FromWatts(5000),
            Power.FromWatts(8000),
            Power.FromWatts(2000));

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.AutoHeatDhw,
            PumpFlow.FromLitersPerMinute(25),
            OutsideTemperature.FromCelsius(0),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(45),
                WaterTemperature.FromCelsius(50)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(52),
                DhwTemperature.FromCelsius(55)),
            Frequency.FromHertz(150),
            power: highPower,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.Power.HeatProduction.Watts.Should().Be(20000);
        heatPump.Power.HeatConsumption.Watts.Should().Be(6000);
        heatPump.Power.TotalConsumption.Watts.Should().Be(13000);
    }

    [Fact]
    public void SyncFrom_WithAllZeroValues_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: false,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(0),
            OutsideTemperature.FromCelsius(0),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(0),
                WaterTemperature.FromCelsius(0),
                WaterTemperature.FromCelsius(0)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(0),
                DhwTemperature.FromCelsius(0)),
            Frequency.FromHertz(0),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.IsOn.Should().BeFalse();
        heatPump.PumpFlow.LitersPerMinute.Should().Be(0);
        heatPump.OutsideTemperature.Celsius.Should().Be(0);
        heatPump.CompressorFrequency.Hertz.Should().Be(0);
    }

    [Fact]
    public void SyncFrom_WithDecimalPrecision_MapsCorrectly()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // When
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(12.345m),
            OutsideTemperature.FromCelsius(7.891m),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(28.123m),
                WaterTemperature.FromCelsius(35.456m),
                WaterTemperature.FromCelsius(38.789m)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(48.111m),
                DhwTemperature.FromCelsius(50.222m)),
            Frequency.FromHertz(55.333m),
            new PowerData(
                Power.FromWatts(5123.45m), Power.FromWatts(1234.56m),
                Power.Zero, Power.Zero,
                Power.Zero, Power.Zero),
            new OperationsData(1500.789m, 2500),
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.PumpFlow.LitersPerMinute.Should().Be(12.345m);
        heatPump.OutsideTemperature.Celsius.Should().Be(7.891m);
        heatPump.CentralHeating.InletTemperature.Celsius.Should().Be(28.123m);
        heatPump.CentralHeating.OutletTemperature.Celsius.Should().Be(35.456m);
        heatPump.CentralHeating.TargetTemperature.Celsius.Should().Be(38.789m);
        heatPump.CompressorFrequency.Hertz.Should().Be(55.333m);
        heatPump.Operations.CompressorHours.Should().Be(1500.789m);
    }

    #endregion

    #region Multiple syncs

    [Fact]
    public void SyncFrom_CalledMultipleTimes_UpdatesAllPropertiesEachTime()
    {
        // Given
        var heatPump = CreateHeatPumpWithInitialState();

        // First sync - heat pump starting
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(10),
            OutsideTemperature.FromCelsius(5),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(25),
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(35)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(45),
                DhwTemperature.FromCelsius(48)),
            Frequency.FromHertz(30),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);

        heatPump.IsOn.Should().BeTrue();
        heatPump.CompressorFrequency.Hertz.Should().Be(30);

        // Second sync - heat pump at full power
        heatPump.SyncFrom(
            isOn: true,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(15),
            OutsideTemperature.FromCelsius(3),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(30),
                WaterTemperature.FromCelsius(40),
                WaterTemperature.FromCelsius(42)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(50),
                DhwTemperature.FromCelsius(55)),
            Frequency.FromHertz(80),
            new PowerData(
                Power.FromWatts(6000), Power.FromWatts(1500),
                Power.Zero, Power.Zero,
                Power.FromWatts(3000), Power.FromWatts(750)),
            new OperationsData(100, 50),
            DefrostData.Inactive,
            ErrorCode.None);

        heatPump.OperatingMode.Should().Be(OperatingMode.HeatDhw);
        heatPump.CompressorFrequency.Hertz.Should().Be(80);

        // Third sync - heat pump stopping
        heatPump.SyncFrom(
            isOn: false,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(0),
            OutsideTemperature.FromCelsius(2),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(32),
                WaterTemperature.FromCelsius(32),
                WaterTemperature.FromCelsius(42)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(55),
                DhwTemperature.FromCelsius(55)),
            Frequency.FromHertz(0),
            PowerData.Zero,
            new OperationsData(100.5m, 51),
            DefrostData.Inactive,
            ErrorCode.None);

        // Then
        heatPump.IsOn.Should().BeFalse();
        heatPump.CompressorFrequency.Hertz.Should().Be(0);
        heatPump.PumpFlow.LitersPerMinute.Should().Be(0);
        heatPump.DomesticHotWater.ActualTemperature.Celsius.Should().Be(55);
        heatPump.Operations.CompressorStarts.Should().Be(51);
    }

    #endregion
}
