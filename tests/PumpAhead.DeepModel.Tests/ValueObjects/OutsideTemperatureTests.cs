using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class OutsideTemperatureTests
{
    #region Creation

    [Fact]
    public void FromCelsius_GivenValidValue_ShouldCreateOutsideTemperatureWithCorrectValue()
    {
        // Given
        const decimal celsius = 15.5m;

        // When
        var temperature = OutsideTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(15.5m);
    }

    [Theory]
    [InlineData(-50)]
    [InlineData(-25)]
    [InlineData(0)]
    [InlineData(25)]
    [InlineData(60)]
    public void FromCelsius_GivenValidBoundaryValues_ShouldCreateOutsideTemperature(decimal celsius)
    {
        // Given & When
        var temperature = OutsideTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    [Theory]
    [InlineData(-20)]
    [InlineData(-10)]
    [InlineData(0)]
    [InlineData(10)]
    [InlineData(20)]
    [InlineData(35)]
    public void FromCelsius_GivenTypicalOutsideTemperatures_ShouldCreateOutsideTemperature(decimal celsius)
    {
        // Given & When
        var temperature = OutsideTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    #endregion

    #region Comparison Operators

    [Fact]
    public void GreaterThan_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(20m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThan_GivenFirstIsLess_ShouldReturnFalse()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(-10m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThan_GivenEqualValues_ShouldReturnFalse()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15m);
        var temp2 = OutsideTemperature.FromCelsius(15m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void LessThan_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(-15m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThan_GivenFirstIsGreater_ShouldReturnFalse()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(25m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15m);
        var temp2 = OutsideTemperature.FromCelsius(15m);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(20m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15m);
        var temp2 = OutsideTemperature.FromCelsius(15m);

        // When
        var result = temp1 <= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(-5m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

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
            OutsideTemperature.FromCelsius(25m),
            OutsideTemperature.FromCelsius(-15m),
            OutsideTemperature.FromCelsius(5m)
        };

        // When
        var ordered = temps.OrderBy(t => t).ToArray();

        // Then
        ordered[0].Celsius.Should().Be(-15m);
        ordered[1].Celsius.Should().Be(5m);
        ordered[2].Celsius.Should().Be(25m);
    }

    [Fact]
    public void CompareTo_GivenSmallerValue_ShouldReturnNegative()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(-10m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BeNegative();
    }

    [Fact]
    public void CompareTo_GivenLargerValue_ShouldReturnPositive()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(30m);
        var temp2 = OutsideTemperature.FromCelsius(10m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BePositive();
    }

    [Fact]
    public void CompareTo_GivenEqualValue_ShouldReturnZero()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15m);
        var temp2 = OutsideTemperature.FromCelsius(15m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().Be(0);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenTwoTemperaturesWithSameValue_ShouldBeEqual()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15.5m);
        var temp2 = OutsideTemperature.FromCelsius(15.5m);

        // When & Then
        temp1.Should().Be(temp2);
        (temp1 == temp2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenTwoTemperaturesWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15.5m);
        var temp2 = OutsideTemperature.FromCelsius(-5.5m);

        // When & Then
        temp1.Should().NotBe(temp2);
        (temp1 != temp2).Should().BeTrue();
    }

    [Fact]
    public void GetHashCode_GivenTwoTemperaturesWithSameValue_ShouldHaveSameHashCode()
    {
        // Given
        var temp1 = OutsideTemperature.FromCelsius(15.5m);
        var temp2 = OutsideTemperature.FromCelsius(15.5m);

        // When & Then
        temp1.GetHashCode().Should().Be(temp2.GetHashCode());
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenPositiveValue_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = OutsideTemperature.FromCelsius(15.5m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("15.5°C");
    }

    [Fact]
    public void ToString_GivenNegativeValue_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = OutsideTemperature.FromCelsius(-12.3m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("-12.3°C");
    }

    [Fact]
    public void ToString_GivenWholeNumber_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = OutsideTemperature.FromCelsius(20m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("20.0°C");
    }

    [Fact]
    public void ToString_GivenZero_ShouldFormatCorrectly()
    {
        // Given
        var temp = OutsideTemperature.FromCelsius(0m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("0.0°C");
    }

    [Fact]
    public void ToString_GivenMinimumValue_ShouldFormatCorrectly()
    {
        // Given
        var temp = OutsideTemperature.FromCelsius(-50m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("-50.0°C");
    }

    [Fact]
    public void ToString_GivenMaximumValue_ShouldFormatCorrectly()
    {
        // Given
        var temp = OutsideTemperature.FromCelsius(60m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("60.0°C");
    }

    #endregion
}
