using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class WaterTemperatureTests
{
    #region Creation

    [Fact]
    public void FromCelsius_GivenValidValue_ShouldCreateWaterTemperatureWithCorrectValue()
    {
        // Given
        const decimal celsius = 45.5m;

        // When
        var temperature = WaterTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(45.5m);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(50)]
    [InlineData(100)]
    [InlineData(25.5)]
    public void FromCelsius_GivenValidBoundaryValues_ShouldCreateWaterTemperature(decimal celsius)
    {
        // Given & When
        var temperature = WaterTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    [Theory]
    [InlineData(20)]
    [InlineData(35)]
    [InlineData(55)]
    [InlineData(70)]
    [InlineData(85)]
    public void FromCelsius_GivenTypicalHeatingWaterTemperatures_ShouldCreateWaterTemperature(decimal celsius)
    {
        // Given & When
        var temperature = WaterTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    #endregion

    #region Comparison Operators

    [Fact]
    public void GreaterThan_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(50m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThan_GivenFirstIsLess_ShouldReturnFalse()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(30m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThan_GivenEqualValues_ShouldReturnFalse()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(40m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void LessThan_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(30m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThan_GivenFirstIsGreater_ShouldReturnFalse()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(50m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(40m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(50m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(40m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1 <= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(30m);
        var temp2 = WaterTemperature.FromCelsius(40m);

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
            WaterTemperature.FromCelsius(55m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(45m)
        };

        // When
        var ordered = temps.OrderBy(t => t).ToArray();

        // Then
        ordered[0].Celsius.Should().Be(35m);
        ordered[1].Celsius.Should().Be(45m);
        ordered[2].Celsius.Should().Be(55m);
    }

    [Fact]
    public void CompareTo_GivenSmallerValue_ShouldReturnNegative()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(30m);
        var temp2 = WaterTemperature.FromCelsius(50m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BeNegative();
    }

    [Fact]
    public void CompareTo_GivenLargerValue_ShouldReturnPositive()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(60m);
        var temp2 = WaterTemperature.FromCelsius(40m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BePositive();
    }

    [Fact]
    public void CompareTo_GivenEqualValue_ShouldReturnZero()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(45m);
        var temp2 = WaterTemperature.FromCelsius(45m);

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
        var temp1 = WaterTemperature.FromCelsius(45.5m);
        var temp2 = WaterTemperature.FromCelsius(45.5m);

        // When & Then
        temp1.Should().Be(temp2);
        (temp1 == temp2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenTwoTemperaturesWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(45.5m);
        var temp2 = WaterTemperature.FromCelsius(50.5m);

        // When & Then
        temp1.Should().NotBe(temp2);
        (temp1 != temp2).Should().BeTrue();
    }

    [Fact]
    public void GetHashCode_GivenTwoTemperaturesWithSameValue_ShouldHaveSameHashCode()
    {
        // Given
        var temp1 = WaterTemperature.FromCelsius(45.5m);
        var temp2 = WaterTemperature.FromCelsius(45.5m);

        // When & Then
        temp1.GetHashCode().Should().Be(temp2.GetHashCode());
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenTypicalValue_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = WaterTemperature.FromCelsius(45.5m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("45.5°C");
    }

    [Fact]
    public void ToString_GivenWholeNumber_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = WaterTemperature.FromCelsius(50m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("50.0°C");
    }

    [Fact]
    public void ToString_GivenZero_ShouldFormatCorrectly()
    {
        // Given
        var temp = WaterTemperature.FromCelsius(0m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("0.0°C");
    }

    [Fact]
    public void ToString_GivenMaximumValue_ShouldFormatCorrectly()
    {
        // Given
        var temp = WaterTemperature.FromCelsius(100m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("100.0°C");
    }

    #endregion
}
