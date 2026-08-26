import * as echarts from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  LineChart,
  ScatterChart,
  CanvasRenderer,
]);

function css(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function option(payload, title) {
  const points = payload.points || [];
  return {
    animation: false,
    aria: { enabled: true, description: title },
    backgroundColor: 'transparent',
    textStyle: { color: css('--color-text', '#111827') },
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        const item = params?.[0]?.data;
        if (!item) return '';
        return `${payload.scale_symbol}=${item[0]} ${payload.grid_unit}<br>${payload.metric}=${item[1]}`;
      },
    },
    grid: { left: 58, right: 24, top: 32, bottom: 66 },
    xAxis: {
      type: 'value',
      name: `${payload.scale_symbol} [${payload.grid_unit}]`,
      scale: true,
    },
    yAxis: { type: 'value', name: payload.metric || '' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 12 }],
    series: [{
      name: payload.metric,
      type: 'line',
      showSymbol: true,
      data: points.map((point) => [point.scale, point.value, point.index]),
      connectNulls: false,
    }],
  };
}

async function json(url) {
  const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function init(root) {
  const chartElement = root.querySelector('[data-sensitivity-chart]');
  const metric = root.querySelector('[data-sensitivity-metric]');
  const error = root.querySelector('[data-sensitivity-error]');
  if (!chartElement) return;
  const chart = echarts.init(chartElement);

  async function render() {
    try {
      const endpoint = new URL(root.dataset.chartEndpoint, window.location.origin);
      if (metric?.value) endpoint.searchParams.set('metric', metric.value);
      const payload = await json(endpoint);
      chart.setOption(option(payload, root.dataset.chartDescription || 'Sensitivity study'), true);
      root.dataset.chartReady = 'true';
      error.hidden = true;
    } catch (exc) {
      error.hidden = false;
      error.textContent = root.dataset.errorMessage || 'Unable to load this sensitivity visualization.';
      root.dataset.chartReady = 'false';
    }
  }

  metric?.addEventListener('change', render);
  window.addEventListener('resize', () => chart.resize());
  document.addEventListener('agencity:theme-changed', () => render());
  await render();
}

document.querySelectorAll('[data-sensitivity-workspace]').forEach((root) => init(root));
