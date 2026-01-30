using FluentAssertions;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.Aggregates;

public class HeatPumpTests
{
    private const string DefaultHeatPumpModel = "Panasonic WH-MDC09J3E5";
    private const string EmptyModel = "";
    private const string WhitespaceModel = "   ";
    private const string ModelCannotBeEmptyMessage = "*Model cannot be empty*";
    private const string ModelParameterName = "model";
    private const string OkStatus = "OK";
    private const string H15ErrorCode = "H15";
    private const string H00ErrorCode = "H00";
    private const string DefaultGuidString = "12345678-1234-1234-1234-123456789abc";

    private const decimal DefaultInletTemperature = 30m;
    private const decimal DefaultOutletTemperature = 35m;
    private const decimal DefaultTargetTemperature = 40m;
    private const decimal DefaultDhwActualTemperature = 45m;
    private const decimal DefaultDhwTargetTemperature = 50m;
    private const decimal DefaultOutsideTemperatureCelsius = 10m;
    private const decimal MinusFiveOutsideTemperatureCelsius = -5m;
    private const decimal DefaultPumpFlowLitersPerMinute = 12.5m;
    private const decimal ZeroLitersPerMinute = 0m;
    private const decimal DefaultFrequencyHertz = 50m;
    private const decimal ZeroFrequencyHertz = 0m;
    private const decimal FiveOutsideTemperatureCelsius = 5m;
    private const decimal FortyFiveFrequencyHertz = 45m;
    private const decimal FiftyFiveFrequencyHertz = 55m;

    private const decimal DefaultCompressorHours = 1000m;
    private const decimal DefaultCompressorHoursSecond = 500m;
    private const int DefaultCompressorStarts = 500;
    private const int DefaultCompressorStartsSecond = 250;
    private const decimal FifteenHundredCompressorHours = 1500m;
    private const int SevenFiftyCompressorStarts = 750;

    private const int FiveThousandWatts = 5000;
    private const int TwelveHundredWatts = 1200;
    private const int ThreeThousandWatts = 3000;
    private const int EightHundredWatts = 800;

    #region Test Data Builders

    private static HeatPumpId CreateValidId() => HeatPumpId.NewId();

    private static HeatPumpId CreateSpecificId(Guid guid) => HeatPumpId.From(guid);

    private static CentralHeatingData CreateCentralHeatingData(
        decimal inlet = DefaultInletTemperature,
        decimal outlet = DefaultOutletTemperature,
        decimal target = DefaultTargetTemperature)
    {
        return new CentralHeatingData(
            WaterTemperature.FromCelsius(inlet),
            WaterTemperature.FromCelsius(outlet),
            WaterTemperature.FromCelsius(target));
    }

    private static DomesticHotWaterData CreateDomesticHotWaterData(
        decimal actual = DefaultDhwActualTemperature,
        decimal target = DefaultDhwTargetTemperature)
    {
        return new DomesticHotWaterData(
            DhwTemperature.FromCelsius(actual),
            DhwTemperature.FromCelsius(target));
    }

    private static PowerData CreatePowerData() => PowerData.Zero;

    #endregion

    #region Reconstitute - Given-When-Then Tests

    public class Reconstitute_WhenCalledWithValidParameters
    {
        [Fact]
        public void Given_ValidId_When_Reconstituted_Then_IdIsSetCorrectly()
        {
            // Given
            var expectedId = Guid.Parse(DefaultGuidString);
            var id = HeatPumpId.From(expectedId);
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: CreateCentralHeatingData(),
                domesticHotWater: CreateDomesticHotWaterData(),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: CreatePowerData(),
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.Id.Should().Be(id);
            heatPump.Id.Value.Should().Be(expectedId);
        }

        [Fact]
        public void Given_ValidModel_When_Reconstituted_Then_ModelIsSetCorrectly()
        {
            // Given
            var id = HeatPumpId.NewId();
            var expectedModel = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                expectedModel,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: CreateCentralHeatingData(),
                domesticHotWater: CreateDomesticHotWaterData(),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: CreatePowerData(),
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.Model.Should().Be(expectedModel);
        }

