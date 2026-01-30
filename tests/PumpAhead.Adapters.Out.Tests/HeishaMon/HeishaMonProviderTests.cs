using System.Net;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using PumpAhead.Adapters.Out.HeishaMon;
using PumpAhead.DeepModel;
using RichardSzalay.MockHttp;

namespace PumpAhead.Adapters.Out.Tests.HeishaMon;

public class HeishaMonProviderTests
{
    private const string HeishaMonBaseAddress = "http://heishamon.local";
    private const string JsonEndpoint = "/json";
    private const string ApplicationJson = "application/json";
    private const string HeatpumpStateOn = "1";
    private const string HeatpumpStateOff = "0";
    private const string DefaultErrorCode = "H00";
    private const decimal DefaultPumpFlow = 12.5m;
    private const decimal DefaultOutsideTemperature = 5.5m;
    private const decimal DefaultChInletTemperature = 32.0m;
    private const decimal DefaultChOutletTemperature = 35.5m;
    private const decimal DefaultChTargetTemperature = 40.0m;
    private const decimal DefaultDhwActualTemperature = 48.5m;
    private const decimal DefaultDhwTargetTemperature = 50.0m;
    private const decimal DefaultCompressorFrequency = 45.0m;
    private const decimal DefaultHeatPowerProduction = 3500.0m;
    private const decimal DefaultHeatPowerConsumption = 850.0m;
    private const decimal DefaultCoolPowerProduction = 0.0m;
    private const decimal DefaultCoolPowerConsumption = 0.0m;
    private const decimal DefaultDhwPowerProduction = 2200.0m;
    private const decimal DefaultDhwPowerConsumption = 600.0m;
    private const decimal DefaultCompressorOperatingHours = 1234.5m;
    private const int DefaultCompressorStartCount = 567;
    private const int DefaultOperatingMode = 4;

    private readonly MockHttpMessageHandler _mockHttp;
    private readonly ILogger<HeishaMonProvider> _logger;
    private readonly HeishaMonProvider _sut;

    public HeishaMonProviderTests()
    {
        _mockHttp = new MockHttpMessageHandler();
        _logger = Substitute.For<ILogger<HeishaMonProvider>>();

        var httpClient = _mockHttp.ToHttpClient();
        httpClient.BaseAddress = new Uri(HeishaMonBaseAddress);

        _sut = new HeishaMonProvider(httpClient, _logger);
    }

    #region Given valid JSON response

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenReturnsCorrectlyMappedData()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(JsonEndpoint)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsIsOnCorrectly()
    {
        // Given
        var jsonResponse = CreateJsonWithHeatpumpState(HeatpumpStateOn);
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.IsOn.Should().BeTrue();
    }

    [Fact]
    public async Task FetchDataAsync_GivenHeatpumpStateZero_WhenCalled_ThenIsOnIsFalse()
    {
        // Given
        var jsonResponse = CreateJsonWithHeatpumpState(HeatpumpStateOff);
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.IsOn.Should().BeFalse();
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsOperatingModeCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.OperatingMode.Should().Be(OperatingMode.HeatDhw);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsPumpFlowCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.PumpFlowLitersPerMinute.Should().Be(DefaultPumpFlow);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsOutsideTemperatureCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.OutsideTemperatureCelsius.Should().Be(DefaultOutsideTemperature);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsCentralHeatingTemperaturesCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.CH_InletTemperatureCelsius.Should().Be(DefaultChInletTemperature);
        result.CH_OutletTemperatureCelsius.Should().Be(DefaultChOutletTemperature);
        result.CH_TargetTemperatureCelsius.Should().Be(DefaultChTargetTemperature);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsDhwTemperaturesCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.DHW_ActualTemperatureCelsius.Should().Be(DefaultDhwActualTemperature);
        result.DHW_TargetTemperatureCelsius.Should().Be(DefaultDhwTargetTemperature);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsCompressorFrequencyCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.CompressorFrequencyHertz.Should().Be(DefaultCompressorFrequency);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsPowerDataCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.HeatPowerProductionWatts.Should().Be(DefaultHeatPowerProduction);
        result.HeatPowerConsumptionWatts.Should().Be(DefaultHeatPowerConsumption);
        result.CoolPowerProductionWatts.Should().Be(DefaultCoolPowerProduction);
        result.CoolPowerConsumptionWatts.Should().Be(DefaultCoolPowerConsumption);
        result.DhwPowerProductionWatts.Should().Be(DefaultDhwPowerProduction);
        result.DhwPowerConsumptionWatts.Should().Be(DefaultDhwPowerConsumption);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsOperationsDataCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.CompressorOperatingHours.Should().Be(DefaultCompressorOperatingHours);
        result.CompressorStartCount.Should().Be(DefaultCompressorStartCount);
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsDefrostingStateCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.IsDefrosting.Should().BeFalse();
    }

