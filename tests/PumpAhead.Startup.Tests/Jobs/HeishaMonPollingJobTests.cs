using System.Reflection;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Startup.Configuration;
using PumpAhead.Startup.Jobs;
using PumpAhead.UseCases.Commands.SaveHeatPumpSnapshot;
using PumpAhead.UseCases.Commands.SyncHeatPumpState;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;
using Quartz;

namespace PumpAhead.Startup.Tests.Jobs;

public class HeishaMonPollingJobTests : IDisposable
{
    private const int DefaultSnapshotIntervalSeconds = 300;
    private const string DefaultHeishaMonAddress = "http://heishamon.local";
    private const string DefaultHeatPumpName = "Test Aquarea";
    private const string DefaultErrorCode = "H00";
    private const string ConsecutiveFailuresFieldName = "_consecutiveFailures";
    private const string LastSnapshotTimeFieldName = "_lastSnapshotTime";

    private const decimal PumpFlowLitersPerMinute = 12.5m;
    private const decimal PumpFlowForReconstitute = 12.0m;
    private const decimal OutsideTemperatureCelsius = 5.0m;
    private const decimal ChInletTemperatureCelsius = 30.0m;
    private const decimal ChOutletTemperatureCelsius = 35.0m;
    private const decimal ChTargetTemperatureCelsius = 40.0m;
    private const decimal DhwActualTemperatureCelsius = 45.0m;
    private const decimal DhwTargetTemperatureCelsius = 50.0m;
    private const decimal CompressorFrequencyHertz = 60.0m;
    private const decimal HeatPowerProductionWatts = 5000m;
    private const decimal HeatPowerConsumptionWatts = 1500m;
    private const decimal ZeroPowerWatts = 0m;
    private const decimal DhwPowerProductionWatts = 3000m;
    private const decimal DhwPowerConsumptionWatts = 1000m;
    private const decimal CompressorOperatingHours = 1234.5m;
    private const int CompressorStartCount = 456;

    private const int ZeroFailures = 0;
    private const int OneFailure = 1;
    private const int ThreeFailures = 3;
    private const int FourFailures = 4;
    private const int FiveFailures = 5;
    private const int NineFailures = 9;
    private const int TenFailures = 10;
    private const int NineteenFailures = 19;
    private const int TwentyFailures = 20;
    private const int NotificationThreshold = 5;

    private const int RecentSnapshotOffsetSeconds = -10;
    private const int SnapshotIntervalOffsetSeconds = -300;
    private const int HeatPumpCreatedMinutesAgo = -5;

    private const string ConnectionRefusedMessage = "Connection refused";
    private const string NetworkErrorMessage = "Network error";
    private const string DatabaseErrorMessage = "Database error";
    private const string ConnectionTimeoutMessage = "Connection timeout";
    private const string SyncFailedMessage = "Sync failed";

    private readonly IHeishaMonProvider _heishaMonProvider;
    private readonly IHeatPumpRepository _heatPumpRepository;
    private readonly ICommandHandler<SyncHeatPumpState.Command> _syncHandler;
    private readonly ICommandHandler<SaveHeatPumpSnapshot.Command> _snapshotHandler;
    private readonly IHeatPumpNotificationService _notificationService;
    private readonly IOptions<HeishaMonSettings> _settings;
    private readonly ILogger<HeishaMonPollingJob> _logger;
    private readonly IJobExecutionContext _jobContext;
    private readonly Guid _heatPumpGuid;

    public HeishaMonPollingJobTests()
    {
        // Reset static fields before each test
        ResetStaticFields();

        _heishaMonProvider = Substitute.For<IHeishaMonProvider>();
        _heatPumpRepository = Substitute.For<IHeatPumpRepository>();
        _syncHandler = Substitute.For<ICommandHandler<SyncHeatPumpState.Command>>();
        _snapshotHandler = Substitute.For<ICommandHandler<SaveHeatPumpSnapshot.Command>>();
        _notificationService = Substitute.For<IHeatPumpNotificationService>();
        _logger = Substitute.For<ILogger<HeishaMonPollingJob>>();
        _jobContext = Substitute.For<IJobExecutionContext>();
        _jobContext.CancellationToken.Returns(CancellationToken.None);

        _heatPumpGuid = Guid.NewGuid();
        _settings = Options.Create(new HeishaMonSettings
        {
            HeatPumpId = _heatPumpGuid,
            SnapshotIntervalSeconds = DefaultSnapshotIntervalSeconds,
            Address = DefaultHeishaMonAddress
        });
    }