        [Fact]
        public void Given_LastSyncTime_When_Reconstituted_Then_LastSyncTimeIsSetCorrectly()
        {
            // Given
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var expectedLastSyncTime = new DateTimeOffset(2024, 1, 15, 10, 30, 0, TimeSpan.Zero);

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                expectedLastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: CreateCentralHeatingData(),
                domesticHotWater: CreateDomesticHotWaterData(),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: CreatePowerData(),
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.LastSyncTime.Should().Be(expectedLastSyncTime);
        }

        [Fact]
        public void Given_IsOnTrue_When_Reconstituted_Then_IsOnIsTrue()
        {
            // Given
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: true,
                operatingMode: OperatingMode.HeatDhw,
                pumpFlow: PumpFlow.FromLitersPerMinute(DefaultPumpFlowLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(FiveOutsideTemperatureCelsius),
                centralHeating: CreateCentralHeatingData(),
                domesticHotWater: CreateDomesticHotWaterData(),
                compressorFrequency: Frequency.FromHertz(DefaultFrequencyHertz),
                power: CreatePowerData(),
                operations: new OperationsData(DefaultCompressorHours, DefaultCompressorStarts),
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.IsOn.Should().BeTrue();
        }

        [Fact]
        public void Given_IsOnFalse_When_Reconstituted_Then_IsOnIsFalse()
        {
            // Given
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: CreateCentralHeatingData(),
                domesticHotWater: CreateDomesticHotWaterData(),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: CreatePowerData(),
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.IsOn.Should().BeFalse();
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
        public void Given_OperatingMode_When_Reconstituted_Then_OperatingModeIsSetCorrectly(
            OperatingMode expectedMode)
        {
            // Given
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: false,
                operatingMode: expectedMode,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: CreateCentralHeatingData(),
                domesticHotWater: CreateDomesticHotWaterData(),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: CreatePowerData(),
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.OperatingMode.Should().Be(expectedMode);
        }

        private static CentralHeatingData CreateCentralHeatingData(
            decimal inlet = DefaultInletTemperature,
            decimal outlet = DefaultOutletTemperature,
            decimal target = DefaultTargetTemperature)
        {
            return new CentralHeatingData(
                WaterTemperature.FromCelsius(inlet),
                WaterTemperature.FromCelsius(outlet),
                WaterTemperature.FromCelsius(target));
        }

        private static DomesticHotWaterData CreateDomesticHotWaterData(
            decimal actual = DefaultDhwActualTemperature,
            decimal target = DefaultDhwTargetTemperature)
        {
            return new DomesticHotWaterData(
                DhwTemperature.FromCelsius(actual),
                DhwTemperature.FromCelsius(target));
        }

        private static PowerData CreatePowerData() => PowerData.Zero;
    }

    public class Reconstitute_WhenCalledWithAllProperties
    {
        [Fact]
        public void Given_CompleteState_When_Reconstituted_Then_AllPropertiesAreSetCorrectly()
        {
            // Given
            var expectedId = HeatPumpId.NewId();
            var expectedModel = DefaultHeatPumpModel;
            var expectedLastSyncTime = new DateTimeOffset(2024, 1, 15, 10, 30, 0, TimeSpan.Zero);
            var expectedIsOn = true;
            var expectedOperatingMode = OperatingMode.HeatDhw;
            var expectedPumpFlow = PumpFlow.FromLitersPerMinute(DefaultPumpFlowLitersPerMinute);
            var expectedOutsideTemp = OutsideTemperature.FromCelsius(MinusFiveOutsideTemperatureCelsius);
            var expectedCentralHeating = new CentralHeatingData(
                WaterTemperature.FromCelsius(DefaultInletTemperature),
                WaterTemperature.FromCelsius(DefaultOutletTemperature),
                WaterTemperature.FromCelsius(DefaultTargetTemperature));
            var expectedDhw = new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                DhwTemperature.FromCelsius(DefaultDhwTargetTemperature));
            var expectedFrequency = Frequency.FromHertz(FiftyFiveFrequencyHertz);
            var expectedPower = new PowerData(
                Power.FromWatts(FiveThousandWatts),
                Power.FromWatts(TwelveHundredWatts),
                Power.Zero,
                Power.Zero,
                Power.FromWatts(ThreeThousandWatts),
                Power.FromWatts(EightHundredWatts));
            var expectedOperations = new OperationsData(FifteenHundredCompressorHours, SevenFiftyCompressorStarts);
            var expectedDefrost = DefrostData.Active;
            var expectedErrorCode = ErrorCode.From(H15ErrorCode);

            // When
            var heatPump = HeatPump.Reconstitute(
                expectedId,
                expectedModel,
                expectedLastSyncTime,
                expectedIsOn,
                expectedOperatingMode,
                expectedPumpFlow,
                expectedOutsideTemp,
                expectedCentralHeating,
                expectedDhw,
                expectedFrequency,
                expectedPower,
                expectedOperations,
                expectedDefrost,
                expectedErrorCode);

            // Then
            heatPump.Id.Should().Be(expectedId);
            heatPump.Model.Should().Be(expectedModel);
            heatPump.LastSyncTime.Should().Be(expectedLastSyncTime);
            heatPump.IsOn.Should().Be(expectedIsOn);
            heatPump.OperatingMode.Should().Be(expectedOperatingMode);
            heatPump.PumpFlow.Should().Be(expectedPumpFlow);
            heatPump.OutsideTemperature.Should().Be(expectedOutsideTemp);
            heatPump.CentralHeating.Should().Be(expectedCentralHeating);
            heatPump.DomesticHotWater.Should().Be(expectedDhw);
            heatPump.CompressorFrequency.Should().Be(expectedFrequency);
            heatPump.Power.Should().Be(expectedPower);
            heatPump.Operations.Should().Be(expectedOperations);
            heatPump.Defrost.Should().Be(expectedDefrost);
            heatPump.ErrorCode.Should().Be(expectedErrorCode);
        }
    }

