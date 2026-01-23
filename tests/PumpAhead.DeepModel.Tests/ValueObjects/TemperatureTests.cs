using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class TemperatureTests
{
    [Fact]
    public void FromCelsius_CreatesTemperatureWithCorrectValue()
    {
        var temp = Temperature.FromCelsius(21.5m);

        Assert.Equal(21.5m, temp.Celsius);
    }

    [Fact]
    public void ToString_FormatsCorrectly()
    {
        var temp = Temperature.FromCelsius(21.5m);

        Assert.Equal("21.5°C", temp.ToString());
    }

    [Fact]
    public void Addition_AddsTwoTemperatures()
    {
        var temp1 = Temperature.FromCelsius(20m);
        var temp2 = Temperature.FromCelsius(5m);

        var result = temp1 + temp2;

        Assert.Equal(25m, result.Celsius);
    }

    [Fact]
    public void Subtraction_SubtractsTwoTemperatures()
    {
        var temp1 = Temperature.FromCelsius(25m);
        var temp2 = Temperature.FromCelsius(5m);

        var result = temp1 - temp2;

        Assert.Equal(20m, result.Celsius);
    }

    [Fact]
    public void GreaterThan_ReturnsTrue_WhenFirstIsGreater()
    {
        var temp1 = Temperature.FromCelsius(25m);
        var temp2 = Temperature.FromCelsius(20m);

        Assert.True(temp1 > temp2);
    }

    [Fact]
    public void LessThan_ReturnsTrue_WhenFirstIsLess()
    {
        var temp1 = Temperature.FromCelsius(15m);
        var temp2 = Temperature.FromCelsius(20m);

        Assert.True(temp1 < temp2);
    }

    [Fact]
    public void Clamp_ReturnsMin_WhenBelowMin()
    {
        var temp = Temperature.FromCelsius(15m);
        var min = Temperature.FromCelsius(20m);
        var max = Temperature.FromCelsius(35m);

        var result = temp.Clamp(min, max);

        Assert.Equal(20m, result.Celsius);
    }

    [Fact]
    public void Clamp_ReturnsMax_WhenAboveMax()
    {
        var temp = Temperature.FromCelsius(40m);
        var min = Temperature.FromCelsius(20m);
        var max = Temperature.FromCelsius(35m);

        var result = temp.Clamp(min, max);

        Assert.Equal(35m, result.Celsius);
    }

    [Fact]
    public void Clamp_ReturnsSame_WhenWithinRange()
    {
        var temp = Temperature.FromCelsius(25m);
        var min = Temperature.FromCelsius(20m);
        var max = Temperature.FromCelsius(35m);

        var result = temp.Clamp(min, max);

        Assert.Equal(25m, result.Celsius);
    }

    [Fact]
    public void Equality_TwoTemperaturesWithSameValue_AreEqual()
    {
        var temp1 = Temperature.FromCelsius(21.5m);
        var temp2 = Temperature.FromCelsius(21.5m);

        Assert.Equal(temp1, temp2);
    }

    [Fact]
    public void CompareTo_OrdersCorrectly()
    {
        var temps = new[]
        {
            Temperature.FromCelsius(25m),
            Temperature.FromCelsius(15m),
            Temperature.FromCelsius(20m)
        };

        var ordered = temps.OrderBy(t => t).ToArray();

        Assert.Equal(15m, ordered[0].Celsius);
        Assert.Equal(20m, ordered[1].Celsius);
        Assert.Equal(25m, ordered[2].Celsius);
    }
}
