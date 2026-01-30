using FluentAssertions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.SaveHeatPumpSnapshot;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.ProcessModel.Tests.Commands;

public class SaveHeatPumpSnapshotTests
{
    private const string HeatPumpModel = "HeatPumpModel";
    private const string ErrorCodeH15 = "H15";
    private const string DatabaseErrorMessage = "Database error";
    private const decimal DefaultPumpFlowLitersPerMinute = 10.0m;
    private const decimal TestPumpFlowLitersPerMinute = 12.5m;
    private const decimal DefaultOutsideTemperatureCelsius = 10.0m;
    private const decimal NegativeOutsideTemperatureCelsius = -5.5m;
    private const decimal DefaultChOutletCelsius = 35.0m;
    private const decimal DefaultChInletCelsius = 30.0m;
    private const decimal DefaultChTargetCelsius = 40.0m;
    private const decimal DefaultDhwActualCelsius = 45.0m;
    private const decimal DefaultDhwTargetCelsius = 50.0m;
    private const decimal TestDhwActualCelsius = 48.0m;
    private const decimal DefaultCompressorFrequencyHertz = 50.0m;
    private const decimal TestCompressorFrequencyHertz = 55.0m;
    private const decimal TestCompressorFrequencyHertz60 = 60.0m;
    private const decimal TestPumpFlowLitersPerMinute15 = 15.0m;
    private const decimal TestOutsideTemperatureCelsius = 5.0m;
    private const decimal TestOperationsHours = 1234.5m;
    private const int TestOperationsStarts = 567;
    private const int TestPowerProductionWatts = 3500;
    private const int TestPowerConsumptionWatts = 1000;
    private const int TestDhwProductionWatts = 2000;
    private const int TestDhwConsumptionWatts = 500;
    private const int ZeroWatts = 0;

    private readonly IHeatPumpSnapshotRepository _repository;
    private readonly SaveHeatPumpSnapshot.Handler _handler;

    public SaveHeatPumpSnapshotTests()
    {
        _repository = Substitute.For<IHeatPumpSnapshotRepository>();
        _handler = new SaveHeatPumpSnapshot.Handler(_repository);
    }

    #region Saving Snapshot from HeatPump Aggregate

