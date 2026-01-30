using FluentAssertions;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class OperatingModeTests
{
    #region Enum Values

    [Fact]
    public void OperatingMode_ShouldHaveHeatOnlyWithValue0()
    {
        // Then
        ((int)OperatingMode.HeatOnly).Should().Be(0);
    }

    [Fact]
    public void OperatingMode_ShouldHaveCoolOnlyWithValue1()
    {
        // Then
        ((int)OperatingMode.CoolOnly).Should().Be(1);
    }

    [Fact]
    public void OperatingMode_ShouldHaveAutoHeatWithValue2()
    {
        // Then
        ((int)OperatingMode.AutoHeat).Should().Be(2);
    }

    [Fact]
    public void OperatingMode_ShouldHaveDhwOnlyWithValue3()
    {
        // Then
        ((int)OperatingMode.DhwOnly).Should().Be(3);
    }

    [Fact]
    public void OperatingMode_ShouldHaveHeatDhwWithValue4()
    {
        // Then
        ((int)OperatingMode.HeatDhw).Should().Be(4);
    }

    [Fact]
    public void OperatingMode_ShouldHaveCoolDhwWithValue5()
    {
        // Then
        ((int)OperatingMode.CoolDhw).Should().Be(5);
    }

    [Fact]
    public void OperatingMode_ShouldHaveAutoHeatDhwWithValue6()
    {
        // Then
        ((int)OperatingMode.AutoHeatDhw).Should().Be(6);
    }

    [Fact]
    public void OperatingMode_ShouldHaveAutoCoolWithValue7()
    {
        // Then
        ((int)OperatingMode.AutoCool).Should().Be(7);
    }

    [Fact]
    public void OperatingMode_ShouldHaveAutoCoolDhwWithValue8()
    {
        // Then
        ((int)OperatingMode.AutoCoolDhw).Should().Be(8);
    }

    #endregion

    #region Total Count

    [Fact]
    public void OperatingMode_ShouldHaveExactlyNineValues()
    {
        // Given
        var values = Enum.GetValues<OperatingMode>();

        // Then
        values.Should().HaveCount(9);
    }

    #endregion

    #region All Values Present

    [Theory]
    [InlineData(OperatingMode.HeatOnly)]
    [InlineData(OperatingMode.CoolOnly)]
    [InlineData(OperatingMode.AutoHeat)]
    [InlineData(OperatingMode.DhwOnly)]
    [InlineData(OperatingMode.HeatDhw)]
    [InlineData(OperatingMode.CoolDhw)]
    [InlineData(OperatingMode.AutoHeatDhw)]
    [InlineData(OperatingMode.AutoCool)]
    [InlineData(OperatingMode.AutoCoolDhw)]
    public void OperatingMode_GivenValidValue_ShouldBeDefinedInEnum(OperatingMode mode)
    {
        // Then
        Enum.IsDefined(mode).Should().BeTrue();
    }

    #endregion

    #region Parsing from Integer

    [Theory]
    [InlineData(0, OperatingMode.HeatOnly)]
    [InlineData(1, OperatingMode.CoolOnly)]
    [InlineData(2, OperatingMode.AutoHeat)]
    [InlineData(3, OperatingMode.DhwOnly)]
    [InlineData(4, OperatingMode.HeatDhw)]
    [InlineData(5, OperatingMode.CoolDhw)]
    [InlineData(6, OperatingMode.AutoHeatDhw)]
    [InlineData(7, OperatingMode.AutoCool)]
    [InlineData(8, OperatingMode.AutoCoolDhw)]
    public void OperatingMode_GivenInteger_ShouldCastToCorrectValue(int intValue, OperatingMode expected)
    {
        // When
        var mode = (OperatingMode)intValue;

        // Then
        mode.Should().Be(expected);
    }

    #endregion

    #region Parsing from String

    [Theory]
    [InlineData("HeatOnly", OperatingMode.HeatOnly)]
    [InlineData("CoolOnly", OperatingMode.CoolOnly)]
    [InlineData("AutoHeat", OperatingMode.AutoHeat)]
    [InlineData("DhwOnly", OperatingMode.DhwOnly)]
    [InlineData("HeatDhw", OperatingMode.HeatDhw)]
    [InlineData("CoolDhw", OperatingMode.CoolDhw)]
    [InlineData("AutoHeatDhw", OperatingMode.AutoHeatDhw)]
    [InlineData("AutoCool", OperatingMode.AutoCool)]
    [InlineData("AutoCoolDhw", OperatingMode.AutoCoolDhw)]
    public void OperatingMode_GivenValidString_ShouldParseCorrectly(string stringValue, OperatingMode expected)
    {
        // When
        var parsed = Enum.Parse<OperatingMode>(stringValue);

        // Then
        parsed.Should().Be(expected);
    }

    [Theory]
    [InlineData("heatonly")]
    [InlineData("HEATONLY")]
    [InlineData("DHWONLY")]
    public void OperatingMode_GivenCaseInsensitiveString_ShouldParseCorrectly(string stringValue)
    {
        // When
        var success = Enum.TryParse<OperatingMode>(stringValue, ignoreCase: true, out var result);

        // Then
        success.Should().BeTrue();
        Enum.IsDefined(result).Should().BeTrue();
    }

    #endregion

    #region ToString

    [Theory]
    [InlineData(OperatingMode.HeatOnly, "HeatOnly")]
    [InlineData(OperatingMode.CoolOnly, "CoolOnly")]
    [InlineData(OperatingMode.AutoHeat, "AutoHeat")]
    [InlineData(OperatingMode.DhwOnly, "DhwOnly")]
    [InlineData(OperatingMode.HeatDhw, "HeatDhw")]
    [InlineData(OperatingMode.CoolDhw, "CoolDhw")]
    [InlineData(OperatingMode.AutoHeatDhw, "AutoHeatDhw")]
    [InlineData(OperatingMode.AutoCool, "AutoCool")]
    [InlineData(OperatingMode.AutoCoolDhw, "AutoCoolDhw")]
    public void OperatingMode_ToString_ShouldReturnCorrectName(OperatingMode mode, string expected)
    {
        // When
        var result = mode.ToString();

        // Then
        result.Should().Be(expected);
    }

    #endregion

    #region Invalid Values

    [Theory]
    [InlineData(-1)]
    [InlineData(9)]
    [InlineData(100)]
    public void OperatingMode_GivenInvalidInteger_ShouldNotBeDefinedInEnum(int invalidValue)
    {
        // When
        var mode = (OperatingMode)invalidValue;

        // Then
        Enum.IsDefined(mode).Should().BeFalse();
    }

    #endregion

    #region Grouping Tests - Heating Modes

    [Theory]
    [InlineData(OperatingMode.HeatOnly)]
    [InlineData(OperatingMode.AutoHeat)]
    [InlineData(OperatingMode.HeatDhw)]
    [InlineData(OperatingMode.AutoHeatDhw)]
    public void OperatingMode_HeatingModes_ShouldContainHeatInName(OperatingMode mode)
    {
        // Then
        mode.ToString().Should().Contain("Heat");
    }

    #endregion

    #region Grouping Tests - Cooling Modes

    [Theory]
    [InlineData(OperatingMode.CoolOnly)]
    [InlineData(OperatingMode.CoolDhw)]
    [InlineData(OperatingMode.AutoCool)]
    [InlineData(OperatingMode.AutoCoolDhw)]
    public void OperatingMode_CoolingModes_ShouldContainCoolInName(OperatingMode mode)
    {
        // Then
        mode.ToString().Should().Contain("Cool");
    }

    #endregion

    #region Grouping Tests - DHW Modes

    [Theory]
    [InlineData(OperatingMode.DhwOnly)]
    [InlineData(OperatingMode.HeatDhw)]
    [InlineData(OperatingMode.CoolDhw)]
    [InlineData(OperatingMode.AutoHeatDhw)]
    [InlineData(OperatingMode.AutoCoolDhw)]
    public void OperatingMode_DhwModes_ShouldContainDhwInName(OperatingMode mode)
    {
        // Then
        mode.ToString().Should().Contain("Dhw");
    }

    #endregion
}
