using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class DhwTemperatureTests
{
    #region Creation

    [Fact]
    public void FromCelsius_GivenValidValue_ShouldCreateDhwTemperatureWithCorrectValue()
    {
        // Given
        const decimal celsius = 48.5m;

        // When
        var temperature = DhwTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(48.5m);
    }

    [Theory]
    [InlineData(40)]
    [InlineData(48)]
    [InlineData(55)]
    [InlineData(60)]
    public void FromCelsius_GivenTypicalDhwTargetTemperatures_ShouldCreateDhwTemperature(decimal celsius)
    {
        // Given & When
        var temperature = DhwTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    [Theory]
    [InlineData(35)]
    [InlineData(45)]
    [InlineData(52)]
    [InlineData(58)]
    public void FromCelsius_GivenTypicalDhwActualTemperatures_ShouldCreateDhwTemperature(decimal celsius)
    {
        // Given & When
        var temperature = DhwTemperature.FromCelsius(celsius);

        // Then
        temperature.Celsius.Should().Be(celsius);
    }

    #endregion

    #region Comparison Operators

    [Fact]
    public void GreaterThan_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(55m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThan_GivenFirstIsLess_ShouldReturnFalse()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(40m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThan_GivenEqualValues_ShouldReturnFalse()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(48m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 > temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void LessThan_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(40m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThan_GivenFirstIsGreater_ShouldReturnFalse()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(55m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 < temp2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(48m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(55m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 >= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(48m);
        var temp2 = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp1 <= temp2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(40m);
        var temp2 = DhwTemperature.FromCelsius(48m);

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
            DhwTemperature.FromCelsius(55m),
            DhwTemperature.FromCelsius(40m),
            DhwTemperature.FromCelsius(48m)
        };

        // When
        var ordered = temps.OrderBy(t => t).ToArray();

        // Then
        ordered[0].Celsius.Should().Be(40m);
        ordered[1].Celsius.Should().Be(48m);
        ordered[2].Celsius.Should().Be(55m);
    }

    [Fact]
    public void CompareTo_GivenSmallerValue_ShouldReturnNegative()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(40m);
        var temp2 = DhwTemperature.FromCelsius(55m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BeNegative();
    }

    [Fact]
    public void CompareTo_GivenLargerValue_ShouldReturnPositive()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(55m);
        var temp2 = DhwTemperature.FromCelsius(40m);

        // When
        var result = temp1.CompareTo(temp2);

        // Then
        result.Should().BePositive();
    }

    [Fact]
    public void CompareTo_GivenEqualValue_ShouldReturnZero()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(48m);
        var temp2 = DhwTemperature.FromCelsius(48m);

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
        var temp1 = DhwTemperature.FromCelsius(48.5m);
        var temp2 = DhwTemperature.FromCelsius(48.5m);

        // When & Then
        temp1.Should().Be(temp2);
        (temp1 == temp2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenTwoTemperaturesWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(48.5m);
        var temp2 = DhwTemperature.FromCelsius(52.5m);

        // When & Then
        temp1.Should().NotBe(temp2);
        (temp1 != temp2).Should().BeTrue();
    }

    [Fact]
    public void GetHashCode_GivenTwoTemperaturesWithSameValue_ShouldHaveSameHashCode()
    {
        // Given
        var temp1 = DhwTemperature.FromCelsius(48.5m);
        var temp2 = DhwTemperature.FromCelsius(48.5m);

        // When & Then
        temp1.GetHashCode().Should().Be(temp2.GetHashCode());
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenTypicalValue_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = DhwTemperature.FromCelsius(48.5m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("48.5°C");
    }

    [Fact]
    public void ToString_GivenWholeNumber_ShouldFormatWithOneDecimalPlace()
    {
        // Given
        var temp = DhwTemperature.FromCelsius(55m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("55.0°C");
    }

    [Fact]
    public void ToString_GivenTypicalTargetTemperature_ShouldFormatCorrectly()
    {
        // Given
        var temp = DhwTemperature.FromCelsius(48m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("48.0°C");
    }

    [Fact]
    public void ToString_GivenHighTemperature_ShouldFormatCorrectly()
    {
        // Given
        var temp = DhwTemperature.FromCelsius(60m);

        // When
        var result = temp.ToString();

        // Then
        result.Should().Be("60.0°C");
    }

    #endregion
}
