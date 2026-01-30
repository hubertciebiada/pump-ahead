using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class FrequencyTests
{
    private const decimal ZeroHertz = 0m;
    private const decimal FiftyHertz = 50.0m;
    private const decimal SixtyHertz = 60.0m;
    private const decimal NegativeOneHertz = -1m;
    private const decimal FractionalHertz = 48.75m;
    private const decimal FiftyPointFiveHertz = 50.5m;

    private const string FrequencyCannotBeNegativeMessage = "*Frequency cannot be negative*";
    private const string HertzParameterName = "hertz";
    private const string FiftyHertzFormatted = "50.0 Hz";
    private const string FractionalHertzFormatted = "48.8 Hz";
    private const string ZeroHertzFormatted = "0.0 Hz";

    #region Factory Method Tests

    [Fact]
    public void FromHertz_GivenValidValue_ShouldCreateFrequencyWithCorrectValue()
    {
        // Given
        var hertz = FiftyHertz;

        // When
        var frequency = Frequency.FromHertz(hertz);

        // Then
        frequency.Hertz.Should().Be(FiftyHertz);
    }

    [Fact]
    public void FromHertz_GivenZero_ShouldCreateFrequencyWithZeroValue()
    {
        // Given
        var hertz = ZeroHertz;

        // When
        var frequency = Frequency.FromHertz(hertz);

        // Then
        frequency.Hertz.Should().Be(ZeroHertz);
    }

    [Theory]
    [InlineData(0.1)]
    [InlineData(25.5)]
    [InlineData(50.0)]
    [InlineData(60.0)]
    [InlineData(100.0)]
    public void FromHertz_GivenVariousValidValues_ShouldCreateFrequency(decimal hertz)
    {
        // Given & When
        var frequency = Frequency.FromHertz(hertz);

        // Then
        frequency.Hertz.Should().Be(hertz);
    }

    #endregion

    #region Validation Tests

    [Fact]
    public void FromHertz_GivenNegativeValue_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        var negativeHertz = NegativeOneHertz;

        // When
        var act = () => Frequency.FromHertz(negativeHertz);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithParameterName(HertzParameterName)
            .WithMessage(FrequencyCannotBeNegativeMessage);
    }

    [Theory]
    [InlineData(-0.1)]
    [InlineData(-1.0)]
    [InlineData(-50.0)]
    [InlineData(-100.0)]
    public void FromHertz_GivenVariousNegativeValues_ShouldThrowArgumentOutOfRangeException(decimal negativeHertz)
    {
        // Given & When
        var act = () => Frequency.FromHertz(negativeHertz);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    #endregion

    #region ToString Tests

    [Fact]
    public void ToString_GivenFrequency_ShouldFormatWithOneDecimalAndHzUnit()
    {
        // Given
        var frequency = Frequency.FromHertz(FiftyHertz);

        // When
        var result = frequency.ToString();

        // Then
        result.Should().Be(FiftyHertzFormatted);
    }

    [Fact]
    public void ToString_GivenFrequencyWithFractionalValue_ShouldFormatCorrectly()
    {
        // Given
        var frequency = Frequency.FromHertz(FractionalHertz);

        // When
        var result = frequency.ToString();

        // Then
        result.Should().Be(FractionalHertzFormatted);
    }

    [Fact]
    public void ToString_GivenZeroFrequency_ShouldFormatCorrectly()
    {
        // Given
        var frequency = Frequency.FromHertz(ZeroHertz);

        // When
        var result = frequency.ToString();

        // Then
        result.Should().Be(ZeroHertzFormatted);
    }

    [Fact]
    public void ToString_ShouldUseInvariantCulture()
    {
        // Given
        var frequency = Frequency.FromHertz(FiftyPointFiveHertz);

        // When
        var result = frequency.ToString();

        // Then - uses dot as decimal separator (invariant culture)
        result.Should().Contain(".");
        result.Should().NotContain(",");
    }

    #endregion

    #region Equality Tests (record struct)

    [Fact]
    public void Equality_GivenTwoFrequenciesWithSameValue_ShouldBeEqual()
    {
        // Given
        var frequency1 = Frequency.FromHertz(FiftyHertz);
        var frequency2 = Frequency.FromHertz(FiftyHertz);

        // When & Then
        frequency1.Should().Be(frequency2);
        (frequency1 == frequency2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenTwoFrequenciesWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var frequency1 = Frequency.FromHertz(FiftyHertz);
        var frequency2 = Frequency.FromHertz(SixtyHertz);

        // When & Then
        frequency1.Should().NotBe(frequency2);
        (frequency1 != frequency2).Should().BeTrue();
    }

    [Fact]
    public void GetHashCode_GivenTwoFrequenciesWithSameValue_ShouldHaveSameHashCode()
    {
        // Given
        var frequency1 = Frequency.FromHertz(FiftyHertz);
        var frequency2 = Frequency.FromHertz(FiftyHertz);

        // When & Then
        frequency1.GetHashCode().Should().Be(frequency2.GetHashCode());
    }

    #endregion
}
