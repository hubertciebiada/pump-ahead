using FluentAssertions;
using Microsoft.AspNetCore.SignalR;
using NSubstitute;
using PumpAhead.Adapters.Gui.Hubs;
using PumpAhead.Adapters.Gui.Services;

namespace PumpAhead.Adapters.Gui.Tests.Services;

public class SignalRHeatPumpNotificationServiceTests
{
    private const int MultipleCallCount = 3;
    private const int FiveConsecutiveFailures = 5;
    private const int ZeroConsecutiveFailures = 0;
    private const int SingleFailure = 1;
    private const string HubConnectionFailedMessage = "Hub connection failed";

    private readonly IHubContext<SensorHub, ISensorHubClient> _hubContext;
    private readonly ISensorHubClient _allClients;
    private readonly SignalRHeatPumpNotificationService _sut;

    public SignalRHeatPumpNotificationServiceTests()
    {
        _hubContext = Substitute.For<IHubContext<SensorHub, ISensorHubClient>>();
        _allClients = Substitute.For<ISensorHubClient>();
        _hubContext.Clients.All.Returns(_allClients);
        _sut = new SignalRHeatPumpNotificationService(_hubContext);
    }

    [Fact]
    public async Task NotifyHeatPumpUpdatedAsync_GivenServiceCall_WhenInvoked_ThenCallsReceiveHeatPumpUpdateOnAllClients()
    {
        // Given
        // Service is set up in constructor

        // When
        await _sut.NotifyHeatPumpUpdatedAsync();

        // Then
        await _allClients.Received(1).ReceiveHeatPumpUpdate();
    }

    [Fact]
    public async Task NotifyHeatPumpUpdatedAsync_GivenMultipleCalls_WhenInvoked_ThenCallsReceiveHeatPumpUpdateEachTime()
    {
        // Given
        // MultipleCallCount defined as class constant

        // When
        for (int i = 0; i < MultipleCallCount; i++)
        {
            await _sut.NotifyHeatPumpUpdatedAsync();
        }

        // Then
        await _allClients.Received(MultipleCallCount).ReceiveHeatPumpUpdate();
    }

    [Fact]
    public async Task NotifyConnectionFailureAsync_GivenConsecutiveFailures_WhenInvoked_ThenCallsReceiveHeatPumpConnectionFailureWithCorrectCount()
    {
        // Given
        // FiveConsecutiveFailures defined as class constant

        // When
        await _sut.NotifyConnectionFailureAsync(FiveConsecutiveFailures);

        // Then
        await _allClients.Received(1).ReceiveHeatPumpConnectionFailure(FiveConsecutiveFailures);
    }

    [Fact]
    public async Task NotifyConnectionFailureAsync_GivenZeroFailures_WhenInvoked_ThenCallsReceiveHeatPumpConnectionFailureWithZero()
    {
        // Given
        // ZeroConsecutiveFailures defined as class constant

        // When
        await _sut.NotifyConnectionFailureAsync(ZeroConsecutiveFailures);

        // Then
        await _allClients.Received(1).ReceiveHeatPumpConnectionFailure(ZeroConsecutiveFailures);
    }

    [Theory]
    [InlineData(1)]
    [InlineData(10)]
    [InlineData(100)]
    public async Task NotifyConnectionFailureAsync_GivenVariousFailureCounts_WhenInvoked_ThenPassesCorrectValueToClients(int failureCount)
    {
        // Given
        // failureCount is provided by theory

        // When
        await _sut.NotifyConnectionFailureAsync(failureCount);

        // Then
        await _allClients.Received(1).ReceiveHeatPumpConnectionFailure(failureCount);
    }

    [Fact]
    public async Task NotifyConnectionFailureAsync_GivenHubThrowsException_WhenInvoked_ThenExceptionPropagates()
    {
        // Given
        var expectedException = new InvalidOperationException(HubConnectionFailedMessage);
        _allClients.ReceiveHeatPumpConnectionFailure(Arg.Any<int>())
            .Returns(Task.FromException(expectedException));

        // When
        var act = () => _sut.NotifyConnectionFailureAsync(SingleFailure);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(HubConnectionFailedMessage);
    }

    [Fact]
    public async Task NotifyHeatPumpUpdatedAsync_GivenHubThrowsException_WhenInvoked_ThenExceptionPropagates()
    {
        // Given
        var expectedException = new InvalidOperationException(HubConnectionFailedMessage);
        _allClients.ReceiveHeatPumpUpdate()
            .Returns(Task.FromException(expectedException));

        // When
        var act = () => _sut.NotifyHeatPumpUpdatedAsync();

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(HubConnectionFailedMessage);
    }
}