    public void Dispose()
    {
        // Reset static fields after each test to ensure isolation
        ResetStaticFields();
    }

    private static void ResetStaticFields()
    {
        // Use reflection to reset static fields since they are private
        var jobType = typeof(HeishaMonPollingJob);

        var failuresField = jobType.GetField(ConsecutiveFailuresFieldName,
            BindingFlags.Static | BindingFlags.NonPublic);
        failuresField?.SetValue(null, ZeroFailures);

        var snapshotTimeField = jobType.GetField(LastSnapshotTimeFieldName,
            BindingFlags.Static | BindingFlags.NonPublic);
        snapshotTimeField?.SetValue(null, DateTimeOffset.MinValue);
    }

    private static int GetConsecutiveFailures()
    {
        var failuresField = typeof(HeishaMonPollingJob).GetField(ConsecutiveFailuresFieldName,
            BindingFlags.Static | BindingFlags.NonPublic);
        return (int)(failuresField?.GetValue(null) ?? ZeroFailures);
    }

    private static void SetConsecutiveFailures(int value)
    {
        var failuresField = typeof(HeishaMonPollingJob).GetField(ConsecutiveFailuresFieldName,
            BindingFlags.Static | BindingFlags.NonPublic);
        failuresField?.SetValue(null, value);
    }

    private static void SetLastSnapshotTime(DateTimeOffset value)
    {
        var snapshotTimeField = typeof(HeishaMonPollingJob).GetField(LastSnapshotTimeFieldName,
            BindingFlags.Static | BindingFlags.NonPublic);
        snapshotTimeField?.SetValue(null, value);
    }

    private HeishaMonPollingJob CreateSut() => new(
        _heishaMonProvider,
        _heatPumpRepository,
        _syncHandler,
        _snapshotHandler,
        _notificationService,
        _settings,
        _logger);

    private static HeishaMonData CreateHeishaMonData() => new(
        IsOn: true,
        OperatingMode: OperatingMode.HeatDhw,
        PumpFlowLitersPerMinute: PumpFlowLitersPerMinute,
        OutsideTemperatureCelsius: OutsideTemperatureCelsius,
        CH_InletTemperatureCelsius: ChInletTemperatureCelsius,
        CH_OutletTemperatureCelsius: ChOutletTemperatureCelsius,
        CH_TargetTemperatureCelsius: ChTargetTemperatureCelsius,
        DHW_ActualTemperatureCelsius: DhwActualTemperatureCelsius,
        DHW_TargetTemperatureCelsius: DhwTargetTemperatureCelsius,
        CompressorFrequencyHertz: CompressorFrequencyHertz,
        HeatPowerProductionWatts: HeatPowerProductionWatts,
        HeatPowerConsumptionWatts: HeatPowerConsumptionWatts,
        CoolPowerProductionWatts: ZeroPowerWatts,
        CoolPowerConsumptionWatts: ZeroPowerWatts,
        DhwPowerProductionWatts: DhwPowerProductionWatts,
        DhwPowerConsumptionWatts: DhwPowerConsumptionWatts,
        CompressorOperatingHours: CompressorOperatingHours,
        CompressorStartCount: CompressorStartCount,
        IsDefrosting: false,
        ErrorCode: DefaultErrorCode);

    private HeatPump CreateHeatPump() => HeatPump.Reconstitute(
        HeatPumpId.From(_heatPumpGuid),
        DefaultHeatPumpName,
        DateTimeOffset.UtcNow.AddMinutes(HeatPumpCreatedMinutesAgo),
        true,
        OperatingMode.HeatDhw,
        PumpFlow.FromLitersPerMinute(PumpFlowForReconstitute),
        OutsideTemperature.FromCelsius(OutsideTemperatureCelsius),
        new CentralHeatingData(
            WaterTemperature.FromCelsius(ChInletTemperatureCelsius),
            WaterTemperature.FromCelsius(ChOutletTemperatureCelsius),
            WaterTemperature.FromCelsius(ChTargetTemperatureCelsius)),
        new DomesticHotWaterData(
            DhwTemperature.FromCelsius(DhwActualTemperatureCelsius),
            DhwTemperature.FromCelsius(DhwTargetTemperatureCelsius)),
        Frequency.FromHertz(CompressorFrequencyHertz),
        new PowerData(
            Power.FromWatts(HeatPowerProductionWatts),
            Power.FromWatts(HeatPowerConsumptionWatts),
            Power.FromWatts(ZeroPowerWatts),
            Power.FromWatts(ZeroPowerWatts),
            Power.FromWatts(DhwPowerProductionWatts),
            Power.FromWatts(DhwPowerConsumptionWatts)),
        new OperationsData(CompressorOperatingHours, CompressorStartCount),
        new DefrostData(false),
        ErrorCode.From(DefaultErrorCode));