    [Fact]
    public async Task FetchDataAsync_GivenDefrostingStateOne_WhenCalled_ThenIsDefrostingIsTrue()
    {
        // Given
        var jsonResponse = CreateJsonWithDefrostingState(HeatpumpStateOn);
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.IsDefrosting.Should().BeTrue();
    }

    [Fact]
    public async Task FetchDataAsync_GivenValidJsonResponse_WhenCalled_ThenMapsErrorCodeCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result!.ErrorCode.Should().Be(DefaultErrorCode);
    }

    [Fact]
    public async Task FetchDataAsync_GivenCaseInsensitiveKeys_WhenCalled_ThenMapsCorrectly()
    {
        // Given
        var jsonResponse = """
            {
                "heatpump": [
                    {"name": "HEATPUMP_STATE", "value": "1"},
                    {"name": "operating_mode_state", "value": "4"},
                    {"name": "Pump_Flow", "value": "10.0"},
                    {"name": "OUTSIDE_TEMP", "value": "3.0"}
                ]
            }
            """;
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();
        result!.IsOn.Should().BeTrue();
        result.OperatingMode.Should().Be(OperatingMode.HeatDhw);
    }

    #endregion

    #region Given HTTP errors

    [Fact]
    public async Task FetchDataAsync_GivenHttpNotFoundError_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(HttpStatusCode.NotFound);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenHttpInternalServerError_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(HttpStatusCode.InternalServerError);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenHttpServiceUnavailable_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(HttpStatusCode.ServiceUnavailable);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenConnectionRefused_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Throw(new HttpRequestException("Connection refused"));

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given timeout

    [Fact]
    public async Task FetchDataAsync_GivenTimeout_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Throw(new TaskCanceledException("Request timed out", new TimeoutException()));

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenOperationCanceled_WhenCalled_ThenReturnsNull()
    {
        // Given
        using var cts = new CancellationTokenSource();
        cts.Cancel();

        _mockHttp
            .When(JsonEndpoint)
            .Throw(new TaskCanceledException("Operation canceled", null, cts.Token));

        // When
        var result = await _sut.FetchDataAsync(cts.Token);

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given invalid JSON

    [Fact]
    public async Task FetchDataAsync_GivenInvalidJson_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(ApplicationJson, "not valid json {{{");

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenEmptyJsonObject_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(ApplicationJson, "{}");

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenEmptyHeatpumpArray_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(ApplicationJson, """{"heatpump": []}""");

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenNullHeatpump_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(ApplicationJson, """{"heatpump": null}""");

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task FetchDataAsync_GivenEmptyResponse_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(JsonEndpoint)
            .Respond(ApplicationJson, "");

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given missing fields

    [Fact]
    public async Task FetchDataAsync_GivenMissingNumericField_WhenCalled_ThenDefaultsToZero()
    {
        // Given
        var jsonResponse = """
            {
                "heatpump": [
                    {"name": "Heatpump_State", "value": "1"}
                ]
            }
            """;
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();
        result!.PumpFlowLitersPerMinute.Should().Be(0m);
        result.OutsideTemperatureCelsius.Should().Be(0m);
        result.CompressorFrequencyHertz.Should().Be(0m);
    }

    [Fact]
    public async Task FetchDataAsync_GivenMissingErrorField_WhenCalled_ThenDefaultsToEmptyString()
    {
        // Given
        var jsonResponse = """
            {
                "heatpump": [
                    {"name": "Heatpump_State", "value": "1"}
                ]
            }
            """;
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();
        result!.ErrorCode.Should().BeEmpty();
    }

    [Fact]
    public async Task FetchDataAsync_GivenInvalidNumericValue_WhenCalled_ThenDefaultsToZero()
    {
        // Given
        var jsonResponse = """
            {
                "heatpump": [
                    {"name": "Heatpump_State", "value": "1"},
                    {"name": "Pump_Flow", "value": "not-a-number"}
                ]
            }
            """;
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();
        result!.PumpFlowLitersPerMinute.Should().Be(0m);
    }

    #endregion

    #region Given decimal values with various formats

    [Theory]
    [InlineData("12.5", 12.5)]
    [InlineData("12,5", 125)] // Comma is treated as thousands separator with NumberStyles.Any
    [InlineData("-5.5", -5.5)]
    [InlineData("0", 0)]
    [InlineData("100", 100)]
    [InlineData("12.500", 12.5)]
    public async Task FetchDataAsync_GivenVariousDecimalFormats_WhenCalled_ThenParsesCorrectly(
        string inputValue, decimal expectedValue)
    {
        // Given
        var jsonResponse = $$"""
            {
                "heatpump": [
                    {"name": "Heatpump_State", "value": "1"},
                    {"name": "Outside_Temp", "value": "{{inputValue}}"}
                ]
            }
            """;
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();
        result!.OutsideTemperatureCelsius.Should().Be(expectedValue);
    }

    #endregion

    #region All fields mapping verification

    [Fact]
    public async Task FetchDataAsync_GivenCompleteJsonResponse_WhenCalled_ThenAllFieldsAreMappedCorrectly()
    {
        // Given
        var jsonResponse = CreateCompleteJsonResponse();
        _mockHttp.When(JsonEndpoint).Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.FetchDataAsync();

        // Then
        result.Should().NotBeNull();

        // Core state
        result!.IsOn.Should().BeTrue();
        result.OperatingMode.Should().Be(OperatingMode.HeatDhw);
        result.PumpFlowLitersPerMinute.Should().Be(DefaultPumpFlow);
        result.OutsideTemperatureCelsius.Should().Be(DefaultOutsideTemperature);

        // Central Heating
        result.CH_InletTemperatureCelsius.Should().Be(DefaultChInletTemperature);
        result.CH_OutletTemperatureCelsius.Should().Be(DefaultChOutletTemperature);
        result.CH_TargetTemperatureCelsius.Should().Be(DefaultChTargetTemperature);

        // Domestic Hot Water
        result.DHW_ActualTemperatureCelsius.Should().Be(DefaultDhwActualTemperature);
        result.DHW_TargetTemperatureCelsius.Should().Be(DefaultDhwTargetTemperature);

        // Performance
        result.CompressorFrequencyHertz.Should().Be(DefaultCompressorFrequency);

        // Power
        result.HeatPowerProductionWatts.Should().Be(DefaultHeatPowerProduction);
        result.HeatPowerConsumptionWatts.Should().Be(DefaultHeatPowerConsumption);
        result.CoolPowerProductionWatts.Should().Be(1200.0m);
        result.CoolPowerConsumptionWatts.Should().Be(400.0m);
        result.DhwPowerProductionWatts.Should().Be(DefaultDhwPowerProduction);
        result.DhwPowerConsumptionWatts.Should().Be(DefaultDhwPowerConsumption);

        // Operations
        result.CompressorOperatingHours.Should().Be(DefaultCompressorOperatingHours);
        result.CompressorStartCount.Should().Be(DefaultCompressorStartCount);

        // Defrost
        result.IsDefrosting.Should().BeFalse();

        // Error
        result.ErrorCode.Should().Be(DefaultErrorCode);
    }

    #endregion

    #region Helper methods

    private static string CreateValidJsonResponse() => """
        {
            "heatpump": [
                {"name": "Heatpump_State", "value": "1"},
                {"name": "Operating_Mode_State", "value": "4"},
                {"name": "Pump_Flow", "value": "12.5"},
                {"name": "Outside_Temp", "value": "5.5"},
                {"name": "Main_Inlet_Temp", "value": "32.0"},
                {"name": "Main_Outlet_Temp", "value": "35.5"},
                {"name": "Main_Target_Temp", "value": "40.0"},
                {"name": "DHW_Temp", "value": "48.5"},
                {"name": "DHW_Target_Temp", "value": "50.0"},
                {"name": "Compressor_Freq", "value": "45.0"},
                {"name": "Heat_Power_Production", "value": "3500.0"},
                {"name": "Heat_Power_Consumption", "value": "850.0"},
                {"name": "Cool_Power_Production", "value": "0.0"},
                {"name": "Cool_Power_Consumption", "value": "0.0"},
                {"name": "DHW_Power_Production", "value": "2200.0"},
                {"name": "DHW_Power_Consumption", "value": "600.0"},
                {"name": "Operations_Hours", "value": "1234.5"},
                {"name": "Operations_Counter", "value": "567"},
                {"name": "Defrosting_State", "value": "0"},
                {"name": "Error", "value": "H00"}
            ],
            "1wire": [],
            "s0": []
        }
        """;

    private static string CreateCompleteJsonResponse() => """
        {
            "heatpump": [
                {"name": "Heatpump_State", "value": "1"},
                {"name": "Operating_Mode_State", "value": "4"},
                {"name": "Pump_Flow", "value": "12.5"},
                {"name": "Outside_Temp", "value": "5.5"},
                {"name": "Main_Inlet_Temp", "value": "32.0"},
                {"name": "Main_Outlet_Temp", "value": "35.5"},
                {"name": "Main_Target_Temp", "value": "40.0"},
                {"name": "DHW_Temp", "value": "48.5"},
                {"name": "DHW_Target_Temp", "value": "50.0"},
                {"name": "Compressor_Freq", "value": "45.0"},
                {"name": "Heat_Power_Production", "value": "3500.0"},
                {"name": "Heat_Power_Consumption", "value": "850.0"},
                {"name": "Cool_Power_Production", "value": "1200.0"},
                {"name": "Cool_Power_Consumption", "value": "400.0"},
                {"name": "DHW_Power_Production", "value": "2200.0"},
                {"name": "DHW_Power_Consumption", "value": "600.0"},
                {"name": "Operations_Hours", "value": "1234.5"},
                {"name": "Operations_Counter", "value": "567"},
                {"name": "Defrosting_State", "value": "0"},
                {"name": "Error", "value": "H00"}
            ],
            "1wire": [],
            "s0": []
        }
        """;

    private static string CreateJsonWithHeatpumpState(string stateValue) => $$"""
        {
            "heatpump": [
                {"name": "Heatpump_State", "value": "{{stateValue}}"},
                {"name": "Operating_Mode_State", "value": "4"},
                {"name": "Pump_Flow", "value": "12.5"},
                {"name": "Outside_Temp", "value": "5.5"}
            ]
        }
        """;

    private static string CreateJsonWithDefrostingState(string stateValue) => $$"""
        {
            "heatpump": [
                {"name": "Heatpump_State", "value": "1"},
                {"name": "Operating_Mode_State", "value": "4"},
                {"name": "Defrosting_State", "value": "{{stateValue}}"}
            ]
        }
        """;

    #endregion
}
