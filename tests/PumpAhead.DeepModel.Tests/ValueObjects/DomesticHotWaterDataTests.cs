using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class DomesticHotWaterDataTests
{
    #region Creation - Valid Values

    [Fact]
    public void Constructor_GivenValidTemperatures_ShouldCreateInstanceWithCorrectValues()
    {
        // Given
        var actual = DhwTemperature.FromCelsius(48m);
        var target = DhwTemperature.FromCelsius(50m);

        // When
        var data = new DomesticHotWaterData(actual, target);

        // Then
        data.ActualTemperature.Should().Be(actual);
        data.TargetTemperature.Should().Be(target);
    }

    [Fact]
    public void Constructor_GivenTypicalDhwScenario_ShouldStoreAllTemperatures()
    {
        // Given - typical DHW scenario: heating towards target
        var actual = DhwTemperature.FromCelsius(45m);
        var target = DhwTemperature.FromCelsius(55m);

        // When
        var data = new DomesticHotWaterData(actual, target);

        // Then
        data.ActualTemperature.Celsius.Should().Be(45m);
        data.TargetTemperature.Celsius.Should().Be(55m);
    }

    [Fact]
    public void Constructor_GivenActualAboveTarget_ShouldCreateValidInstance()
    {
        // Given - actual can be above target (e.g., cooling down)
        var actual = DhwTemperature.FromCelsius(58m);
        var target = DhwTemperature.FromCelsius(50m);

        // When
        var data = new DomesticHotWaterData(actual, target);

        // Then
        data.ActualTemperature.Celsius.Should().Be(58m);
        data.TargetTemperature.Celsius.Should().Be(50m);
    }

    [Fact]
    public void Constructor_GivenEqualActualAndTarget_ShouldCreateValidInstance()
    {
        // Given - target reached
        var temperature = DhwTemperature.FromCelsius(50m);

        // When
        var data = new DomesticHotWaterData(temperature, temperature);

        // Then
        data.ActualTemperature.Should().Be(temperature);
        data.TargetTemperature.Should().Be(temperature);
    }

    [Fact]
    public void Constructor_GivenLowActualTemperature_ShouldCreateValidInstance()
    {
        // Given - cold water, system starting
        var actual = DhwTemperature.FromCelsius(15m);
        var target = DhwTemperature.FromCelsius(55m);

        // When
        var data = new DomesticHotWaterData(actual, target);

        // Then
        data.ActualTemperature.Celsius.Should().Be(15m);
        data.TargetTemperature.Celsius.Should().Be(55m);
    }

    #endregion

    #region Immutability

    [Fact]
    public void RecordStruct_ShouldBeReadonly()
    {
        // Given
        var type = typeof(DomesticHotWaterData);

        // Then
        type.IsValueType.Should().BeTrue("DomesticHotWaterData should be a value type (struct)");
    }

    [Fact]
    public void Type_ShouldBeReadonlyRecordStruct()
    {
        // Given
        var type = typeof(DomesticHotWaterData);

        // Then - readonly structs have IsLayoutSequential=false and are value types
        type.IsValueType.Should().BeTrue("should be a struct");

        // Check that it's a record (has compiler-generated Equals)
        var equalsMethod = type.GetMethod("Equals", new[] { typeof(DomesticHotWaterData) });
        equalsMethod.Should().NotBeNull("record structs have value-based Equals");
    }

    [Fact]
    public void With_ShouldCreateNewInstanceWithModifiedValue()
    {
        // Given
        var original = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(45m),
            DhwTemperature.FromCelsius(50m));
        var newTarget = DhwTemperature.FromCelsius(55m);

        // When
        var modified = original with { TargetTemperature = newTarget };

        // Then
        modified.TargetTemperature.Should().Be(newTarget);
        original.TargetTemperature.Celsius.Should().Be(50m, "original should remain unchanged");
    }

    [Fact]
    public void With_ShouldAllowModifyingActualTemperature()
    {
        // Given
        var original = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(45m),
            DhwTemperature.FromCelsius(50m));
        var newActual = DhwTemperature.FromCelsius(48m);

        // When
        var modified = original with { ActualTemperature = newActual };

        // Then
        modified.ActualTemperature.Should().Be(newActual);
        original.ActualTemperature.Celsius.Should().Be(45m, "original should remain unchanged");
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenSameValues_ShouldBeEqual()
    {
        // Given
        var data1 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var data2 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));

        // Then
        data1.Should().Be(data2);
        (data1 == data2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenDifferentActualTemperature_ShouldNotBeEqual()
    {
        // Given
        var data1 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var data2 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(45m),
            DhwTemperature.FromCelsius(50m));

        // Then
        data1.Should().NotBe(data2);
        (data1 != data2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenDifferentTargetTemperature_ShouldNotBeEqual()
    {
        // Given
        var data1 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var data2 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(55m));

        // Then
        data1.Should().NotBe(data2);
    }

    [Fact]
    public void Equality_GivenSwappedActualAndTarget_ShouldNotBeEqual()
    {
        // Given - values swapped between actual and target
        var data1 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var data2 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(50m),
            DhwTemperature.FromCelsius(48m));

        // Then
        data1.Should().NotBe(data2);
    }

    [Fact]
    public void GetHashCode_GivenEqualInstances_ShouldReturnSameHashCode()
    {
        // Given
        var data1 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var data2 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));

        // Then
        data1.GetHashCode().Should().Be(data2.GetHashCode());
    }

    [Fact]
    public void GetHashCode_GivenDifferentInstances_ShouldReturnDifferentHashCodes()
    {
        // Given
        var data1 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var data2 = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(45m),
            DhwTemperature.FromCelsius(55m));

        // Then
        data1.GetHashCode().Should().NotBe(data2.GetHashCode());
    }

    #endregion

    #region Value Semantics

    [Fact]
    public void ValueSemantics_ShouldSupportDeconstructionViaPositionalRecord()
    {
        // Given
        var actual = DhwTemperature.FromCelsius(48m);
        var target = DhwTemperature.FromCelsius(50m);
        var data = new DomesticHotWaterData(actual, target);

        // When
        var (deconstructedActual, deconstructedTarget) = data;

        // Then
        deconstructedActual.Should().Be(actual);
        deconstructedTarget.Should().Be(target);
    }

    [Fact]
    public void ValueSemantics_ShouldWorkInCollections()
    {
        // Given
        var data = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var set = new HashSet<DomesticHotWaterData> { data };

        // When
        var duplicate = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));

        // Then
        set.Should().Contain(duplicate);
        set.Add(duplicate);
        set.Should().HaveCount(1, "duplicate should not be added");
    }

    [Fact]
    public void ValueSemantics_ShouldWorkAsDictionaryKey()
    {
        // Given
        var data = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));
        var dictionary = new Dictionary<DomesticHotWaterData, string>
        {
            { data, "test value" }
        };

        // When
        var lookupKey = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(48m),
            DhwTemperature.FromCelsius(50m));

        // Then
        dictionary.Should().ContainKey(lookupKey);
        dictionary[lookupKey].Should().Be("test value");
    }

    #endregion
}
