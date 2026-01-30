using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PumpAhead.Adapters.Out.Migrations
{
    /// <inheritdoc />
    public partial class AddHeishaMonIntegration : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<bool>(
                name: "Defrost_IsActive",
                table: "HeatPumps",
                type: "bit",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<string>(
                name: "ErrorCode",
                table: "HeatPumps",
                type: "nvarchar(20)",
                maxLength: 20,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<decimal>(
                name: "Operations_CompressorHours",
                table: "HeatPumps",
                type: "decimal(8,2)",
                precision: 8,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<int>(
                name: "Operations_CompressorStarts",
                table: "HeatPumps",
                type: "int",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<decimal>(
                name: "Power_CoolConsumption",
                table: "HeatPumps",
                type: "decimal(7,2)",
                precision: 7,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<decimal>(
                name: "Power_CoolProduction",
                table: "HeatPumps",
                type: "decimal(7,2)",
                precision: 7,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<decimal>(
                name: "Power_DhwConsumption",
                table: "HeatPumps",
                type: "decimal(7,2)",
                precision: 7,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<decimal>(
                name: "Power_DhwProduction",
                table: "HeatPumps",
                type: "decimal(7,2)",
                precision: 7,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<decimal>(
                name: "Power_HeatConsumption",
                table: "HeatPumps",
                type: "decimal(7,2)",
                precision: 7,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<decimal>(
                name: "Power_HeatProduction",
                table: "HeatPumps",
                type: "decimal(7,2)",
                precision: 7,
                scale: 2,
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.CreateTable(
                name: "HeatPumpSnapshots",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    HeatPumpId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Timestamp = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    IsOn = table.Column<bool>(type: "bit", nullable: false),
                    OperatingMode = table.Column<int>(type: "int", nullable: false),
                    PumpFlow = table.Column<decimal>(type: "decimal(6,2)", precision: 6, scale: 2, nullable: false),
                    OutsideTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    CH_InletTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    CH_OutletTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    CH_TargetTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    DHW_ActualTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    DHW_TargetTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    Compressor_Frequency = table.Column<decimal>(type: "decimal(6,2)", precision: 6, scale: 2, nullable: false),
                    Power_HeatProduction = table.Column<decimal>(type: "decimal(7,2)", precision: 7, scale: 2, nullable: false),
                    Power_HeatConsumption = table.Column<decimal>(type: "decimal(7,2)", precision: 7, scale: 2, nullable: false),
                    Power_CoolProduction = table.Column<decimal>(type: "decimal(7,2)", precision: 7, scale: 2, nullable: false),
                    Power_CoolConsumption = table.Column<decimal>(type: "decimal(7,2)", precision: 7, scale: 2, nullable: false),
                    Power_DhwProduction = table.Column<decimal>(type: "decimal(7,2)", precision: 7, scale: 2, nullable: false),
                    Power_DhwConsumption = table.Column<decimal>(type: "decimal(7,2)", precision: 7, scale: 2, nullable: false),
                    Operations_CompressorHours = table.Column<decimal>(type: "decimal(8,2)", precision: 8, scale: 2, nullable: false),
                    Operations_CompressorStarts = table.Column<int>(type: "int", nullable: false),
                    Defrost_IsActive = table.Column<bool>(type: "bit", nullable: false),
                    ErrorCode = table.Column<string>(type: "nvarchar(20)", maxLength: 20, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_HeatPumpSnapshots", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_HeatPumpSnapshots_HeatPumpId_Timestamp",
                table: "HeatPumpSnapshots",
                columns: new[] { "HeatPumpId", "Timestamp" },
                descending: new[] { false, true });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "HeatPumpSnapshots");

            migrationBuilder.DropColumn(
                name: "Defrost_IsActive",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "ErrorCode",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Operations_CompressorHours",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Operations_CompressorStarts",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Power_CoolConsumption",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Power_CoolProduction",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Power_DhwConsumption",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Power_DhwProduction",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Power_HeatConsumption",
                table: "HeatPumps");

            migrationBuilder.DropColumn(
                name: "Power_HeatProduction",
                table: "HeatPumps");
        }
    }
}
