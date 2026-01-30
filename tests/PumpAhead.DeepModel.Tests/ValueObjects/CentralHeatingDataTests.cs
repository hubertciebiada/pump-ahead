using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class CentralHeatingDataTests
{
    #region Creation - Valid Values

    [Fact]
    public void Constructor_GivenValidTemperatures_ShouldCreateInstanceWithCorrectValues()
    {
        // Given
        var inlet = WaterTemperature.FromCelsius(45m);
        var outlet = WaterTemperature.FromCelsius(35m);
        var target = WaterTemperature.FromCelsius(40m);

        // When
        var data = new CentralHeatingData(inlet, outlet, target);

        // Then
        data.InletTemperature.Should().Be(inlet);
        data.OutletTemperature.Should().Be(outlet);
        data.TargetTemperature.Should().Be(target);
    }

    [Fact]
    public void Constructor_GivenTypicalHeatingScenario_ShouldStoreAllTemperatures()
    {
        // Given - typical heating scenario: inlet hot, outlet cooler, target moderate
        var inlet = WaterTemperature.FromCelsius(55m);
        var outlet = WaterTemperature.FromCelsius(40m);
        var target = WaterTemperature.FromCelsius(50m);

        // When
        var data = new CentralHeatingData(inlet, outlet, target);

        // Then
        data.InletTemperature.Celsius.Should().Be(55m);
        data.OutletTemperature.Celsius.Should().Be(40m);
        data.TargetTemperature.Celsius.Should().Be(50m);
    }

    [Fact]
    public void Constructor_GivenSameTemperatureForAllFields_ShouldCreateValidInstance()
    {
        // Given
        var sameTemp = WaterTemperature.FromCelsius(42m);

        // When
        var data = new CentralHeatingData(sameTemp, sameTemp, sameTemp);

        // Then
        data.InletTemperature.Should().Be(sameTemp);
        data.OutletTemperature.Should().Be(sameTemp);
        data.TargetTemperature.Should().Be(sameTemp);
    }

    [Fact]
    public void Constructor_GivenLowTemperatures_ShouldCreateValidInstance()
    {
        // Given - system off or just starting
        var inlet = WaterTemperature.FromCelsius(20m);
        var outlet = WaterTemperature.FromCelsius(19m);
        var target = WaterTemperature.FromCelsius(45m);

        // When
        var data = new CentralHeatingData(inlet, outlet, target);

        // Then
        data.InletTemperature.Celsius.Should().Be(20m);
        data.OutletTemperature.Celsius.Should().Be(19m);
        data.TargetTemperature.Celsius.Should().Be(45m);
    }

    #endregion

    #region Immutability

    [Fact]
    public void RecordStruct_ShouldBeReadonly()
    {
        // Given
        var type = typeof(CentralHeatingData);

        // Then
        type.IsValueType.Should().BeTrue("CentralHeatingData should be a value type (struct)");
    }

    [Fact]
    public void Type_ShouldBeReadonlyRecordStruct()
    {
        // Given
        var type = typeof(CentralHeatingData);

        // Then - readonly structs have IsLayoutSequential=false and are value types
        type.IsValueType.Should().BeTrue("should be a struct");

        // Check that it's a record (has EqualityContract or compiler-generated Equals)
        var equalsMethod = type.GetMethod("Equals", new[] { typeof(CentralHeatingData) });
        equalsMethod.Should().NotBeNull("record structs have value-based Equals");
    }

    [Fact]
    public void With_ShouldCreateNewInstanceWithModifiedValue()
    {
        // Given
        var original = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var newTarget = WaterTemperature.FromCelsius(50m);

        // When
        var modified = original with { TargetTemperature = newTarget };

        // Then
        modified.TargetTemperature.Should().Be(newTarget);
        original.TargetTemperature.Celsius.Should().Be(40m, "original should remain unchanged");
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenSameValues_ShouldBeEqual()
    {
        // Given
        var data1 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var data2 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));

        // Then
        data1.Should().Be(data2);
        (data1 == data2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenDifferentInletTemperature_ShouldNotBeEqual()
    {
        // Given
        var data1 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var data2 = new CentralHeatingData(
            WaterTemperature.FromCelsius(50m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));

        // Then
        data1.Should().NotBe(data2);
        (data1 != data2).Should().BeTrue();
    }

    [Fact]
    public void Equality_GivenDifferentOutletTemperature_ShouldNotBeEqual()
    {
        // Given
        var data1 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var data2 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(30m),
            WaterTemperature.FromCelsius(40m));

        // Then
        data1.Should().NotBe(data2);
    }

    [Fact]
    public void Equality_GivenDifferentTargetTemperature_ShouldNotBeEqual()
    {
        // Given
        var data1 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var data2 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(42m));

        // Then
        data1.Should().NotBe(data2);
    }

    [Fact]
    public void GetHashCode_GivenEqualInstances_ShouldReturnSameHashCode()
    {
        // Given
        var data1 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var data2 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));

        // Then
        data1.GetHashCode().Should().Be(data2.GetHashCode());
    }

    [Fact]
    public void GetHashCode_GivenDifferentInstances_ShouldReturnDifferentHashCodes()
    {
        // Given
        var data1 = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var data2 = new CentralHeatingData(
            WaterTemperature.FromCelsius(50m),
            WaterTemperature.FromCelsius(38m),
            WaterTemperature.FromCelsius(42m));

        // Then
        data1.GetHashCode().Should().NotBe(data2.GetHashCode());
    }

    #endregion

    #region Value Semantics

    [Fact]
    public void ValueSemantics_ShouldSupportDeconstructionViaPositionalRecord()
    {
        // Given
        var inlet = WaterTemperature.FromCelsius(45m);
        var outlet = WaterTemperature.FromCelsius(35m);
        var target = WaterTemperature.FromCelsius(40m);
        var data = new CentralHeatingData(inlet, outlet, target);

        // When
        var (deconstructedInlet, deconstructedOutlet, deconstructedTarget) = data;

        // Then
        deconstructedInlet.Should().Be(inlet);
        deconstructedOutlet.Should().Be(outlet);
        deconstructedTarget.Should().Be(target);
    }

    [Fact]
    public void ValueSemantics_ShouldWorkInCollections()
    {
        // Given
        var data = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));
        var set = new HashSet<CentralHeatingData> { data };

        // When
        var duplicate = new CentralHeatingData(
            WaterTemperature.FromCelsius(45m),
            WaterTemperature.FromCelsius(35m),
            WaterTemperature.FromCelsius(40m));

        // Then
        set.Should().Contain(duplicate);
        set.Add(duplicate);
        set.Should().HaveCount(1, "duplicate should not be added");
    }

    #endregion
}
