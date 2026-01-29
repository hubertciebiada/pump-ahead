# Lightweight Charts - LLM Knowledge Base

## Overview
**Lightweight Charts** is TradingView's open-source charting library for financial/time-series data visualization.
- **Version**: 5.1 (current)
- **License**: Apache 2.0 (requires TradingView attribution link)
- **Bundle size**: ~40KB minified
- **Rendering**: HTML5 Canvas
- **GitHub**: https://github.com/tradingview/lightweight-charts
- **Docs**: https://tradingview.github.io/lightweight-charts/

## Installation

```bash
npm install lightweight-charts
```

**CDN:**
```html
<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
```

## Core Concepts

### Creating a Chart
```javascript
import { createChart, LineSeries } from 'lightweight-charts';

const chart = createChart(document.getElementById('container'), {
    width: 800,
    height: 400,
    layout: {
        background: { type: 'solid', color: '#1e1e1e' },
        textColor: '#d1d4dc',
    },
    grid: {
        vertLines: { color: '#2B2B43' },
        horzLines: { color: '#2B2B43' },
    },
    timeScale: {
        timeVisible: true,
        secondsVisible: false,
    },
});
```

### Series Types
| Type | Import | Data Format |
|------|--------|-------------|
| Line | `LineSeries` | `{ time, value }` |
| Area | `AreaSeries` | `{ time, value }` |
| Candlestick | `CandlestickSeries` | `{ time, open, high, low, close }` |
| Bar | `BarSeries` | `{ time, open, high, low, close }` |
| Histogram | `HistogramSeries` | `{ time, value, color? }` |
| Baseline | `BaselineSeries` | `{ time, value }` |

### Time Format
Time can be provided as:
- **Unix timestamp** (seconds): `1642425322`
- **ISO date string**: `'2024-01-15'`
- **Business day object**: `{ year: 2024, month: 1, day: 15 }`

```javascript
// All valid:
{ time: 1642425322, value: 100 }
{ time: '2024-01-15', value: 100 }
{ time: { year: 2024, month: 1, day: 15 }, value: 100 }
```

## Adding Multiple Series

```javascript
import { createChart, LineSeries, AreaSeries } from 'lightweight-charts';

const chart = createChart(container, options);

// First series
const tempSeries = chart.addSeries(LineSeries, {
    color: '#2962FF',
    lineWidth: 2,
    title: 'Temperature',
});
tempSeries.setData([
    { time: 1704067200, value: 21.5 },
    { time: 1704070800, value: 22.1 },
    // ...
]);

// Second series
const humiditySeries = chart.addSeries(LineSeries, {
    color: '#26a69a',
    lineWidth: 2,
    title: 'Humidity',
    priceScaleId: 'right', // or 'left' for separate scale
});
humiditySeries.setData([...]);
```

## Crosshair Configuration

```javascript
import { CrosshairMode } from 'lightweight-charts';

chart.applyOptions({
    crosshair: {
        // Mode: Normal (free) or Magnet (snaps to data points)
        mode: CrosshairMode.Normal, // or CrosshairMode.Magnet
        
        // Vertical line (time axis)
        vertLine: {
            width: 1,
            color: '#758696',
            style: 0, // 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed
            labelVisible: true,
            labelBackgroundColor: '#4c525e',
        },
        
        // Horizontal line (price axis)
        horzLine: {
            color: '#758696',
            labelVisible: true,
            labelBackgroundColor: '#4c525e',
        },
    },
});
```

## Crosshair Events & Custom Tooltips

```javascript
// Subscribe to crosshair movement
chart.subscribeCrosshairMove((param) => {
    if (!param.point || !param.time) {
        // Cursor left chart area
        tooltip.style.display = 'none';
        return;
    }
    
    // Get values for all series at this time point
    param.seriesData.forEach((data, series) => {
        const value = data.value !== undefined ? data.value : data.close;
        console.log(`Series value: ${value}`);
    });
    
    // Position tooltip
    tooltip.style.left = param.point.x + 'px';
    tooltip.style.top = param.point.y + 'px';
});

// Unsubscribe
chart.unsubscribeCrosshairMove(handler);
```

## Real-time Updates

```javascript
// Update last point or add new one
series.update({ time: 1704067200, value: 23.5 });

// For streaming data
setInterval(() => {
    const now = Math.floor(Date.now() / 1000);
    series.update({ time: now, value: getNewValue() });
}, 1000);
```

## Time Scale Control

```javascript
const timeScale = chart.timeScale();

// Fit all data
timeScale.fitContent();

// Set visible range
timeScale.setVisibleRange({
    from: '2024-01-01',
    to: '2024-01-31',
});

// Scroll/zoom
timeScale.scrollToPosition(-10, false); // Scroll left
timeScale.setVisibleLogicalRange({ from: 0, to: 100 });

// Subscribe to range changes
timeScale.subscribeVisibleLogicalRangeChange((range) => {
    console.log('Visible range:', range);
});
```

## Price Scale Options

```javascript
chart.applyOptions({
    rightPriceScale: {
        visible: true,
        borderColor: '#2B2B43',
        scaleMargins: {
            top: 0.1,
            bottom: 0.1,
        },
    },
    leftPriceScale: {
        visible: true, // Enable second Y-axis
    },
});

// Assign series to left scale
series.applyOptions({
    priceScaleId: 'left',
});
```

