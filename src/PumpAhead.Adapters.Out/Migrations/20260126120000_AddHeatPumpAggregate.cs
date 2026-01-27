using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PumpAhead.Adapters.Out.Migrations
{
    /// <inheritdoc />
    public partial class AddHeatPumpAggregate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "HeatPumps",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Model = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: false),
                    LastSyncTime = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    OperatingMode = table.Column<int>(type: "int", nullable: false),
                    CH_FlowTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    CH_ReturnTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    CH_Offset = table.Column<decimal>(type: "decimal(4,2)", precision: 4, scale: 2, nullable: false),
                    DHW_ActualTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    DHW_TargetTemperature = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    DHW_Delta = table.Column<decimal>(type: "decimal(4,2)", precision: 4, scale: 2, nullable: false),
                    Compressor_Frequency = table.Column<decimal>(type: "decimal(6,2)", precision: 6, scale: 2, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_HeatPumps", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_HeatPumps_LastSyncTime",
                table: "HeatPumps",
                column: "LastSyncTime",
                descending: new[] { true });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "HeatPumps");
        }
    }
}