    #endregion

    #region Reconstitute - Validation Tests

    public class Reconstitute_WhenCalledWithInvalidParameters
    {
        [Fact]
        public void Given_EmptyModel_When_Reconstituted_Then_ThrowsArgumentException()
        {
            // Given
            var id = HeatPumpId.NewId();
            var emptyModel = EmptyModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var act = () => HeatPump.Reconstitute(
                id,
                emptyModel,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: new CentralHeatingData(
                    WaterTemperature.FromCelsius(DefaultInletTemperature),
                    WaterTemperature.FromCelsius(DefaultOutletTemperature),
                    WaterTemperature.FromCelsius(DefaultTargetTemperature)),
                domesticHotWater: new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                    DhwTemperature.FromCelsius(DefaultDhwTargetTemperature)),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: PowerData.Zero,
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            act.Should().Throw<ArgumentException>()
                .WithParameterName(ModelParameterName)
                .WithMessage(ModelCannotBeEmptyMessage);
        }

        [Fact]
        public void Given_WhitespaceModel_When_Reconstituted_Then_ThrowsArgumentException()
        {
            // Given
            var id = HeatPumpId.NewId();
            var whitespaceModel = WhitespaceModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var act = () => HeatPump.Reconstitute(
                id,
                whitespaceModel,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: new CentralHeatingData(
                    WaterTemperature.FromCelsius(DefaultInletTemperature),
                    WaterTemperature.FromCelsius(DefaultOutletTemperature),
                    WaterTemperature.FromCelsius(DefaultTargetTemperature)),
                domesticHotWater: new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                    DhwTemperature.FromCelsius(DefaultDhwTargetTemperature)),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: PowerData.Zero,
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            act.Should().Throw<ArgumentException>()
                .WithParameterName(ModelParameterName)
                .WithMessage(ModelCannotBeEmptyMessage);
        }

        [Fact]
        public void Given_NullModel_When_Reconstituted_Then_ThrowsArgumentException()
        {
            // Given
            var id = HeatPumpId.NewId();
            string? nullModel = null;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var act = () => HeatPump.Reconstitute(
                id,
                nullModel!,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: new CentralHeatingData(
                    WaterTemperature.FromCelsius(DefaultInletTemperature),
                    WaterTemperature.FromCelsius(DefaultOutletTemperature),
                    WaterTemperature.FromCelsius(DefaultTargetTemperature)),
                domesticHotWater: new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                    DhwTemperature.FromCelsius(DefaultDhwTargetTemperature)),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: PowerData.Zero,
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            act.Should().Throw<ArgumentException>()
                .WithParameterName(ModelParameterName);
        }
    }