    #region Execute - Provider Invocation

    [Fact]
    public async Task Execute_GivenJobContext_WhenInvoked_ThenCallsFetchDataAsync()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        // When
        await sut.Execute(_jobContext);

        // Then
        await _heishaMonProvider.Received(1).FetchDataAsync(_jobContext.CancellationToken);
    }

    [Fact]
    public async Task Execute_GivenCancellationToken_WhenInvoked_ThenPassesCancellationTokenToProvider()
    {
        // Given
        var cts = new CancellationTokenSource();
        _jobContext.CancellationToken.Returns(cts.Token);
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        // When
        await sut.Execute(_jobContext);

        // Then
        await _heishaMonProvider.Received(1).FetchDataAsync(cts.Token);
    }

    #endregion

    #region Execute - SyncHandler Invocation

    [Fact]
    public async Task Execute_GivenDataAvailable_WhenInvoked_ThenCallsSyncHandler()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        // When
        await sut.Execute(_jobContext);

        // Then
        await _syncHandler.Received(1).HandleAsync(
            Arg.Is<SyncHeatPumpState.Command>(cmd =>
                cmd.Data == data &&
                cmd.HeatPumpId == HeatPumpId.From(_heatPumpGuid)),
            _jobContext.CancellationToken);
    }

    [Fact]
    public async Task Execute_GivenDataNull_WhenInvoked_ThenDoesNotCallSyncHandler()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        // When
        await sut.Execute(_jobContext);

        // Then
        await _syncHandler.DidNotReceive().HandleAsync(
            Arg.Any<SyncHeatPumpState.Command>(),
            Arg.Any<CancellationToken>());
    }

    #endregion

    #region Execute - Snapshot Saving

    [Fact]
    public async Task Execute_GivenSnapshotIntervalPassed_WhenInvoked_ThenSavesSnapshot()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        var heatPump = CreateHeatPump();

        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _heatPumpRepository.GetByIdAsync(
                Arg.Any<HeatPumpId>(), Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // _lastSnapshotTime is DateTimeOffset.MinValue by default, so interval has passed

        // When
        await sut.Execute(_jobContext);

        // Then
        await _snapshotHandler.Received(1).HandleAsync(
            Arg.Is<SaveHeatPumpSnapshot.Command>(cmd => cmd.HeatPump == heatPump),
            _jobContext.CancellationToken);
    }

    [Fact]
    public async Task Execute_GivenSnapshotIntervalNotPassed_WhenInvoked_ThenDoesNotSaveSnapshot()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();

        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        // Set last snapshot time to recent (within interval)
        SetLastSnapshotTime(DateTimeOffset.UtcNow.AddSeconds(RecentSnapshotOffsetSeconds));

        // When
        await sut.Execute(_jobContext);

        // Then
        await _snapshotHandler.DidNotReceive().HandleAsync(
            Arg.Any<SaveHeatPumpSnapshot.Command>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Execute_GivenSnapshotIntervalExactlyPassed_WhenInvoked_ThenSavesSnapshot()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        var heatPump = CreateHeatPump();

        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _heatPumpRepository.GetByIdAsync(
                Arg.Any<HeatPumpId>(), Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // Set last snapshot time exactly at interval boundary
        SetLastSnapshotTime(DateTimeOffset.UtcNow.AddSeconds(SnapshotIntervalOffsetSeconds));

        // When
        await sut.Execute(_jobContext);

        // Then
        await _snapshotHandler.Received(1).HandleAsync(
            Arg.Any<SaveHeatPumpSnapshot.Command>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Execute_GivenHeatPumpNotFound_WhenSnapshotTime_ThenDoesNotSaveSnapshot()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();

        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _heatPumpRepository.GetByIdAsync(
                Arg.Any<HeatPumpId>(), Arg.Any<CancellationToken>())
            .Returns((HeatPump?)null);

        // When
        await sut.Execute(_jobContext);

        // Then
        await _snapshotHandler.DidNotReceive().HandleAsync(
            Arg.Any<SaveHeatPumpSnapshot.Command>(),
            Arg.Any<CancellationToken>());
    }

    #endregion

    #region Execute - Failure Counter

    [Fact]
    public async Task Execute_GivenProviderReturnsNull_WhenInvoked_ThenIncrementsFailureCounter()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        // When
        await sut.Execute(_jobContext);

        // Then
        GetConsecutiveFailures().Should().Be(OneFailure);
    }

    [Fact]
    public async Task Execute_GivenProviderThrowsException_WhenInvoked_ThenIncrementsFailureCounter()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .ThrowsAsync(new HttpRequestException(ConnectionRefusedMessage));

        // When
        await sut.Execute(_jobContext);

        // Then
        GetConsecutiveFailures().Should().Be(OneFailure);
    }

    [Fact]
    public async Task Execute_GivenMultipleFailures_WhenInvoked_ThenAccumulatesFailureCounter()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        // When
        await sut.Execute(_jobContext);
        await sut.Execute(_jobContext);
        await sut.Execute(_jobContext);

        // Then
        GetConsecutiveFailures().Should().Be(ThreeFailures);
    }

    [Fact]
    public async Task Execute_GivenSyncHandlerThrows_WhenInvoked_ThenIncrementsFailureCounter()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _syncHandler.HandleAsync(Arg.Any<SyncHeatPumpState.Command>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(SyncFailedMessage));

        // When
        await sut.Execute(_jobContext);

        // Then
        GetConsecutiveFailures().Should().Be(OneFailure);
    }

    #endregion

    #region Execute - Notification after 5 Failures

    [Fact]
    public async Task Execute_GivenFifthConsecutiveFailure_WhenInvoked_ThenNotifiesConnectionFailure()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        SetConsecutiveFailures(FourFailures); // Set to 4, next failure will be 5th

        // When
        await sut.Execute(_jobContext);

        // Then
        await _notificationService.Received(1).NotifyConnectionFailureAsync(FiveFailures);
    }

    [Fact]
    public async Task Execute_GivenFourthConsecutiveFailure_WhenInvoked_ThenDoesNotNotify()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        SetConsecutiveFailures(ThreeFailures); // Set to 3, next failure will be 4th

        // When
        await sut.Execute(_jobContext);

        // Then
        await _notificationService.DidNotReceive().NotifyConnectionFailureAsync(Arg.Any<int>());
    }

    [Fact]
    public async Task Execute_GivenTenthConsecutiveFailure_WhenInvoked_ThenNotifiesAgain()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        SetConsecutiveFailures(NineFailures); // Set to 9, next failure will be 10th

        // When
        await sut.Execute(_jobContext);

        // Then
        await _notificationService.Received(1).NotifyConnectionFailureAsync(TenFailures);
    }

    [Fact]
    public async Task Execute_GivenSixthConsecutiveFailure_WhenInvoked_ThenDoesNotNotify()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        SetConsecutiveFailures(FiveFailures); // Set to 5, next failure will be 6th

        // When
        await sut.Execute(_jobContext);

        // Then
        await _notificationService.DidNotReceive().NotifyConnectionFailureAsync(Arg.Any<int>());
    }

    [Fact]
    public async Task Execute_GivenTwentiethConsecutiveFailure_WhenInvoked_ThenNotifiesAgain()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        SetConsecutiveFailures(NineteenFailures); // Set to 19, next failure will be 20th

        // When
        await sut.Execute(_jobContext);

        // Then
        await _notificationService.Received(1).NotifyConnectionFailureAsync(TwentyFailures);
    }

    #endregion

    #region Execute - Counter Reset after Success

    [Fact]
    public async Task Execute_GivenPreviousFailures_WhenSuccessfulFetch_ThenResetsFailureCounter()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        SetConsecutiveFailures(ThreeFailures);

        // When
        await sut.Execute(_jobContext);

        // Then
        GetConsecutiveFailures().Should().Be(ZeroFailures);
    }

    [Fact]
    public async Task Execute_GivenPreviousFailures_WhenSuccessfulFetch_ThenLogsConnectionRestored()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        SetConsecutiveFailures(ThreeFailures);

        // When
        await sut.Execute(_jobContext);

        // Then
        _logger.Received(1).Log(
            LogLevel.Information,
            Arg.Any<EventId>(),
            Arg.Is<object>(o => o.ToString()!.Contains("restored")),
            Arg.Is<Exception?>(e => e == null),
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task Execute_GivenNoFailures_WhenSuccessfulFetch_ThenDoesNotLogRestored()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        // _consecutiveFailures is 0 by default

        // When
        await sut.Execute(_jobContext);

        // Then - should only log debug "synced successfully", not "restored"
        _logger.DidNotReceive().Log(
            LogLevel.Information,
            Arg.Any<EventId>(),
            Arg.Is<object>(o => o.ToString()!.Contains("restored")),
            Arg.Any<Exception?>(),
            Arg.Any<Func<object, Exception?, string>>());
    }

    #endregion

    #region Execute - Error Handling

    [Fact]
    public async Task Execute_GivenProviderThrows_WhenInvoked_ThenDoesNotRethrow()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .ThrowsAsync(new HttpRequestException(NetworkErrorMessage));

        // When
        var act = () => sut.Execute(_jobContext);

        // Then
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task Execute_GivenSyncHandlerThrows_WhenInvoked_ThenDoesNotRethrow()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _syncHandler.HandleAsync(Arg.Any<SyncHeatPumpState.Command>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(DatabaseErrorMessage));

        // When
        var act = () => sut.Execute(_jobContext);

        // Then
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task Execute_GivenProviderThrows_WhenInvoked_ThenLogsError()
    {
        // Given
        var sut = CreateSut();
        var exception = new HttpRequestException(ConnectionTimeoutMessage);
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .ThrowsAsync(exception);

        // When
        await sut.Execute(_jobContext);

        // Then
        _logger.Received(1).Log(
            LogLevel.Error,
            Arg.Any<EventId>(),
            Arg.Any<object>(),
            exception,
            Arg.Any<Func<object, Exception?, string>>());
    }

    #endregion

    #region Execute - Logging

    [Fact]
    public async Task Execute_GivenDataNull_WhenInvoked_ThenLogsWarning()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        // When
        await sut.Execute(_jobContext);

        // Then
        _logger.Received(1).Log(
            LogLevel.Warning,
            Arg.Any<EventId>(),
            Arg.Is<object>(o => o.ToString()!.Contains("failed")),
            Arg.Is<Exception?>(e => e == null),
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task Execute_GivenSnapshotSaved_WhenInvoked_ThenLogsInformation()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        var heatPump = CreateHeatPump();

        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _heatPumpRepository.GetByIdAsync(
                Arg.Any<HeatPumpId>(), Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // When
        await sut.Execute(_jobContext);

        // Then
        _logger.Received(1).Log(
            LogLevel.Information,
            Arg.Any<EventId>(),
            Arg.Is<object>(o => o.ToString()!.Contains("snapshot")),
            Arg.Is<Exception?>(e => e == null),
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task Execute_GivenFifthFailure_WhenInvoked_ThenLogsError()
    {
        // Given
        var sut = CreateSut();
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        SetConsecutiveFailures(FourFailures);

        // When
        await sut.Execute(_jobContext);

        // Then
        _logger.Received(1).Log(
            LogLevel.Error,
            Arg.Any<EventId>(),
            Arg.Is<object>(o => o.ToString()!.Contains($"{NotificationThreshold} times")),
            Arg.Is<Exception?>(e => e == null),
            Arg.Any<Func<object, Exception?, string>>());
    }

    #endregion

    #region Execute - Full Integration Scenario

    [Fact]
    public async Task Execute_GivenSuccessfulExecution_WhenAllConditionsMet_ThenPerformsAllOperations()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();
        var heatPump = CreateHeatPump();

        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);
        _heatPumpRepository.GetByIdAsync(
                Arg.Any<HeatPumpId>(), Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // When
        await sut.Execute(_jobContext);

        // Then
        await _heishaMonProvider.Received(1).FetchDataAsync(Arg.Any<CancellationToken>());
        await _syncHandler.Received(1).HandleAsync(
            Arg.Any<SyncHeatPumpState.Command>(),
            Arg.Any<CancellationToken>());
        await _snapshotHandler.Received(1).HandleAsync(
            Arg.Any<SaveHeatPumpSnapshot.Command>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Execute_GivenFailureThenSuccess_WhenInvoked_ThenResetsAndContinuesNormally()
    {
        // Given
        var sut = CreateSut();
        var data = CreateHeishaMonData();

        // First call fails
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns((HeishaMonData?)null);

        await sut.Execute(_jobContext);
        GetConsecutiveFailures().Should().Be(OneFailure);

        // Second call succeeds
        _heishaMonProvider.FetchDataAsync(Arg.Any<CancellationToken>())
            .Returns(data);

        // When
        await sut.Execute(_jobContext);

        // Then
        GetConsecutiveFailures().Should().Be(ZeroFailures);
    }

    #endregion
}
