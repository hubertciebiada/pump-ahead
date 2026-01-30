using FluentAssertions;
using NSubstitute;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.SyncHeatPumpState;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.ProcessModel.Tests.Commands;

public class SyncHeatPumpStateTests
{
    private const string HeatPumpModel = "WH-MDC09J3E5";
    private const string DefaultErrorCode = "H00";
    private const string ErrorCodeH62 = "H62";
    private const decimal DefaultPumpFlowLitersPerMinute = 12.5m;
    private const decimal DefaultOutsideTemperatureCelsius = 5.0m;
    private const decimal DefaultChInletCelsius = 35.0m;
    private const decimal DefaultChOutletCelsius = 40.0m;
    private const decimal DefaultChTargetCelsius = 42.0m;
    private const decimal DefaultDhwActualCelsius = 48.0m;
    private const decimal DefaultDhwTargetCelsius = 50.0m;
    private const decimal DefaultCompressorFrequencyHertz = 45.0m;
    private const decimal DefaultHeatProductionWatts = 5000m;
    private const decimal DefaultHeatConsumptionWatts = 1200m;
    private const decimal DefaultCoolProdWatts = 0m;
    private const decimal DefaultCoolConsWatts = 0m;
    private const decimal DefaultDhwProdWatts = 3000m;
    private const decimal DefaultDhwConsWatts = 800m;
    private const decimal DefaultCompressorHours = 1500.5m;
    private const int DefaultCompressorStarts = 2500;
    private const decimal ExistingPumpFlowLitersPerMinute = 10.0m;
    private const decimal ExistingOutsideTemperatureCelsius = 8.0m;
    private const decimal ExistingChInletCelsius = 30.0m;
    private const decimal ExistingChOutletCelsius = 35.0m;
    private const decimal ExistingChTargetCelsius = 40.0m;
    private const decimal ExistingDhwActualCelsius = 45.0m;
    private const decimal ExistingCompressorFrequencyHertz = 30.0m;
    private const decimal ExistingHeatProdWatts = 3000m;
    private const decimal ExistingHeatConsWatts = 900m;
    private const decimal ExistingDhwProdWatts = 2000m;
    private const decimal ExistingDhwConsWatts = 600m;
    private const decimal ExistingCompressorHours = 1400.0m;
    private const int ExistingCompressorStarts = 2400;

    private readonly IHeatPumpRepository _heatPumpRepository;
    private readonly IHeatPumpNotificationService _notificationService;
    private readonly SyncHeatPumpState.Handler _handler;

    public SyncHeatPumpStateTests()
    {
        _heatPumpRepository = Substitute.For<IHeatPumpRepository>();
        _notificationService = Substitute.For<IHeatPumpNotificationService>();
        _handler = new SyncHeatPumpState.Handler(_heatPumpRepository, _notificationService);
    }

    #region Test Data Helpers

    private static HeishaMonData CreateHeishaMonData(
        bool isOn = true,
        OperatingMode operatingMode = OperatingMode.HeatDhw,
        decimal pumpFlow = DefaultPumpFlowLitersPerMinute,
        decimal outsideTemp = DefaultOutsideTemperatureCelsius,
        decimal chInlet = DefaultChInletCelsius,
        decimal chOutlet = DefaultChOutletCelsius,
        decimal chTarget = DefaultChTargetCelsius,
        decimal dhwActual = DefaultDhwActualCelsius,
        decimal dhwTarget = DefaultDhwTargetCelsius,
        decimal compressorFreq = DefaultCompressorFrequencyHertz,
        decimal heatProdWatts = DefaultHeatProductionWatts,
        decimal heatConsWatts = DefaultHeatConsumptionWatts,
        decimal coolProdWatts = DefaultCoolProdWatts,
        decimal coolConsWatts = DefaultCoolConsWatts,
        decimal dhwProdWatts = DefaultDhwProdWatts,
        decimal dhwConsWatts = DefaultDhwConsWatts,
        decimal compressorHours = DefaultCompressorHours,
        int compressorStarts = DefaultCompressorStarts,
        bool isDefrosting = false,
        string errorCode = DefaultErrorCode)
    {
        return new HeishaMonData(
            isOn,
            operatingMode,
            pumpFlow,
            outsideTemp,
            chInlet,
            chOutlet,
            chTarget,
            dhwActual,
            dhwTarget,
            compressorFreq,
            heatProdWatts,
            heatConsWatts,
            coolProdWatts,
            coolConsWatts,
            dhwProdWatts,
            dhwConsWatts,
            compressorHours,
            compressorStarts,
            isDefrosting,
            errorCode);
    }

