using Microsoft.JSInterop;

namespace PumpAhead.Adapters.Gui.Services;

public sealed class LightweightChartsService : IAsyncDisposable
{
    private readonly Lazy<Task<IJSObjectReference>> _moduleTask;
    private readonly List<string> _chartIds = [];

    public LightweightChartsService(IJSRuntime jsRuntime)
    {
        _moduleTask = new(() => jsRuntime.InvokeAsync<IJSObjectReference>(
            "import", "./_content/PumpAhead.Adapters.Gui/js/charts.js").AsTask());
    }

    public async Task<string?> InitializeChartAsync(string containerId, ChartOptions? options = null)
    {
        var module = await _moduleTask.Value;
        options ??= ChartOptions.Default;

        var chartId = await module.InvokeAsync<string?>("initializeChart", containerId, new
        {
            backgroundColor = options.BackgroundColor,
            textColor = options.TextColor,
            gridColor = options.GridColor,
        });

        if (chartId != null)
        {
            _chartIds.Add(chartId);
        }

        return chartId;
    }

    public async Task<string?> AddLineSeriesAsync(string chartId, LineSeriesOptions options)
    {
        var module = await _moduleTask.Value;
        return await module.InvokeAsync<string?>("addLineSeries", chartId, new
        {
            color = options.Color,
            lineWidth = options.LineWidth,
            title = options.Title,
            lineStyle = options.LineStyle,
            priceRangeMin = options.PriceRangeMin,
            priceRangeMax = options.PriceRangeMax,
            lastValueVisible = options.LastValueVisible,
            priceLineVisible = options.PriceLineVisible,
        });
    }

    public async Task SetDataAsync(string seriesId, IEnumerable<ChartDataPoint> dataPoints)
    {
        var module = await _moduleTask.Value;
        var data = dataPoints.Select(p => new { time = p.Time, value = p.Value }).ToArray();
        await module.InvokeVoidAsync("setData", seriesId, data);
    }

    public async Task UpdateDataAsync(string seriesId, ChartDataPoint dataPoint)
    {
        var module = await _moduleTask.Value;
        await module.InvokeVoidAsync("updateData", seriesId, new { time = dataPoint.Time, value = dataPoint.Value });
    }

    public async Task SetVisibleRangeAsync(string chartId, long fromTimestamp, long toTimestamp)
    {
        var module = await _moduleTask.Value;
        await module.InvokeVoidAsync("setVisibleRange", chartId, fromTimestamp, toTimestamp);
    }

    public async Task DestroyChartAsync(string chartId)
    {
        var module = await _moduleTask.Value;
        await module.InvokeVoidAsync("destroyChart", chartId);
        _chartIds.Remove(chartId);
    }

    public async Task<string?> InitializeXYChartAsync(string containerId, ChartOptions? options = null)
    {
        var module = await _moduleTask.Value;
        options ??= ChartOptions.Default;

        var chartId = await module.InvokeAsync<string?>("initializeXYChart", containerId, new
        {
            backgroundColor = options.BackgroundColor,
            textColor = options.TextColor,
            gridColor = options.GridColor,
        });

        if (chartId != null)
        {
            _chartIds.Add(chartId);
        }

        return chartId;
    }

    public async Task SetXYVisibleRangeAsync(string chartId, int fromValue, int toValue)
    {
        var module = await _moduleTask.Value;
        await module.InvokeVoidAsync("setXYVisibleRange", chartId, fromValue, toValue);
    }

    public async ValueTask DisposeAsync()
    {
        if (_moduleTask.IsValueCreated)
        {
            var module = await _moduleTask.Value;
            await module.InvokeVoidAsync("destroyAllCharts");
            await module.DisposeAsync();
        }
    }
}

public record ChartOptions(string BackgroundColor, string TextColor, string GridColor)
{
    public static ChartOptions Default => new("#1e1e1e", "#d4d4d4", "#333333");
}

public record LineSeriesOptions(
    string Color,
    int LineWidth = 2,
    string Title = "",
    int LineStyle = 0,
    decimal? PriceRangeMin = null,
    decimal? PriceRangeMax = null,
    bool LastValueVisible = false,
    bool PriceLineVisible = false);

public record ChartDataPoint(long Time, decimal Value);