    [Fact]
    public async Task HandleAsync_GivenHeatPump_WhenHandleAsync_ThenSnapshotSavedInRepository()
    {
        // Given
        var heatPump = CreateTestHeatPump();
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _repository.Received(1).SaveSnapshotAsync(
            Arg.Any<HeatPumpSnapshot>(),
            Arg.Any<CancellationToken>());

        capturedSnapshot.Should().NotBeNull();
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPump_WhenHandleAsync_ThenSnapshotContainsCorrectHeatPumpId()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var heatPump = CreateTestHeatPump(heatPumpId);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.HeatPumpId.Should().Be(heatPumpId);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPump_WhenHandleAsync_ThenSnapshotContainsValidTimestamp()
    {
        // Given
        var heatPump = CreateTestHeatPump();
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        var beforeExecution = DateTimeOffset.UtcNow;
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);
        var afterExecution = DateTimeOffset.UtcNow;

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.Timestamp.Should().BeOnOrAfter(beforeExecution);
        capturedSnapshot.Timestamp.Should().BeOnOrBefore(afterExecution);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithIsOnTrue_WhenHandleAsync_ThenSnapshotContainsIsOnTrue()
    {
        // Given
        var heatPump = CreateTestHeatPump(isOn: true);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.IsOn.Should().BeTrue();
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithIsOnFalse_WhenHandleAsync_ThenSnapshotContainsIsOnFalse()
    {
        // Given
        var heatPump = CreateTestHeatPump(isOn: false);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.IsOn.Should().BeFalse();
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithOperatingMode_WhenHandleAsync_ThenSnapshotContainsSameOperatingMode()
    {
        // Given
        var operatingMode = OperatingMode.HeatDhw;
        var heatPump = CreateTestHeatPump(operatingMode: operatingMode);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.OperatingMode.Should().Be(operatingMode);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithPumpFlow_WhenHandleAsync_ThenSnapshotContainsSamePumpFlow()
    {
        // Given
        var pumpFlow = PumpFlow.FromLitersPerMinute(TestPumpFlowLitersPerMinute);
        var heatPump = CreateTestHeatPump(pumpFlow: pumpFlow);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.PumpFlow.Should().Be(pumpFlow);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithOutsideTemperature_WhenHandleAsync_ThenSnapshotContainsSameOutsideTemperature()
    {
        // Given
        var outsideTemperature = OutsideTemperature.FromCelsius(NegativeOutsideTemperatureCelsius);
        var heatPump = CreateTestHeatPump(outsideTemperature: outsideTemperature);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.OutsideTemperature.Should().Be(outsideTemperature);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithCentralHeatingData_WhenHandleAsync_ThenSnapshotContainsSameCentralHeatingData()
    {
        // Given
        var centralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(DefaultChOutletCelsius),
            WaterTemperature.FromCelsius(DefaultChInletCelsius),
            WaterTemperature.FromCelsius(DefaultChTargetCelsius));
        var heatPump = CreateTestHeatPump(centralHeating: centralHeating);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.CentralHeating.Should().Be(centralHeating);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithDomesticHotWaterData_WhenHandleAsync_ThenSnapshotContainsSameDomesticHotWaterData()
    {
        // Given
        var domesticHotWater = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(TestDhwActualCelsius),
            DhwTemperature.FromCelsius(DefaultDhwTargetCelsius));
        var heatPump = CreateTestHeatPump(domesticHotWater: domesticHotWater);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.DomesticHotWater.Should().Be(domesticHotWater);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithCompressorFrequency_WhenHandleAsync_ThenSnapshotContainsSameCompressorFrequency()
    {
        // Given
        var compressorFrequency = Frequency.FromHertz(TestCompressorFrequencyHertz);
        var heatPump = CreateTestHeatPump(compressorFrequency: compressorFrequency);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.CompressorFrequency.Should().Be(compressorFrequency);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithPowerData_WhenHandleAsync_ThenSnapshotContainsSamePowerData()
    {
        // Given
        var powerData = new PowerData(
            Power.FromWatts(TestPowerProductionWatts),
            Power.FromWatts(TestPowerConsumptionWatts),
            Power.FromWatts(ZeroWatts),
            Power.FromWatts(ZeroWatts),
            Power.FromWatts(TestDhwProductionWatts),
            Power.FromWatts(TestDhwConsumptionWatts));
        var heatPump = CreateTestHeatPump(power: powerData);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.Power.Should().Be(powerData);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithOperationsData_WhenHandleAsync_ThenSnapshotContainsSameOperationsData()
    {
        // Given
        var operationsData = new OperationsData(TestOperationsHours, TestOperationsStarts);
        var heatPump = CreateTestHeatPump(operations: operationsData);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.Operations.Should().Be(operationsData);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithDefrostActive_WhenHandleAsync_ThenSnapshotContainsSameDefrostData()
    {
        // Given
        var defrostData = DefrostData.Active;
        var heatPump = CreateTestHeatPump(defrost: defrostData);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.Defrost.Should().Be(defrostData);
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPumpWithErrorCode_WhenHandleAsync_ThenSnapshotContainsSameErrorCode()
    {
        // Given
        var errorCode = ErrorCode.From(ErrorCodeH15);
        var heatPump = CreateTestHeatPump(errorCode: errorCode);
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        HeatPumpSnapshot? capturedSnapshot = null;

        _repository
            .SaveSnapshotAsync(Arg.Do<HeatPumpSnapshot>(s => capturedSnapshot = s), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When
        await _handler.HandleAsync(command);

        // Then
        capturedSnapshot.Should().NotBeNull();
        capturedSnapshot!.ErrorCode.Should().Be(errorCode);
    }

    #endregion

    #region Repository Interaction

    [Fact]
    public async Task HandleAsync_GivenHeatPump_WhenHandleAsync_ThenSaveSnapshotAsyncIsCalledWithCorrectObject()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var isOn = true;
        var operatingMode = OperatingMode.HeatDhw;
        var pumpFlow = PumpFlow.FromLitersPerMinute(TestPumpFlowLitersPerMinute15);
        var outsideTemperature = OutsideTemperature.FromCelsius(TestOutsideTemperatureCelsius);
        var centralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(DefaultChOutletCelsius),
            WaterTemperature.FromCelsius(DefaultChInletCelsius),
            WaterTemperature.FromCelsius(DefaultChTargetCelsius));
        var domesticHotWater = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(DefaultDhwActualCelsius),
            DhwTemperature.FromCelsius(DefaultDhwTargetCelsius));
        var compressorFrequency = Frequency.FromHertz(TestCompressorFrequencyHertz60);
        var power = PowerData.Zero;
        var operations = OperationsData.Zero;
        var defrost = DefrostData.Inactive;
        var errorCode = ErrorCode.None;

        var heatPump = CreateTestHeatPump(
            heatPumpId,
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

        var command = new SaveHeatPumpSnapshot.Command(heatPump);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _repository.Received(1).SaveSnapshotAsync(
            Arg.Is<HeatPumpSnapshot>(s =>
                s.HeatPumpId == heatPumpId &&
                s.IsOn == isOn &&
                s.OperatingMode == operatingMode &&
                s.PumpFlow == pumpFlow &&
                s.OutsideTemperature == outsideTemperature &&
                s.CentralHeating == centralHeating &&
                s.DomesticHotWater == domesticHotWater &&
                s.CompressorFrequency == compressorFrequency &&
                s.Power == power &&
                s.Operations == operations &&
                s.Defrost == defrost &&
                s.ErrorCode == errorCode),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_GivenHeatPump_WhenHandleAsync_ThenCancellationTokenIsPassed()
    {
        // Given
        var heatPump = CreateTestHeatPump();
        var command = new SaveHeatPumpSnapshot.Command(heatPump);
        using var cts = new CancellationTokenSource();
        var cancellationToken = cts.Token;

        // When
        await _handler.HandleAsync(command, cancellationToken);

        // Then
        await _repository.Received(1).SaveSnapshotAsync(
            Arg.Any<HeatPumpSnapshot>(),
            cancellationToken);
    }

    #endregion

    #region Error Handling

    [Fact]
    public async Task HandleAsync_WhenRepositoryThrows_ThenExceptionIsPropagated()
    {
        // Given
        var heatPump = CreateTestHeatPump();
        var command = new SaveHeatPumpSnapshot.Command(heatPump);

        _repository
            .SaveSnapshotAsync(Arg.Any<HeatPumpSnapshot>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(DatabaseErrorMessage));

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(DatabaseErrorMessage);
    }

    #endregion

    #region Helper Methods

    private static HeatPump CreateTestHeatPump(
        HeatPumpId? heatPumpId = null,
        bool isOn = true,
        OperatingMode operatingMode = OperatingMode.HeatDhw,
        PumpFlow? pumpFlow = null,
        OutsideTemperature? outsideTemperature = null,
        CentralHeatingData? centralHeating = null,
        DomesticHotWaterData? domesticHotWater = null,
        Frequency? compressorFrequency = null,
        PowerData? power = null,
        OperationsData? operations = null,
        DefrostData? defrost = null,
        ErrorCode? errorCode = null)
    {
        return HeatPump.Reconstitute(
            heatPumpId ?? HeatPumpId.NewId(),
            HeatPumpModel,
            DateTimeOffset.UtcNow,
            isOn,
            operatingMode,
            pumpFlow ?? PumpFlow.FromLitersPerMinute(DefaultPumpFlowLitersPerMinute),
            outsideTemperature ?? OutsideTemperature.FromCelsius(DefaultOutsideTemperatureCelsius),
            centralHeating ?? new CentralHeatingData(
                WaterTemperature.FromCelsius(DefaultChOutletCelsius),
                WaterTemperature.FromCelsius(DefaultChInletCelsius),
                WaterTemperature.FromCelsius(DefaultChTargetCelsius)),
            domesticHotWater ?? new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DefaultDhwActualCelsius),
                DhwTemperature.FromCelsius(DefaultDhwTargetCelsius)),
            compressorFrequency ?? Frequency.FromHertz(DefaultCompressorFrequencyHertz),
            power ?? PowerData.Zero,
            operations ?? OperationsData.Zero,
            defrost ?? DefrostData.Inactive,
            errorCode ?? ErrorCode.None);
    }

    #endregion
}
