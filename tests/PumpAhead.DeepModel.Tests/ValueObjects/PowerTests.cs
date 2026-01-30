using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class PowerTests
{
    private const decimal ZeroWatts = 0m;
    private const decimal NegativeWatts = -1m;
    private const decimal LargeNegativeWatts = -9999.99m;
    private const decimal FiveHundredWatts = 500m;
    private const decimal OneThousandWatts = 1000m;
    private const decimal FifteenHundredWatts = 1500m;
    private const decimal TwoThousandWatts = 2000m;
    private const decimal TwoThousandFiveHundredWatts = 2500m;
    private const decimal ThreeThousandWatts = 3000m;
    private const decimal DecimalWatts = 1234.56m;
    private const decimal ThreeHundredWatts = 300m;
    private const decimal SevenHundredWatts = 700m;
    private const decimal HalfKilowatt = 0.5m;
    private const decimal OneKilowatt = 1m;
    private const decimal TwoAndHalfKilowatts = 2.5m;

    private const string PowerCannotBeNegativeMessage = "*Power cannot be negative*";
    private const string FiveHundredWattsFormatted = "500 W";
    private const string OneKilowattFormatted = "1.00 kW";
    private const string TwoAndHalfKilowattsFormatted = "2.50 kW";
    private const string ZeroWattsFormatted = "0 W";

    #region FromWatts - Valid Values

    [Fact]
    public void FromWatts_GivenZeroWatts_ShouldCreatePowerWithZeroValue()
    {
        // Given
        var watts = ZeroWatts;

        // When
        var power = Power.FromWatts(watts);

        // Then
        power.Watts.Should().Be(ZeroWatts);
    }

    [Fact]
    public void FromWatts_GivenPositiveWatts_ShouldCreatePowerWithCorrectValue()
    {
        // Given
        var watts = FifteenHundredWatts;

        // When
        var power = Power.FromWatts(watts);

        // Then
        power.Watts.Should().Be(FifteenHundredWatts);
    }

    [Fact]
    public void FromWatts_GivenDecimalWatts_ShouldPreservePrecision()
    {
        // Given
        var watts = DecimalWatts;

        // When
        var power = Power.FromWatts(watts);

        // Then
        power.Watts.Should().Be(DecimalWatts);
    }

    #endregion

    #region FromWatts - Invalid Values

    [Fact]
    public void FromWatts_GivenNegativeWatts_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        var watts = NegativeWatts;

        // When
        var act = () => Power.FromWatts(watts);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithMessage(PowerCannotBeNegativeMessage);
    }

    [Fact]
    public void FromWatts_GivenLargeNegativeWatts_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        var watts = LargeNegativeWatts;

        // When
        var act = () => Power.FromWatts(watts);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    #endregion

    #region Power.Zero

    [Fact]
    public void Zero_ShouldReturnPowerWithZeroWatts()
    {
        // When
        var power = Power.Zero;

        // Then
        power.Watts.Should().Be(ZeroWatts);
    }

    [Fact]
    public void Zero_ShouldBeEqualToFromWattsZero()
    {
        // Given
        var fromWatts = Power.FromWatts(ZeroWatts);

        // When
        var zero = Power.Zero;

        // Then
        zero.Should().Be(fromWatts);
    }

    #endregion

    #region Kilowatts Conversion

    [Fact]
    public void Kilowatts_GivenWattsLessThanThousand_ShouldReturnFraction()
    {
        // Given
        var power = Power.FromWatts(FiveHundredWatts);

        // When
        var kilowatts = power.Kilowatts;

        // Then
        kilowatts.Should().Be(HalfKilowatt);
    }

    [Fact]
    public void Kilowatts_GivenExactlyThousandWatts_ShouldReturnOne()
    {
        // Given
        var power = Power.FromWatts(OneThousandWatts);

        // When
        var kilowatts = power.Kilowatts;

        // Then
        kilowatts.Should().Be(OneKilowatt);
    }

    [Fact]
    public void Kilowatts_GivenMultipleThousandWatts_ShouldReturnCorrectKilowatts()
    {
        // Given
        var power = Power.FromWatts(TwoThousandFiveHundredWatts);

        // When
        var kilowatts = power.Kilowatts;

        // Then
        kilowatts.Should().Be(TwoAndHalfKilowatts);
    }

    [Fact]
    public void Kilowatts_GivenZeroWatts_ShouldReturnZero()
    {
        // Given
        var power = Power.Zero;

        // When
        var kilowatts = power.Kilowatts;

        // Then
        kilowatts.Should().Be(ZeroWatts);
    }

    #endregion

    #region Addition Operator

    [Fact]
    public void AdditionOperator_GivenTwoPowers_ShouldReturnSumOfWatts()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power1 + power2;

        // Then
        result.Watts.Should().Be(FifteenHundredWatts);
    }

    [Fact]
    public void AdditionOperator_GivenZeroPower_ShouldReturnOriginalValue()
    {
        // Given
        var power = Power.FromWatts(OneThousandWatts);
        var zero = Power.Zero;

        // When
        var result = power + zero;

        // Then
        result.Watts.Should().Be(OneThousandWatts);
    }

    [Fact]
    public void AdditionOperator_GivenTwoZeros_ShouldReturnZero()
    {
        // Given
        var zero1 = Power.Zero;
        var zero2 = Power.Zero;

        // When
        var result = zero1 + zero2;

        // Then
        result.Watts.Should().Be(ZeroWatts);
    }

    [Fact]
    public void AdditionOperator_ShouldBeCommutative()
    {
        // Given
        var power1 = Power.FromWatts(ThreeHundredWatts);
        var power2 = Power.FromWatts(SevenHundredWatts);

        // When
        var result1 = power1 + power2;
        var result2 = power2 + power1;

        // Then
        result1.Should().Be(result2);
    }

    #endregion

    #region Greater Than Operator

    [Fact]
    public void GreaterThanOperator_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power1 > power2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOperator_GivenFirstIsLess_ShouldReturnFalse()
    {
        // Given
        var power1 = Power.FromWatts(FiveHundredWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 > power2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThanOperator_GivenEqualValues_ShouldReturnFalse()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 > power2;

        // Then
        result.Should().BeFalse();
    }

    #endregion

    #region Less Than Operator

    [Fact]
    public void LessThanOperator_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var power1 = Power.FromWatts(FiveHundredWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 < power2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOperator_GivenFirstIsGreater_ShouldReturnFalse()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power1 < power2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void LessThanOperator_GivenEqualValues_ShouldReturnFalse()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 < power2;

        // Then
        result.Should().BeFalse();
    }

    #endregion

    #region Greater Than Or Equal Operator

    [Fact]
    public void GreaterThanOrEqualOperator_GivenFirstIsGreater_ShouldReturnTrue()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power1 >= power2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqualOperator_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 >= power2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqualOperator_GivenFirstIsLess_ShouldReturnFalse()
    {
        // Given
        var power1 = Power.FromWatts(FiveHundredWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 >= power2;

        // Then
        result.Should().BeFalse();
    }

    #endregion

    #region Less Than Or Equal Operator

    [Fact]
    public void LessThanOrEqualOperator_GivenFirstIsLess_ShouldReturnTrue()
    {
        // Given
        var power1 = Power.FromWatts(FiveHundredWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 <= power2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqualOperator_GivenEqualValues_ShouldReturnTrue()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1 <= power2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqualOperator_GivenFirstIsGreater_ShouldReturnFalse()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power1 <= power2;

        // Then
        result.Should().BeFalse();
    }

    #endregion

    #region CompareTo

    [Fact]
    public void CompareTo_GivenGreaterValue_ShouldReturnPositive()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power1.CompareTo(power2);

        // Then
        result.Should().BePositive();
    }

    [Fact]
    public void CompareTo_GivenLesserValue_ShouldReturnNegative()
    {
        // Given
        var power1 = Power.FromWatts(FiveHundredWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1.CompareTo(power2);

        // Then
        result.Should().BeNegative();
    }

    [Fact]
    public void CompareTo_GivenEqualValue_ShouldReturnZero()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // When
        var result = power1.CompareTo(power2);

        // Then
        result.Should().Be(0);
    }

    [Fact]
    public void CompareTo_ShouldAllowSorting()
    {
        // Given
        var powers = new[]
        {
            Power.FromWatts(ThreeThousandWatts),
            Power.FromWatts(OneThousandWatts),
            Power.FromWatts(TwoThousandWatts)
        };

        // When
        var sorted = powers.OrderBy(p => p).ToArray();

        // Then
        sorted[0].Watts.Should().Be(OneThousandWatts);
        sorted[1].Watts.Should().Be(TwoThousandWatts);
        sorted[2].Watts.Should().Be(ThreeThousandWatts);
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenWattsLessThanThousand_ShouldFormatAsWatts()
    {
        // Given
        var power = Power.FromWatts(FiveHundredWatts);

        // When
        var result = power.ToString();

        // Then
        result.Should().Be(FiveHundredWattsFormatted);
    }

    [Fact]
    public void ToString_GivenExactlyThousandWatts_ShouldFormatAsKilowatts()
    {
        // Given
        var power = Power.FromWatts(OneThousandWatts);

        // When
        var result = power.ToString();

        // Then
        result.Should().Be(OneKilowattFormatted);
    }

    [Fact]
    public void ToString_GivenWattsAboveThousand_ShouldFormatAsKilowatts()
    {
        // Given
        var power = Power.FromWatts(TwoThousandFiveHundredWatts);

        // When
        var result = power.ToString();

        // Then
        result.Should().Be(TwoAndHalfKilowattsFormatted);
    }

    [Fact]
    public void ToString_GivenZeroWatts_ShouldFormatAsWatts()
    {
        // Given
        var power = Power.Zero;

        // When
        var result = power.ToString();

        // Then
        result.Should().Be(ZeroWattsFormatted);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenSameWatts_ShouldBeEqual()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(OneThousandWatts);

        // Then
        power1.Should().Be(power2);
    }

    [Fact]
    public void Equality_GivenDifferentWatts_ShouldNotBeEqual()
    {
        // Given
        var power1 = Power.FromWatts(OneThousandWatts);
        var power2 = Power.FromWatts(TwoThousandWatts);

        // Then
        power1.Should().NotBe(power2);
    }

    #endregion
}
