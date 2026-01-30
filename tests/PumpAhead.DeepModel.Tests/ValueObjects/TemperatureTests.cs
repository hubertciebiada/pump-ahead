using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class TemperatureTests
{
    private const decimal ValidTemperatureCelsius = 21.5m;
    private const decimal ZeroTemperatureCelsius = 0m;
    private const decimal TwentyCelsius = 20m;
    private const decimal TwentyFiveCelsius = 25m;
    private const decimal FifteenCelsius = 15m;
    private const decimal ThirtyCelsius = 30m;
    private const decimal ThirtyFiveCelsius = 35m;
    private const decimal TenCelsius = 10m;
    private const decimal FiveCelsius = 5m;
    private const decimal MinusTenCelsius = -10m;
    private const decimal FortyCelsius = 40m;
    private const decimal MinusFivePointThreeCelsius = -5.3m;
    private const decimal TwentyTwoPointFiveCelsius = 22.5m;
    private const decimal BelowAbsoluteZero = -273.16m;
    private const decimal MinusTwoHundredCelsius = -200m;
    private const decimal OneHundredCelsius = 100m;

    private const string CelsiusParameterName = "celsius";
    private const string AbsoluteZeroMessage = "*absolute zero*";
    private const string ValidTemperatureFormatted = "21.5";
    private const string TwentyCelsiusFormatted = "20.0";
    private const string ZeroCelsiusFormatted = "0.0";
    private const string MinusFivePointThreeCelsiusFormatted = "-5.3";

    #region Creation

    [Fact]
    public void FromCelsius_GivenValidValue_ShouldCreateTemperatureWithCorrectValue()
    {
        // Given
        const decimal celsius = ValidTemperatureCelsius;

        // When
        var temperature = Temperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(ValidTemperatureCelsius);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-273.15)]
    [InlineData(100)]
    [InlineData(-50)]
    public void FromCelsius_GivenValidBoundaryValues_ShouldCreateTemperature(decimal celsius)
    {
        // Given & When
        var temperature = Temperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    [Fact]
    public void FromCelsius_GivenValueBelowAbsoluteZero_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        const decimal belowAbsoluteZero = BelowAbsoluteZero;

        // When
        var act = () => Temperature.FromCelsius(belowAbsoluteZero);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithParameterName(CelsiusParameterName)
            .WithMessage(AbsoluteZeroMessage);
    }

    [Theory]
    [InlineData(-274)]
    [InlineData(-500)]
    [InlineData(-1000)]
    public void FromCelsius_GivenVariousValuesBelowAbsoluteZero_ShouldThrowArgumentOutOfRangeException(decimal celsius)
    {
        // Given & When
        var act = () => Temperature.FromCelsius(celsius);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    #endregion

    #region Arithmetic Operators

    [Fact]
    public void Addition_GivenTwoTemperatures_ShouldReturnSumOfCelsiusValues()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyCelsius);
        var temp2 = Temperature.FromCelsius(FiveCelsius);

        // When
        var result = temp1 + temp2;

        // Then
        result.Celsius.Should().Be(TwentyFiveCelsius);
    }

    [Fact]
    public void Addition_GivenNegativeAndPositiveTemperatures_ShouldReturnCorrectSum()
    {
        // Given
        var temp1 = Temperature.FromCelsius(MinusTenCelsius);
        var temp2 = Temperature.FromCelsius(ThirtyCelsius);

        // When
        var result = temp1 + temp2;

        // Then
        result.Celsius.Should().Be(TwentyCelsius);
    }

    [Fact]
    public void Subtraction_GivenTwoTemperatures_ShouldReturnDifferenceOfCelsiusValues()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyFiveCelsius);
        var temp2 = Temperature.FromCelsius(FiveCelsius);

        // When
        var result = temp1 - temp2;

        // Then
        result.Celsius.Should().Be(TwentyCelsius);
    }

    [Fact]
    public void Subtraction_GivenResultBelowAbsoluteZero_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        var temp1 = Temperature.FromCelsius(MinusTwoHundredCelsius);
        var temp2 = Temperature.FromCelsius(OneHundredCelsius);

        // When
        var act = () => temp1 - temp2;

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    #endregion

    #region Comparison Operators

    [Fact]
    public void GreaterThan_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyFiveCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThan_GivenFirstIsLess_ShouldReturnFalse()
    {
        // Given
        var temp1 = Temperature.FromCelsius(FifteenCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThan_GivenEqualValues_ShouldReturnFalse()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void LessThan_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = Temperature.FromCelsius(FifteenCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThan_GivenFirstIsGreater_ShouldReturnFalse()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyFiveCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyFiveCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 <= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = Temperature.FromCelsius(FifteenCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1 <= temp2;

        // Then
        result.Should().BeTrue();
    }

    #endregion

    #region IComparable

    [Fact]
    public void CompareTo_GivenOrderedTemperatures_ShouldSortCorrectly()
    {
        // Given
        var temps = new[]
        {
            Temperature.FromCelsius(TwentyFiveCelsius),
            Temperature.FromCelsius(FifteenCelsius),
            Temperature.FromCelsius(TwentyCelsius)
        };

        // When
        var ordered = temps.OrderBy(t => t).ToArray();

        // Then
        ordered[0].Celsius.Should().Be(FifteenCelsius);
        ordered[1].Celsius.Should().Be(TwentyCelsius);
        ordered[2].Celsius.Should().Be(TwentyFiveCelsius);
    }

    [Fact]
    public void CompareTo_GivenSmallerValue_ShouldReturnNegative()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TenCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BeNegative();
    }

    [Fact]
    public void CompareTo_GivenLargerValue_ShouldReturnPositive()
    {
        // Given
        var temp1 = Temperature.FromCelsius(ThirtyCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BePositive();
    }

    [Fact]
    public void CompareTo_GivenEqualValue_ShouldReturnZero()
    {
        // Given
        var temp1 = Temperature.FromCelsius(TwentyCelsius);
        var temp2 = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().Be(0);
    }

    #endregion

    #region Clamp

    [Fact]
    public void Clamp_GivenValueBelowMin_ShouldReturnMin()
    {
        // Given
        var temp = Temperature.FromCelsius(FifteenCelsius);
        var min = Temperature.FromCelsius(TwentyCelsius);
        var max = Temperature.FromCelsius(ThirtyFiveCelsius);

        // When
        var result = temp.Clamp(min, max);

        // Then
        result.Celsius.Should().Be(TwentyCelsius);
    }

    [Fact]
    public void Clamp_GivenValueAboveMax_ShouldReturnMax()
    {
        // Given
        var temp = Temperature.FromCelsius(FortyCelsius);
        var min = Temperature.FromCelsius(TwentyCelsius);
        var max = Temperature.FromCelsius(ThirtyFiveCelsius);

        // When
        var result = temp.Clamp(min, max);

        // Then
        result.Celsius.Should().Be(ThirtyFiveCelsius);
    }

    [Fact]
    public void Clamp_GivenValueWithinRange_ShouldReturnSameValue()
    {
        // Given
        var temp = Temperature.FromCelsius(TwentyFiveCelsius);
        var min = Temperature.FromCelsius(TwentyCelsius);
        var max = Temperature.FromCelsius(ThirtyFiveCelsius);

        // When
        var result = temp.Clamp(min, max);

        // Then
        result.Celsius.Should().Be(TwentyFiveCelsius);
    }

    [Fact]
    public void Clamp_GivenValueEqualToMin_ShouldReturnSameValue()
    {
        // Given
        var temp = Temperature.FromCelsius(TwentyCelsius);
        var min = Temperature.FromCelsius(TwentyCelsius);
        var max = Temperature.FromCelsius(ThirtyFiveCelsius);

        // When
        var result = temp.Clamp(min, max);

        // Then
        result.Celsius.Should().Be(TwentyCelsius);
    }

    [Fact]
    public void Clamp_GivenValueEqualToMax_ShouldReturnSameValue()
    {
        // Given
        var temp = Temperature.FromCelsius(ThirtyFiveCelsius);
        var min = Temperature.FromCelsius(TwentyCelsius);
        var max = Temperature.FromCelsius(ThirtyFiveCelsius);

        // When
        var result = temp.Clamp(min, max);

        // Then
        result.Celsius.Should().Be(ThirtyFiveCelsius);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenTwoTemperaturesWithSameValue_ShouldBeEqual()
    {
        // Given
        var temp1 = Temperature.FromCelsius(ValidTemperatureCelsius);
        var temp2 = Temperature.FromCelsius(ValidTemperatureCelsius);

        // When & Then
        temp1.Should().Be(temp2);
        (temp1 == temp2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenTwoTemperaturesWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var temp1 = Temperature.FromCelsius(ValidTemperatureCelsius);
        var temp2 = Temperature.FromCelsius(TwentyTwoPointFiveCelsius);

        // When & Then
        temp1.Should().NotBe(temp2);
        (temp1 != temp2).Should().BeTrue();
    }

    [Fact]
    public void GetHashCode_GivenTwoTemperaturesWithSameValue_ShouldHaveSameHashCode()
    {
        // Given
        var temp1 = Temperature.FromCelsius(ValidTemperatureCelsius);
        var temp2 = Temperature.FromCelsius(ValidTemperatureCelsius);

        // When & Then
        temp1.GetHashCode().Should().Be(temp2.GetHashCode());
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenPositiveValue_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = Temperature.FromCelsius(ValidTemperatureCelsius);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be($"{ValidTemperatureFormatted}\u00b0C");
    }

    [Fact]
    public void ToString_GivenNegativeValue_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = Temperature.FromCelsius(MinusFivePointThreeCelsius);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be($"{MinusFivePointThreeCelsiusFormatted}\u00b0C");
    }

    [Fact]
    public void ToString_GivenWholeNumber_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = Temperature.FromCelsius(TwentyCelsius);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be($"{TwentyCelsiusFormatted}\u00b0C");
    }

    [Fact]
    public void ToString_GivenZero_ShouldFormatCorrectly()
    {
        // Given
        var temp = Temperature.FromCelsius(ZeroTemperatureCelsius);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be($"{ZeroCelsiusFormatted}\u00b0C");
    }

    #endregion
}
