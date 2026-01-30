using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class OperationsDataTests
{
    private const decimal ValidCompressorHours = 1234.5m;
    private const int ValidCompressorStarts = 567;
    private const decimal ZeroHours = 0m;
    private const int ZeroStarts = 0;
    private const decimal LargeCompressorHours = 99999.99m;
    private const decimal NegativeHours = -1m;
    private const int NegativeStarts = -1;
    private const decimal ValidHours = 100m;
    private const int ValidStarts = 100;
    private const decimal NegativeHoursForBothTest = -100m;
    private const int NegativeStartsForBothTest = -50;
    private const decimal DecimalHoursForFormatting = 1234.567m;
    private const decimal OneThousandHours = 1000m;
    private const decimal TwoThousandHours = 2000m;
    private const int FiveHundredStarts = 500;
    private const int SixHundredStarts = 600;

    private const string CompressorHoursParameterName = "compressorHours";
    private const string CompressorStartsParameterName = "compressorStarts";
    private const string OperatingHoursCannotBeNegativeMessage = "*Operating hours cannot be negative*";
    private const string StartCountCannotBeNegativeMessage = "*Start count cannot be negative*";
    private const string TypicalValuesFormatted = "1234h / 567 starts";
    private const string ZeroValuesFormatted = "0h / 0 starts";
    private const string RoundedDecimalFormatted = "1235h / 100 starts";

    #region Constructor - Valid Values

    [Fact]
    public void Constructor_GivenValidHoursAndStarts_ShouldCreateOperationsData()
    {
        // Given
        const decimal compressorHours = ValidCompressorHours;
        const int compressorStarts = ValidCompressorStarts;

        // When
        var operationsData = new OperationsData(compressorHours, compressorStarts);

        // Then
        operationsData.CompressorHours.Should().Be(compressorHours);
        operationsData.CompressorStarts.Should().Be(compressorStarts);
    }

    [Fact]
    public void Constructor_GivenZeroValues_ShouldCreateOperationsData()
    {
        // Given
        const decimal compressorHours = ZeroHours;
        const int compressorStarts = ZeroStarts;

        // When
        var operationsData = new OperationsData(compressorHours, compressorStarts);

        // Then
        operationsData.CompressorHours.Should().Be(ZeroHours);
        operationsData.CompressorStarts.Should().Be(ZeroStarts);
    }

    [Fact]
    public void Constructor_GivenLargeValues_ShouldCreateOperationsData()
    {
        // Given
        const decimal compressorHours = LargeCompressorHours;
        const int compressorStarts = int.MaxValue;

        // When
        var operationsData = new OperationsData(compressorHours, compressorStarts);

        // Then
        operationsData.CompressorHours.Should().Be(compressorHours);
        operationsData.CompressorStarts.Should().Be(compressorStarts);
    }

    #endregion

    #region Constructor - Invalid Values

    [Fact]
    public void Constructor_GivenNegativeCompressorHours_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        const decimal negativeHours = NegativeHours;
        const int validStarts = ValidStarts;

        // When
        var act = () => new OperationsData(negativeHours, validStarts);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithParameterName(CompressorHoursParameterName)
            .WithMessage(OperatingHoursCannotBeNegativeMessage);
    }

    [Fact]
    public void Constructor_GivenNegativeCompressorStarts_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        const decimal validHours = ValidHours;
        const int negativeStarts = NegativeStarts;

        // When
        var act = () => new OperationsData(validHours, negativeStarts);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithParameterName(CompressorStartsParameterName)
            .WithMessage(StartCountCannotBeNegativeMessage);
    }

    [Fact]
    public void Constructor_GivenBothNegativeValues_ShouldThrowForCompressorHoursFirst()
    {
        // Given
        const decimal negativeHours = NegativeHoursForBothTest;
        const int negativeStarts = NegativeStartsForBothTest;

        // When
        var act = () => new OperationsData(negativeHours, negativeStarts);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithParameterName(CompressorHoursParameterName);
    }

    #endregion

    #region Zero Static Property

    [Fact]
    public void Zero_ShouldReturnOperationsDataWithZeroValues()
    {
        // When
        var zero = OperationsData.Zero;

        // Then
        zero.CompressorHours.Should().Be(ZeroHours);
        zero.CompressorStarts.Should().Be(ZeroStarts);
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenTypicalValues_ShouldFormatCorrectly()
    {
        // Given
        var operationsData = new OperationsData(1234m, ValidCompressorStarts);

        // When
        var result = operationsData.ToString();

        // Then
        result.Should().Be(TypicalValuesFormatted);
    }

    [Fact]
    public void ToString_GivenZeroValues_ShouldFormatCorrectly()
    {
        // Given
        var operationsData = OperationsData.Zero;

        // When
        var result = operationsData.ToString();

        // Then
        result.Should().Be(ZeroValuesFormatted);
    }

    [Fact]
    public void ToString_GivenDecimalHours_ShouldRoundToWholeNumber()
    {
        // Given
        var operationsData = new OperationsData(DecimalHoursForFormatting, ValidStarts);

        // When
        var result = operationsData.ToString();

        // Then
        result.Should().Be(RoundedDecimalFormatted);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenSameValues_ShouldBeEqual()
    {
        // Given
        var data1 = new OperationsData(OneThousandHours, FiveHundredStarts);
        var data2 = new OperationsData(OneThousandHours, FiveHundredStarts);

        // Then
        data1.Should().Be(data2);
    }

    [Fact]
    public void Equality_GivenDifferentHours_ShouldNotBeEqual()
    {
        // Given
        var data1 = new OperationsData(OneThousandHours, FiveHundredStarts);
        var data2 = new OperationsData(TwoThousandHours, FiveHundredStarts);

        // Then
        data1.Should().NotBe(data2);
    }

    [Fact]
    public void Equality_GivenDifferentStarts_ShouldNotBeEqual()
    {
        // Given
        var data1 = new OperationsData(OneThousandHours, FiveHundredStarts);
        var data2 = new OperationsData(OneThousandHours, SixHundredStarts);

        // Then
        data1.Should().NotBe(data2);
    }

    #endregion
}
