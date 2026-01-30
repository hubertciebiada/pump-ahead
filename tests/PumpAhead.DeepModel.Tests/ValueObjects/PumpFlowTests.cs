using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class PumpFlowTests
{
    #region Factory Method Tests

    [Fact]
    public void FromLitersPerMinute_GivenValidValue_ShouldCreatePumpFlowWithCorrectValue()
    {
        // Given
        var litersPerMinute = 15.5m;

        // When
        var pumpFlow = PumpFlow.FromLitersPerMinute(litersPerMinute);

        // Then
        pumpFlow.LitersPerMinute.Should().Be(15.5m);
    }

    [Fact]
    public void FromLitersPerMinute_GivenZero_ShouldCreatePumpFlowWithZeroValue()
    {
        // Given
        const decimal litersPerMinute = 0m;

        // When
        var pumpFlow = PumpFlow.FromLitersPerMinute(litersPerMinute);

        // Then
        pumpFlow.LitersPerMinute.Should().Be(0m);
    }

    [Theory]
    [InlineData(0.1)]
    [InlineData(5.0)]
    [InlineData(10.5)]
    [InlineData(20.0)]
    [InlineData(100.0)]
    public void FromLitersPerMinute_GivenVariousValidValues_ShouldCreatePumpFlow(decimal litersPerMinute)
    {
        // Given & When
        var pumpFlow = PumpFlow.FromLitersPerMinute(litersPerMinute);

        // Then
        pumpFlow.LitersPerMinute.Should().Be(litersPerMinute);
    }

    #endregion

    #region Validation Tests

    [Fact]
    public void FromLitersPerMinute_GivenNegativeValue_ShouldThrowArgumentOutOfRangeException()
    {
        // Given
        var negativeFlow = -1m;

        // When
        var act = () => PumpFlow.FromLitersPerMinute(negativeFlow);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>()
            .WithParameterName("litersPerMinute")
            .WithMessage("*Pump flow cannot be negative*");
    }

    [Theory]
    [InlineData(-0.1)]
    [InlineData(-1.0)]
    [InlineData(-10.0)]
    [InlineData(-100.0)]
    public void FromLitersPerMinute_GivenVariousNegativeValues_ShouldThrowArgumentOutOfRangeException(decimal negativeFlow)
    {
        // Given & When
        var act = () => PumpFlow.FromLitersPerMinute(negativeFlow);

        // Then
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    #endregion

    #region ToString Tests

    [Fact]
    public void ToString_GivenPumpFlow_ShouldFormatWithOneDecimalAndLPerMinUnit()
    {
        // Given
        var pumpFlow = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = pumpFlow.ToString();

        // Then
        result.Should().Be("15.0 l/min");
    }

    [Fact]
    public void ToString_GivenPumpFlowWithFractionalValue_ShouldFormatCorrectly()
    {
        // Given
        var pumpFlow = PumpFlow.FromLitersPerMinute(12.75m);

        // When
        var result = pumpFlow.ToString();

        // Then
        result.Should().Be("12.8 l/min");
    }

    [Fact]
    public void ToString_GivenZeroPumpFlow_ShouldFormatCorrectly()
    {
        // Given
        var pumpFlow = PumpFlow.FromLitersPerMinute(0m);

        // When
        var result = pumpFlow.ToString();

        // Then
        result.Should().Be("0.0 l/min");
    }

    [Fact]
    public void ToString_ShouldUseInvariantCulture()
    {
        // Given
        var pumpFlow = PumpFlow.FromLitersPerMinute(15.5m);

        // When
        var result = pumpFlow.ToString();

        // Then - uses dot as decimal separator (invariant culture)
        result.Should().Contain(".");
        result.Should().NotContain(",");
    }

    #endregion

    #region Comparison Operator Tests

    [Fact]
    public void GreaterThan_GivenFirstFlowIsGreater_ShouldReturnTrue()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(20.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 > flow2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThan_GivenFirstFlowIsLess_ShouldReturnFalse()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(10.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 > flow2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void LessThan_GivenFirstFlowIsLess_ShouldReturnTrue()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(10.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 < flow2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThan_GivenFirstFlowIsGreater_ShouldReturnFalse()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(20.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 < flow2;

        // Then
        result.Should().BeFalse();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenEqualFlows_ShouldReturnTrue()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(15.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 >= flow2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void GreaterThanOrEqual_GivenFirstFlowIsGreater_ShouldReturnTrue()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(20.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 >= flow2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenEqualFlows_ShouldReturnTrue()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(15.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 <= flow2;

        // Then
        result.Should().BeTrue();
    }

    [Fact]
    public void LessThanOrEqual_GivenFirstFlowIsLess_ShouldReturnTrue()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(10.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1 <= flow2;

        // Then
        result.Should().BeTrue();
    }

    #endregion

    #region IComparable Tests

    [Fact]
    public void CompareTo_GivenGreaterFlow_ShouldReturnPositive()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(20.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1.CompareTo(flow2);

        // Then
        result.Should().BePositive();
    }

    [Fact]
    public void CompareTo_GivenLesserFlow_ShouldReturnNegative()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(10.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1.CompareTo(flow2);

        // Then
        result.Should().BeNegative();
    }

    [Fact]
    public void CompareTo_GivenEqualFlows_ShouldReturnZero()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(15.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When
        var result = flow1.CompareTo(flow2);

        // Then
        result.Should().Be(0);
    }

    [Fact]
    public void OrderBy_GivenUnsortedFlows_ShouldSortCorrectly()
    {
        // Given
        var flows = new[]
        {
            PumpFlow.FromLitersPerMinute(25.0m),
            PumpFlow.FromLitersPerMinute(10.0m),
            PumpFlow.FromLitersPerMinute(15.0m),
            PumpFlow.FromLitersPerMinute(5.0m)
        };

        // When
        var ordered = flows.OrderBy(f => f).ToArray();

        // Then
        ordered[0].LitersPerMinute.Should().Be(5.0m);
        ordered[1].LitersPerMinute.Should().Be(10.0m);
        ordered[2].LitersPerMinute.Should().Be(15.0m);
        ordered[3].LitersPerMinute.Should().Be(25.0m);
    }

    [Fact]
    public void OrderByDescending_GivenUnsortedFlows_ShouldSortCorrectlyDescending()
    {
        // Given
        var flows = new[]
        {
            PumpFlow.FromLitersPerMinute(10.0m),
            PumpFlow.FromLitersPerMinute(25.0m),
            PumpFlow.FromLitersPerMinute(5.0m),
            PumpFlow.FromLitersPerMinute(15.0m)
        };

        // When
        var ordered = flows.OrderByDescending(f => f).ToArray();

        // Then
        ordered[0].LitersPerMinute.Should().Be(25.0m);
        ordered[1].LitersPerMinute.Should().Be(15.0m);
        ordered[2].LitersPerMinute.Should().Be(10.0m);
        ordered[3].LitersPerMinute.Should().Be(5.0m);
    }

    #endregion

    #region Equality Tests (record struct)

    [Fact]
    public void Equality_GivenTwoPumpFlowsWithSameValue_ShouldBeEqual()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(15.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When & Then
        flow1.Should().Be(flow2);
        (flow1 == flow2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenTwoPumpFlowsWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(15.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(20.0m);

        // When & Then
        flow1.Should().NotBe(flow2);
        (flow1 != flow2).Should().BeTrue();
    }

    [Fact]
    public void GetHashCode_GivenTwoPumpFlowsWithSameValue_ShouldHaveSameHashCode()
    {
        // Given
        var flow1 = PumpFlow.FromLitersPerMinute(15.0m);
        var flow2 = PumpFlow.FromLitersPerMinute(15.0m);

        // When & Then
        flow1.GetHashCode().Should().Be(flow2.GetHashCode());
    }

    #endregion
}