    #endregion

    #region Default/Initial State Tests

    public class DefaultState_WhenHeatPumpIsOff
    {
        [Fact]
        public void Given_OffState_When_Reconstituted_Then_HasExpectedDefaultValues()
        {
            // Given - a heat pump in "off" state with default/zero values
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(0),
                centralHeating: new CentralHeatingData(
                    WaterTemperature.FromCelsius(0),
                    WaterTemperature.FromCelsius(0),
                    WaterTemperature.FromCelsius(0)),
                domesticHotWater: new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(0),
                    DhwTemperature.FromCelsius(0)),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: PowerData.Zero,
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: ErrorCode.None);

            // Then
            heatPump.IsOn.Should().BeFalse();
            heatPump.PumpFlow.LitersPerMinute.Should().Be(0);
            heatPump.CompressorFrequency.Hertz.Should().Be(0);
            heatPump.Power.TotalConsumption.Watts.Should().Be(0);
            heatPump.Defrost.IsActive.Should().BeFalse();
            heatPump.ErrorCode.HasError.Should().BeFalse();
        }

        [Fact]
        public void Given_NoError_When_Reconstituted_Then_ErrorCodeHasNoError()
        {
            // Given
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;
            var noError = ErrorCode.None;

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: new CentralHeatingData(
                    WaterTemperature.FromCelsius(DefaultInletTemperature),
                    WaterTemperature.FromCelsius(DefaultOutletTemperature),
                    WaterTemperature.FromCelsius(DefaultTargetTemperature)),
                domesticHotWater: new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                    DhwTemperature.FromCelsius(DefaultDhwTargetTemperature)),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: PowerData.Zero,
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: noError);

            // Then
            heatPump.ErrorCode.HasError.Should().BeFalse();
            heatPump.ErrorCode.ToString().Should().Be(OkStatus);
        }

        [Fact]
        public void Given_H00ErrorCode_When_Reconstituted_Then_ErrorCodeHasNoError()
        {
            // Given - H00 is the "no error" code from Panasonic
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = DateTimeOffset.UtcNow;
            var h00Error = ErrorCode.From(H00ErrorCode);

            // When
            var heatPump = HeatPump.Reconstitute(
                id,
                model,
                lastSyncTime,
                isOn: false,
                operatingMode: OperatingMode.HeatOnly,
                pumpFlow: PumpFlow.FromLitersPerMinute(ZeroLitersPerMinute),
                outsideTemperature: OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
                centralHeating: new CentralHeatingData(
                    WaterTemperature.FromCelsius(DefaultInletTemperature),
                    WaterTemperature.FromCelsius(DefaultOutletTemperature),
                    WaterTemperature.FromCelsius(DefaultTargetTemperature)),
                domesticHotWater: new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                    DhwTemperature.FromCelsius(DefaultDhwTargetTemperature)),
                compressorFrequency: Frequency.FromHertz(ZeroFrequencyHertz),
                power: PowerData.Zero,
                operations: OperationsData.Zero,
                defrost: DefrostData.Inactive,
                errorCode: h00Error);

            // Then
            heatPump.ErrorCode.HasError.Should().BeFalse();
        }
    }

    #endregion

    #region State Persistence Tests

    public class StatePersistence_WhenReconstitutingFromStorage
    {
        [Fact]
        public void Given_StoredState_When_Reconstituted_Then_StateIsPreserved()
        {
            // Given - simulating persistence round-trip
            var originalId = HeatPumpId.NewId();
            var originalModel = DefaultHeatPumpModel;
            var originalLastSyncTime = new DateTimeOffset(2024, 1, 15, 10, 30, 0, TimeSpan.Zero);
            var originalIsOn = true;
            var originalOperatingMode = OperatingMode.HeatDhw;
            var originalPumpFlow = PumpFlow.FromLitersPerMinute(DefaultPumpFlowLitersPerMinute);

            // When - reconstitute from "stored" values
            var heatPump = HeatPump.Reconstitute(
                originalId,
                originalModel,
                originalLastSyncTime,
                originalIsOn,
                originalOperatingMode,
                originalPumpFlow,
                OutsideTemperature.FromCelsius(FiveOutsideTemperatureCelsius),
                new CentralHeatingData(
                    WaterTemperature.FromCelsius(DefaultInletTemperature),
                    WaterTemperature.FromCelsius(DefaultOutletTemperature),
                    WaterTemperature.FromCelsius(DefaultTargetTemperature)),
                new DomesticHotWaterData(
                    DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                    DhwTemperature.FromCelsius(DefaultDhwTargetTemperature)),
                Frequency.FromHertz(FortyFiveFrequencyHertz),
                PowerData.Zero,
                new OperationsData(DefaultCompressorHoursSecond, DefaultCompressorStartsSecond),
                DefrostData.Inactive,
                ErrorCode.None);

            // Then - all state should be preserved
            heatPump.Id.Should().Be(originalId);
            heatPump.Model.Should().Be(originalModel);
            heatPump.LastSyncTime.Should().Be(originalLastSyncTime);
            heatPump.IsOn.Should().Be(originalIsOn);
            heatPump.OperatingMode.Should().Be(originalOperatingMode);
            heatPump.PumpFlow.Should().Be(originalPumpFlow);
        }

        [Fact]
        public void Given_TwoReconstituteCallsWithSameData_When_Compared_Then_HaveSamePropertyValues()
        {
            // Given
            var id = HeatPumpId.NewId();
            var model = DefaultHeatPumpModel;
            var lastSyncTime = new DateTimeOffset(2024, 1, 15, 10, 30, 0, TimeSpan.Zero);
            var centralHeating = new CentralHeatingData(
                WaterTemperature.FromCelsius(DefaultInletTemperature),
                WaterTemperature.FromCelsius(DefaultOutletTemperature),
                WaterTemperature.FromCelsius(DefaultTargetTemperature));
            var dhw = new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DefaultDhwActualTemperature),
                DhwTemperature.FromCelsius(DefaultDhwTargetTemperature));

            // When
            var heatPump1 = HeatPump.Reconstitute(
                id, model, lastSyncTime, true, OperatingMode.HeatDhw,
                PumpFlow.FromLitersPerMinute(DefaultOutsideTemperatureCelsius), OutsideTemperature.FromCelsius(FiveOutsideTemperatureCelsius),
                centralHeating, dhw, Frequency.FromHertz(DefaultFrequencyHertz), PowerData.Zero,
                OperationsData.Zero, DefrostData.Inactive, ErrorCode.None);

            var heatPump2 = HeatPump.Reconstitute(
                id, model, lastSyncTime, true, OperatingMode.HeatDhw,
                PumpFlow.FromLitersPerMinute(DefaultOutsideTemperatureCelsius), OutsideTemperature.FromCelsius(FiveOutsideTemperatureCelsius),
                centralHeating, dhw, Frequency.FromHertz(DefaultFrequencyHertz), PowerData.Zero,
                OperationsData.Zero, DefrostData.Inactive, ErrorCode.None);

            // Then
            heatPump1.Id.Should().Be(heatPump2.Id);
            heatPump1.Model.Should().Be(heatPump2.Model);
            heatPump1.LastSyncTime.Should().Be(heatPump2.LastSyncTime);
            heatPump1.IsOn.Should().Be(heatPump2.IsOn);
            heatPump1.OperatingMode.Should().Be(heatPump2.OperatingMode);
            heatPump1.PumpFlow.Should().Be(heatPump2.PumpFlow);
            heatPump1.OutsideTemperature.Should().Be(heatPump2.OutsideTemperature);
            heatPump1.CentralHeating.Should().Be(heatPump2.CentralHeating);
            heatPump1.DomesticHotWater.Should().Be(heatPump2.DomesticHotWater);
            heatPump1.CompressorFrequency.Should().Be(heatPump2.CompressorFrequency);
        }
    }

    #endregion
}