    private static HeatPump CreateExistingHeatPump(HeatPumpId id)
    {
        return HeatPump.Reconstitute(
            id,
            HeatPumpModel,
            DateTimeOffset.UtcNow.AddMinutes(-5),
            isOn: false,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(ExistingPumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(ExistingOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(ExistingChInletCelsius),
                WaterTemperature.FromCelsius(ExistingChOutletCelsius),
                WaterTemperature.FromCelsius(ExistingChTargetCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(ExistingDhwActualCelsius),
                DhwTemperature.FromCelsius(ExistingDhwActualCelsius + 3.0m)),
            Frequency.FromHertz(ExistingCompressorFrequencyHertz),
            new PowerData(
                Power.FromWatts(ExistingHeatProdWatts),
                Power.FromWatts(ExistingHeatConsWatts),
                Power.FromWatts(DefaultCoolProdWatts),
                Power.FromWatts(DefaultCoolConsWatts),
                Power.FromWatts(ExistingDhwProdWatts),
                Power.FromWatts(ExistingDhwConsWatts)),
            new OperationsData(ExistingCompressorHours, ExistingCompressorStarts),
            new DefrostData(false),
            ErrorCode.From(DefaultErrorCode));
    }

    #endregion

    #region Given: HeatPump does not exist

    [Fact]
    public async Task GivenHeatPumpDoesNotExist_WhenHandleAsync_ThenThrowsInvalidOperationException()
    {
        // Given: HeatPump does not exist in repository
        var heatPumpId = HeatPumpId.NewId();
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns((HeatPump?)null);

        // When: HandleAsync is called
        var act = () => _handler.HandleAsync(command);

        // Then: InvalidOperationException is thrown
        await act.Should()
            .ThrowAsync<InvalidOperationException>()
            .WithMessage($"HeatPump '{heatPumpId.Value}' does not exist.");
    }

    [Fact]
    public async Task GivenHeatPumpDoesNotExist_WhenHandleAsync_ThenRepositorySaveIsNotCalled()
    {
        // Given: HeatPump does not exist
        var heatPumpId = HeatPumpId.NewId();
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns((HeatPump?)null);

        // When: HandleAsync is called (and throws)
        try
        {
            await _handler.HandleAsync(command);
        }
        catch (InvalidOperationException)
        {
            // Expected
        }

        // Then: SaveAsync is never called
        await _heatPumpRepository.DidNotReceive()
            .SaveAsync(Arg.Any<HeatPump>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task GivenHeatPumpDoesNotExist_WhenHandleAsync_ThenNotificationIsNotSent()
    {
        // Given: HeatPump does not exist
        var heatPumpId = HeatPumpId.NewId();
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns((HeatPump?)null);

        // When: HandleAsync is called (and throws)
        try
        {
            await _handler.HandleAsync(command);
        }
        catch (InvalidOperationException)
        {
            // Expected
        }

        // Then: Notification service is never called
        await _notificationService.DidNotReceive().NotifyHeatPumpUpdatedAsync();
    }

    #endregion

    #region Given: Existing HeatPump

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenHeatPumpIsUpdatedAndSaved()
    {
        // Given: Existing HeatPump in repository
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(
            isOn: true,
            operatingMode: OperatingMode.HeatDhw,
            pumpFlow: 15.0m,
            outsideTemp: 3.0m);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Repository.SaveAsync is called with updated HeatPump
        await _heatPumpRepository.Received(1)
            .SaveAsync(Arg.Is<HeatPump>(hp => hp.Id == heatPumpId), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenHeatPumpStateIsUpdatedCorrectly()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(
            isOn: true,
            operatingMode: OperatingMode.CoolDhw,
            pumpFlow: 18.5m,
            outsideTemp: 28.0m,
            compressorFreq: 60.0m);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: HeatPump state is updated with new values
        existingHeatPump.IsOn.Should().BeTrue();
        existingHeatPump.OperatingMode.Should().Be(OperatingMode.CoolDhw);
        existingHeatPump.PumpFlow.Should().Be(PumpFlow.FromLitersPerMinute(18.5m));
        existingHeatPump.OutsideTemperature.Should().Be(OutsideTemperature.FromCelsius(28.0m));
        existingHeatPump.CompressorFrequency.Should().Be(Frequency.FromHertz(60.0m));
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenCentralHeatingDataIsUpdated()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(
            chInlet: 38.0m,
            chOutlet: 45.0m,
            chTarget: 48.0m);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Central Heating data is updated
        existingHeatPump.CentralHeating.InletTemperature.Should().Be(WaterTemperature.FromCelsius(38.0m));
        existingHeatPump.CentralHeating.OutletTemperature.Should().Be(WaterTemperature.FromCelsius(45.0m));
        existingHeatPump.CentralHeating.TargetTemperature.Should().Be(WaterTemperature.FromCelsius(48.0m));
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenDomesticHotWaterDataIsUpdated()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(
            dhwActual: 52.0m,
            dhwTarget: 55.0m);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: DHW data is updated
        existingHeatPump.DomesticHotWater.ActualTemperature.Should().Be(DhwTemperature.FromCelsius(52.0m));
        existingHeatPump.DomesticHotWater.TargetTemperature.Should().Be(DhwTemperature.FromCelsius(55.0m));
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenPowerDataIsUpdated()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(
            heatProdWatts: 6000m,
            heatConsWatts: 1500m,
            coolProdWatts: 100m,
            coolConsWatts: 50m,
            dhwProdWatts: 4000m,
            dhwConsWatts: 1000m);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Power data is updated
        existingHeatPump.Power.HeatProduction.Should().Be(Power.FromWatts(6000m));
        existingHeatPump.Power.HeatConsumption.Should().Be(Power.FromWatts(1500m));
        existingHeatPump.Power.CoolProduction.Should().Be(Power.FromWatts(100m));
        existingHeatPump.Power.CoolConsumption.Should().Be(Power.FromWatts(50m));
        existingHeatPump.Power.DhwProduction.Should().Be(Power.FromWatts(4000m));
        existingHeatPump.Power.DhwConsumption.Should().Be(Power.FromWatts(1000m));
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenOperationsDataIsUpdated()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(
            compressorHours: 1600.5m,
            compressorStarts: 2600);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Operations data is updated
        existingHeatPump.Operations.CompressorHours.Should().Be(1600.5m);
        existingHeatPump.Operations.CompressorStarts.Should().Be(2600);
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenDefrostDataIsUpdated()
    {
        // Given: Existing HeatPump not defrosting
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(isDefrosting: true);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Defrost data is updated
        existingHeatPump.Defrost.IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenErrorCodeIsUpdated()
    {
        // Given: Existing HeatPump with no error
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var newData = CreateHeishaMonData(errorCode: ErrorCodeH62);
        var command = new SyncHeatPumpState.Command(newData, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Error code is updated
        existingHeatPump.ErrorCode.Should().Be(ErrorCode.From(ErrorCodeH62));
    }

    #endregion

    #region SignalR Notification

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenSignalRNotificationIsSent()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: NotifyHeatPumpUpdatedAsync is called exactly once
        await _notificationService.Received(1).NotifyHeatPumpUpdatedAsync();
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenNotificationIsSentAfterSave()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        var callOrder = new List<string>();
        _heatPumpRepository
            .SaveAsync(Arg.Any<HeatPump>(), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask)
            .AndDoes(_ => callOrder.Add("Save"));
        _notificationService
            .NotifyHeatPumpUpdatedAsync()
            .Returns(Task.CompletedTask)
            .AndDoes(_ => callOrder.Add("Notify"));

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: Save is called before Notification
        callOrder.Should().ContainInOrder("Save", "Notify");
    }

    #endregion

    #region Repository.SaveAsync

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenRepositorySaveAsyncIsCalledOnce()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: SaveAsync is called exactly once
        await _heatPumpRepository.Received(1)
            .SaveAsync(Arg.Any<HeatPump>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenRepositorySaveAsyncReceivesCorrectHeatPump()
    {
        // Given: Existing HeatPump
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        HeatPump? savedHeatPump = null;
        _heatPumpRepository
            .SaveAsync(Arg.Do<HeatPump>(hp => savedHeatPump = hp), Arg.Any<CancellationToken>())
            .Returns(Task.CompletedTask);

        // When: HandleAsync is called
        await _handler.HandleAsync(command);

        // Then: The same HeatPump instance (updated) is saved
        savedHeatPump.Should().BeSameAs(existingHeatPump);
    }

    [Fact]
    public async Task GivenExistingHeatPump_WhenHandleAsync_ThenCancellationTokenIsPassedToSave()
    {
        // Given: Existing HeatPump and a CancellationToken
        var heatPumpId = HeatPumpId.NewId();
        var existingHeatPump = CreateExistingHeatPump(heatPumpId);
        var data = CreateHeishaMonData();
        var command = new SyncHeatPumpState.Command(data, heatPumpId);
        using var cts = new CancellationTokenSource();
        var token = cts.Token;

        _heatPumpRepository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(existingHeatPump);

        // When: HandleAsync is called with CancellationToken
        await _handler.HandleAsync(command, token);

        // Then: SaveAsync receives the same CancellationToken
        await _heatPumpRepository.Received(1)
            .SaveAsync(Arg.Any<HeatPump>(), token);
    }

    #endregion
}