## Markers (Annotations)

```javascript
import { createSeriesMarkers } from 'lightweight-charts';

const markers = createSeriesMarkers(series, [
    {
        time: '2024-01-15',
        position: 'aboveBar', // or 'belowBar', 'inBar'
        color: '#f68410',
        shape: 'circle', // 'circle', 'square', 'arrowUp', 'arrowDown'
        text: 'Alert!',
    },
]);
```

## Price Lines (Horizontal Lines)

```javascript
const priceLine = series.createPriceLine({
    price: 25.5,
    color: '#ef5350',
    lineWidth: 2,
    lineStyle: 2, // Dashed
    axisLabelVisible: true,
    title: 'Target',
});

// Remove
series.removePriceLine(priceLine);
```

## Responsive / Auto-resize

```javascript
// Option 1: autoSize (recommended)
const chart = createChart(container, {
    autoSize: true, // Chart fills container
});

// Option 2: Manual resize
window.addEventListener('resize', () => {
    chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
    });
});

// Option 3: ResizeObserver
const resizeObserver = new ResizeObserver(entries => {
    const { width, height } = entries[0].contentRect;
    chart.applyOptions({ width, height });
});
resizeObserver.observe(container);
```

## Complete Example: Sensor Dashboard

```javascript
import { createChart, LineSeries, CrosshairMode } from 'lightweight-charts';

// Create chart
const chart = createChart(document.getElementById('chart'), {
    width: 800,
    height: 400,
    autoSize: true,
    layout: {
        background: { type: 'solid', color: '#1a1a2e' },
        textColor: '#eee',
    },
    grid: {
        vertLines: { color: '#2a2a4a' },
        horzLines: { color: '#2a2a4a' },
    },
    crosshair: {
        mode: CrosshairMode.Magnet,
    },
    timeScale: {
        timeVisible: true,
        secondsVisible: true,
    },
    rightPriceScale: {
        borderColor: '#2a2a4a',
    },
});

// Temperature series
const tempSeries = chart.addSeries(LineSeries, {
    color: '#ff6b6b',
    lineWidth: 2,
    title: 'Temp °C',
    priceFormat: {
        type: 'custom',
        formatter: (price) => price.toFixed(1) + '°C',
    },
});

// Humidity series (separate scale)
const humidSeries = chart.addSeries(LineSeries, {
    color: '#4ecdc4',
    lineWidth: 2,
    title: 'Humidity %',
    priceScaleId: 'left',
    priceFormat: {
        type: 'custom',
        formatter: (price) => price.toFixed(0) + '%',
    },
});

// Enable left scale
chart.applyOptions({
    leftPriceScale: { visible: true, borderColor: '#2a2a4a' },
});

// Load data
tempSeries.setData(temperatureData);
humidSeries.setData(humidityData);

// Custom tooltip
const tooltip = document.createElement('div');
tooltip.className = 'chart-tooltip';
document.getElementById('chart').appendChild(tooltip);

chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.point) {
        tooltip.style.display = 'none';
        return;
    }
    
    const tempData = param.seriesData.get(tempSeries);
    const humidData = param.seriesData.get(humidSeries);
    
    tooltip.innerHTML = `
        <div>Time: ${new Date(param.time * 1000).toLocaleString()}</div>
        <div style="color:#ff6b6b">Temp: ${tempData?.value?.toFixed(1)}°C</div>
        <div style="color:#4ecdc4">Humidity: ${humidData?.value?.toFixed(0)}%</div>
    `;
    tooltip.style.display = 'block';
    tooltip.style.left = param.point.x + 15 + 'px';
    tooltip.style.top = param.point.y + 15 + 'px';
});

// Fit content
chart.timeScale().fitContent();
```

## Key API Interfaces

| Interface | Purpose |
|-----------|---------|
| `IChartApi` | Main chart control (series, options, events) |
| `ISeriesApi` | Series control (data, options, price lines) |
| `ITimeScaleApi` | Time axis control (range, zoom, scroll) |
| `IPriceScaleApi` | Price axis control |

## Common Gotchas

1. **Container must have dimensions** - Chart won't render in 0-height container
2. **Time must be sorted ascending** - Data array must be chronologically ordered
3. **Attribution required** - Apache 2.0 license requires TradingView link
4. **No built-in tooltip** - Must implement custom tooltip with `subscribeCrosshairMove`
5. **Single value per timestamp** - Duplicate times will overwrite

## Attribution Requirement

```javascript
// Option 1: Built-in logo
const chart = createChart(container, {
    attributionLogo: true, // Shows TradingView logo
});

// Option 2: Manual link in your UI
// Add link to https://www.tradingview.com/ somewhere visible
```

## TypeScript Support

Library is written in TypeScript with full type definitions included.

```typescript
import {
    createChart,
    IChartApi,
    ISeriesApi,
    LineSeries,
    LineData,
    Time,
} from 'lightweight-charts';

const chart: IChartApi = createChart(container);
const series: ISeriesApi<'Line'> = chart.addSeries(LineSeries);

const data: LineData[] = [
    { time: '2024-01-01' as Time, value: 100 },
];
series.setData(data);
```
