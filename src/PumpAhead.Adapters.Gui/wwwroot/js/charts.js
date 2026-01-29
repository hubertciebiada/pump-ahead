const chartInstances = new Map();
const seriesInstances = new Map();
let idCounter = 0;

export function initializeChart(containerId, options) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container with id '${containerId}' not found`);
        return null;
    }

    const chartId = `chart_${idCounter++}`;

    const chart = LightweightCharts.createChart(container, {
        autoSize: true,
        layout: {
            background: { type: 'solid', color: options.backgroundColor || '#1e1e1e' },
            textColor: options.textColor || '#d4d4d4',
        },
        grid: {
            vertLines: { color: options.gridColor || '#333333' },
            horzLines: { color: options.gridColor || '#333333' },
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: options.gridColor || '#333333',
        },
        rightPriceScale: {
            borderColor: options.gridColor || '#333333',
            scaleMargins: { top: 0, bottom: 0 },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: '#758696',
                labelBackgroundColor: '#4c525e',
            },
            horzLine: {
                color: '#758696',
                labelBackgroundColor: '#4c525e',
            },
        },
    });

    chartInstances.set(chartId, chart);
    return chartId;
}

export function addLineSeries(chartId, options) {
    const chart = chartInstances.get(chartId);
    if (!chart) {
        console.error(`Chart with id '${chartId}' not found`);
        return null;
    }

    const seriesId = `series_${idCounter++}`;

    const seriesOptions = {
        color: options.color || '#2196f3',
        lineWidth: options.lineWidth || 2,
        lineStyle: options.lineStyle || 0,
        title: options.title || '',
        lastValueVisible: options.lastValueVisible !== undefined ? options.lastValueVisible : true,
        priceLineVisible: options.priceLineVisible !== undefined ? options.priceLineVisible : true,
        priceFormat: {
            type: 'custom',
            formatter: (price) => price.toFixed(1) + '\u00B0C',
        },
    };

    // If price range is specified, use autoscaleInfoProvider to enforce it
    if (options.priceRangeMin !== undefined && options.priceRangeMax !== undefined) {
        seriesOptions.autoscaleInfoProvider = () => ({
            priceRange: {
                minValue: options.priceRangeMin,
                maxValue: options.priceRangeMax,
            },
            margins: { above: 0, below: 0 },
        });
    }

    const series = chart.addSeries(LightweightCharts.LineSeries, seriesOptions);

    seriesInstances.set(seriesId, { series, chartId });
    return seriesId;
}

export function setData(seriesId, dataPoints) {
    const seriesInfo = seriesInstances.get(seriesId);
    if (!seriesInfo) {
        console.error(`Series with id '${seriesId}' not found`);
        return;
    }

    const formattedData = dataPoints.map(p => ({
        time: p.time,
        value: p.value,
    }));

    seriesInfo.series.setData(formattedData);
}

export function updateData(seriesId, dataPoint) {
    const seriesInfo = seriesInstances.get(seriesId);
    if (!seriesInfo) {
        console.error(`Series with id '${seriesId}' not found`);
        return;
    }

    seriesInfo.series.update({
        time: dataPoint.time,
        value: dataPoint.value,
    });
}

export function setVisibleRange(chartId, fromTimestamp, toTimestamp) {
    const chart = chartInstances.get(chartId);
    if (!chart) {
        console.error(`Chart with id '${chartId}' not found`);
        return;
    }

    chart.timeScale().setVisibleRange({
        from: fromTimestamp,
        to: toTimestamp,
    });
}

export function destroyChart(chartId) {
    const chart = chartInstances.get(chartId);
    if (!chart) {
        return;
    }

    for (const [seriesId, seriesInfo] of seriesInstances.entries()) {
        if (seriesInfo.chartId === chartId) {
            seriesInstances.delete(seriesId);
        }
    }

    chart.remove();
    chartInstances.delete(chartId);
}

export function destroyAllCharts() {
    for (const chartId of chartInstances.keys()) {
        destroyChart(chartId);
    }
}
