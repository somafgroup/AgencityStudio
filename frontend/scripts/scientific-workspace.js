import * as echarts from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
  LineChart,
  ScatterChart,
  CanvasRenderer,
]);

const lineStyles = ['solid', 'dashed', 'dotted'];
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const systemDark = window.matchMedia('(prefers-color-scheme: dark)');

function formatNumber(value, precision = 8) {
  if (value === null || value === undefined) return '—';
  if (!Number.isFinite(Number(value))) return String(value);
  return Number(value).toPrecision(precision).replace(/(?:\.0+|(?:(\.\d*?[1-9])0+))(?=e|$)/, '$1');
}

function actualTheme() {
  const selected = document.documentElement.dataset.theme || 'system';
  if (selected === 'system') return systemDark.matches ? 'dark' : 'light';
  return selected;
}

function cssValue(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function chartTheme() {
  return {
    actual: actualTheme(),
    text: cssValue('--text'),
    muted: cssValue('--muted'),
    border: cssValue('--border'),
    surface: cssValue('--surface'),
    selection: cssValue('--chart-selection') || cssValue('--danger'),
    palette: [
      cssValue('--chart-1') || cssValue('--accent'),
      cssValue('--chart-2') || '#7c3aed',
      cssValue('--chart-3') || '#b45309',
    ],
  };
}

async function fetchJson(url) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || 'Unable to load this visualization.');
  }
  return payload;
}

function baseAxes(theme, coordinateLabel) {
  const common = {
    axisLine: { lineStyle: { color: theme.border } },
    axisTick: { lineStyle: { color: theme.border } },
    axisLabel: { color: theme.muted },
    nameTextStyle: { color: theme.muted },
    splitLine: { lineStyle: { color: theme.border, opacity: 0.45 } },
  };
  return {
    xAxis: { type: 'value', name: coordinateLabel, nameLocation: 'middle', nameGap: 30, ...common },
    yAxis: { type: 'value', scale: true, ...common },
  };
}

function tooltipText(params) {
  const items = Array.isArray(params) ? params : [params];
  if (!items.length) return '';
  const data = items[0].data || [];
  const index = data[data.length - 1];
  const lines = [`Sample ${Number(index) + 1}`];
  for (const item of items) {
    if (!Array.isArray(item.data)) continue;
    lines.push(`${item.seriesName}: ${formatNumber(item.data[1])}`);
  }
  return lines.join('\n');
}

function commonOption(theme, description, coordinateLabel) {
  const axes = baseAxes(theme, coordinateLabel);
  return {
    animation: !reducedMotion.matches,
    color: theme.palette,
    backgroundColor: 'transparent',
    textStyle: { color: theme.text },
    aria: {
      enabled: true,
      show: true,
      description,
      decal: { show: true },
    },
    grid: { left: 58, right: 24, top: 45, bottom: 72, containLabel: true },
    legend: { top: 4, textStyle: { color: theme.text } },
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      confine: true,
      formatter: tooltipText,
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'slider', xAxisIndex: 0, filterMode: 'none', bottom: 10, height: 22 },
    ],
    ...axes,
  };
}

class ScientificWorkspaceController {
  constructor(root) {
    this.root = root;
    this.manifestEndpoint = root.dataset.manifestEndpoint;
    this.seriesEndpoint = root.dataset.seriesEndpoint;
    this.sampleEndpoint = root.dataset.sampleEndpoint;
    this.resultSha256 = root.dataset.resultSha256;
    this.coordinateLabel = root.dataset.coordinateLabel || 'Coordinate';
    this.errorMessage = root.dataset.errorMessage || 'Unable to load this visualization.';
    this.groupName = `canonical-run-${root.dataset.runId}`;
    this.chartRecords = [];
    this.selectedSample = Number(root.dataset.initialSample || 0);
    this.playTimer = null;
    this.manifest = null;
  }

  async init() {
    try {
      this.manifest = await fetchJson(this.manifestEndpoint);
      if (this.manifest.result_sha256 !== this.resultSha256) {
        throw new Error(this.errorMessage);
      }
      this.sampleCount = Number(this.manifest.sample_count || 0);
      this.bindSampleControls();
      await Promise.all(
        Array.from(this.root.querySelectorAll('[data-chart-card]')).map((card) => this.loadChart(card)),
      );
      const timeInstances = this.chartRecords
        .filter((record) => record.mode !== 'complex-plane')
        .map((record) => record.instance);
      for (const instance of timeInstances) instance.group = this.groupName;
      if (timeInstances.length > 1) echarts.connect(this.groupName);
      if (this.sampleCount > 0) await this.selectSample(this.selectedSample, { updateUrl: false });
      this.root.dataset.workspaceReady = 'true';
    } catch (error) {
      this.showWorkspaceError(error.message || this.errorMessage);
    }

    window.addEventListener('agencity:theme-changed', () => this.refreshTheme());
    systemDark.addEventListener('change', () => {
      if ((document.documentElement.dataset.theme || 'system') === 'system') this.refreshTheme();
    });
    window.addEventListener('resize', () => this.resizeCharts(), { passive: true });
    document.addEventListener('fullscreenchange', () => this.resizeCharts());
  }

  showWorkspaceError(message) {
    const target = this.root.querySelector('[data-workspace-error]');
    if (!target) return;
    target.textContent = message;
    target.hidden = false;
  }

  chartError(card, message = this.errorMessage) {
    const container = card.querySelector('[data-chart-container]');
    if (!container) return;
    container.replaceChildren();
    const error = document.createElement('p');
    error.className = 'alert alert-error';
    error.textContent = message;
    container.append(error);
    card.dataset.chartReady = 'error';
  }

  availableNames(card) {
    const requested = (card.dataset.series || '')
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    return requested.filter((name) => Object.hasOwn(this.manifest.series || {}, name));
  }

  async loadChart(card) {
    const names = this.availableNames(card);
    if (!names.length) {
      this.chartError(card, card.dataset.unavailableMessage || this.errorMessage);
      return;
    }
    const query = new URLSearchParams({
      series: names.join(','),
      start: '0',
      stop: String(this.sampleCount),
      max_points: this.root.dataset.maxPoints || '5000',
    });
    try {
      const payload = await fetchJson(`${this.seriesEndpoint}?${query}`);
      if (payload.result_sha256 !== this.resultSha256) throw new Error(this.errorMessage);
      const container = card.querySelector('[data-chart-container]');
      const instance = echarts.init(container, null, { renderer: 'canvas' });
      const mode = card.dataset.chartMode || 'series';
      const record = { card, container, instance, mode, names, payload };
      this.chartRecords.push(record);
      this.renderRecord(record);
      this.bindChartActions(record);
      instance.on('click', (params) => {
        const data = params.data;
        if (!Array.isArray(data)) return;
        const index = Number(data[data.length - 1]);
        if (Number.isInteger(index)) this.selectSample(index);
      });
      card.dataset.chartReady = 'true';
      card.dataset.chartTheme = actualTheme();
      if (payload.decimated) card.dataset.displayDecimated = 'true';
      const note = card.querySelector('[data-decimation-note]');
      if (note) note.hidden = !payload.decimated;
    } catch (error) {
      this.chartError(card, error.message || this.errorMessage);
    }
  }

  renderRecord(record) {
    const theme = chartTheme();
    let option;
    if (record.mode === 'complex-plane') {
      option = this.complexPlaneOption(record, theme);
    } else if (record.mode === 'complex-components') {
      option = this.complexComponentsOption(record, theme);
    } else {
      option = this.seriesOption(record, theme);
    }
    record.instance.setOption(option, { notMerge: true });
    record.card.dataset.chartTheme = theme.actual;
  }

  coordinateLookup(payload) {
    return new Map(
      (payload.coordinate?.points || []).map((point) => [Number(point.index), point.value]),
    );
  }

  seriesOption(record, theme) {
    const option = commonOption(theme, record.card.dataset.chartDescription || '', this.coordinateLabel);
    const coordinates = this.coordinateLookup(record.payload);
    option.series = record.names.map((name, traceIndex) => {
      const stored = record.payload.series[name];
      const data = stored.points.map((point) => [
        coordinates.get(Number(point.index)),
        point.value,
        Number(point.index),
      ]);
      return {
        id: `stored-${name}`,
        name: stored.metadata?.symbol || name,
        type: 'line',
        data,
        showSymbol: data.length <= 300,
        symbolSize: 5,
        connectNulls: false,
        smooth: false,
        sampling: 'none',
        lineStyle: { type: lineStyles[traceIndex % lineStyles.length], width: 1.8 },
        emphasis: { focus: 'series' },
      };
    });
    return option;
  }

  complexComponentsOption(record, theme) {
    const option = commonOption(theme, record.card.dataset.chartDescription || '', this.coordinateLabel);
    const name = record.names[0];
    const stored = record.payload.series[name];
    const symbol = stored.metadata?.symbol || name;
    const coordinates = this.coordinateLookup(record.payload);
    const parts = [
      ['real', `Re(${symbol})`],
      ['imag', `Im(${symbol})`],
      ['magnitude', `|${symbol}|`],
    ];
    option.series = parts.map(([field, label], traceIndex) => ({
      id: `stored-${name}-${field}`,
      name: label,
      type: 'line',
      data: stored.points.map((point) => [
        coordinates.get(Number(point.index)),
        point[field],
        Number(point.index),
      ]),
      showSymbol: stored.points.length <= 300,
      symbolSize: 5,
      connectNulls: false,
      smooth: false,
      sampling: 'none',
      lineStyle: { type: lineStyles[traceIndex % lineStyles.length], width: 1.8 },
    }));
    return option;
  }

  complexPlaneOption(record, theme) {
    const name = record.names[0];
    const stored = record.payload.series[name];
    const symbol = stored.metadata?.symbol || name;
    const coordinates = this.coordinateLookup(record.payload);
    const points = stored.points.map((point) => {
      const coordinate = coordinates.get(Number(point.index));
      const gradientValue = coordinate === null || coordinate === undefined ? Number(point.index) : coordinate;
      return [point.real, point.imag, gradientValue, point.magnitude, Number(point.index)];
    });
    const finiteGradient = points.map((item) => Number(item[2])).filter(Number.isFinite);
    const minimum = finiteGradient.length ? Math.min(...finiteGradient) : 0;
    const maximum = finiteGradient.length ? Math.max(...finiteGradient) : Math.max(points.length - 1, 1);
    return {
      animation: !reducedMotion.matches,
      backgroundColor: 'transparent',
      color: theme.palette,
      textStyle: { color: theme.text },
      aria: {
        enabled: true,
        show: true,
        description: record.card.dataset.chartDescription || '',
        decal: { show: true },
      },
      grid: { left: 62, right: 30, top: 35, bottom: 82, containLabel: true },
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        confine: true,
        formatter: (params) => {
          const data = params.data || [];
          return [
            `Sample ${Number(data[4]) + 1}`,
            `Re: ${formatNumber(data[0])}`,
            `Im: ${formatNumber(data[1])}`,
            `Magnitude: ${formatNumber(data[3])}`,
            `${this.coordinateLabel}: ${formatNumber(data[2])}`,
          ].join('\n');
        },
      },
      xAxis: {
        type: 'value',
        name: `Re(${symbol})`,
        scale: true,
        axisLabel: { color: theme.muted },
        axisLine: { lineStyle: { color: theme.border } },
        splitLine: { lineStyle: { color: theme.border, opacity: 0.45 } },
        nameTextStyle: { color: theme.muted },
      },
      yAxis: {
        type: 'value',
        name: `Im(${symbol})`,
        scale: true,
        axisLabel: { color: theme.muted },
        axisLine: { lineStyle: { color: theme.border } },
        splitLine: { lineStyle: { color: theme.border, opacity: 0.45 } },
        nameTextStyle: { color: theme.muted },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, yAxisIndex: 0, filterMode: 'none' },
        { type: 'slider', xAxisIndex: 0, filterMode: 'none', bottom: 10, height: 22 },
      ],
      visualMap: {
        type: 'continuous',
        min: minimum,
        max: maximum,
        dimension: 2,
        seriesIndex: 1,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 38,
        text: [record.card.dataset.gradientEndLabel || '', record.card.dataset.gradientStartLabel || ''],
        textStyle: { color: theme.muted },
      },
      series: [
        {
          id: `stored-${name}-trajectory`,
          name: `${symbol} trajectory`,
          type: 'line',
          data: points.map((item) => [item[0], item[1]]),
          smooth: false,
          showSymbol: false,
          silent: true,
          connectNulls: false,
          lineStyle: { color: theme.muted, width: 1, opacity: 0.55 },
        },
        {
          id: `stored-${name}-samples`,
          name: symbol,
          type: 'scatter',
          data: points,
          symbolSize: points.length > 1500 ? 4 : 6,
          large: points.length > 5000,
          largeThreshold: 5000,
        },
        {
          id: `selected-${name}`,
          name: 'Selected sample',
          type: 'scatter',
          data: [],
          symbolSize: 12,
          itemStyle: { color: theme.selection, borderColor: theme.surface, borderWidth: 2 },
          tooltip: { show: false },
          z: 20,
        },
      ],
    };
  }

  bindChartActions(record) {
    record.card.querySelectorAll('[data-chart-action]').forEach((button) => {
      button.addEventListener('click', () => {
        const action = button.dataset.chartAction;
        if (action === 'reset') {
          record.instance.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
          record.instance.resize();
        } else if (action === 'fullscreen') {
          if (document.fullscreenElement === record.card) document.exitFullscreen();
          else record.card.requestFullscreen?.();
        } else if (action === 'export') {
          this.exportPng(record);
        }
      });
    });
  }

  exportPng(record) {
    const theme = chartTheme();
    const url = record.instance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: theme.surface });
    const link = document.createElement('a');
    link.href = url;
    link.download = `canonical-run-${this.root.dataset.runNumber}-${record.card.dataset.chartKey || 'chart'}.png`;
    link.click();
  }

  bindSampleControls() {
    const previous = this.root.querySelector('[data-sample-action="previous"]');
    const next = this.root.querySelector('[data-sample-action="next"]');
    const input = this.root.querySelector('[data-sample-input]');
    const play = this.root.querySelector('[data-sample-action="play"]');
    const pause = this.root.querySelector('[data-sample-action="pause"]');
    const speed = this.root.querySelector('[data-playback-speed]');
    previous?.addEventListener('click', () => this.selectSample(this.selectedSample - 1));
    next?.addEventListener('click', () => this.selectSample(this.selectedSample + 1));
    input?.addEventListener('change', () => this.selectSample(Number(input.value) - 1));
    play?.addEventListener('click', () => this.startPlayback(speed));
    pause?.addEventListener('click', () => this.stopPlayback());
    speed?.addEventListener('change', () => {
      if (this.playTimer) this.startPlayback(speed);
    });
    this.root.addEventListener('keydown', (event) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        this.selectSample(this.selectedSample - 1);
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        this.selectSample(this.selectedSample + 1);
      }
    });
  }

  startPlayback(speedSelect) {
    this.stopPlayback();
    const multiplier = Number(speedSelect?.value || 1);
    const interval = Math.max(80, 500 / (Number.isFinite(multiplier) && multiplier > 0 ? multiplier : 1));
    this.playTimer = window.setInterval(() => {
      const next = this.selectedSample + 1;
      if (next >= this.sampleCount) this.stopPlayback();
      else this.selectSample(next);
    }, interval);
    this.root.dataset.playback = 'playing';
  }

  stopPlayback() {
    if (this.playTimer) window.clearInterval(this.playTimer);
    this.playTimer = null;
    this.root.dataset.playback = 'paused';
  }

  async selectSample(index, { updateUrl = true } = {}) {
    if (!this.sampleCount) return;
    const resolved = Math.min(Math.max(Number.isFinite(index) ? Math.trunc(index) : 0, 0), this.sampleCount - 1);
    try {
      const payload = await fetchJson(`${this.sampleEndpoint}?index=${resolved}`);
      if (payload.result_sha256 !== this.resultSha256) throw new Error(this.errorMessage);
      this.selectedSample = resolved;
      this.root.dataset.selectedSample = String(resolved);
      const input = this.root.querySelector('[data-sample-input]');
      if (input) input.value = String(resolved + 1);
      const summary = this.root.querySelector('[data-sample-summary]');
      if (summary) summary.textContent = `${resolved + 1} / ${this.sampleCount}`;
      this.renderInspector(payload);
      this.highlightCharts(payload);
      this.updateSampleLinks(resolved);
      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set('sample', String(resolved));
        history.replaceState(null, '', url);
      }
    } catch (error) {
      this.showWorkspaceError(error.message || this.errorMessage);
    }
  }

  renderInspector(payload) {
    const container = this.root.querySelector('[data-sample-values]');
    if (!container) return;
    container.replaceChildren();
    const order = ['xi', 'u', 'u_star', 'X_star', 'A_star', 'M', 'O', 'D', 'S', 'J', 'theta', 'U', 'beta', 'b'];
    for (const name of order) {
      const item = payload.values?.[name];
      if (!item) continue;
      const wrapper = document.createElement('div');
      wrapper.className = 'sample-value';
      const term = document.createElement('dt');
      term.className = 'muted scientific-variable';
      term.textContent = item.metadata?.symbol || name;
      const description = document.createElement('dd');
      description.className = 'font-mono text-xs';
      const value = item.value || {};
      if (item.metadata?.complex) {
        description.textContent = `Re ${formatNumber(value.real)} · Im ${formatNumber(value.imag)} · |·| ${formatNumber(value.magnitude)} · arg ${formatNumber(value.phase)}`;
      } else {
        description.textContent = formatNumber(value.value, 10);
      }
      wrapper.append(term, description);
      container.append(wrapper);
    }
  }

  highlightCharts(payload) {
    const coordinateValue = payload.values?.xi?.value?.value ?? payload.index;
    const theme = chartTheme();
    for (const record of this.chartRecords) {
      if (record.mode === 'complex-plane') {
        const name = record.names[0];
        const value = payload.values?.[name]?.value;
        if (!value) continue;
        record.instance.setOption({
          series: [{ id: `selected-${name}`, data: [[value.real, value.imag, payload.index]] }],
        });
      } else {
        const firstName = record.names[0];
        const firstId = record.mode === 'complex-components'
          ? `stored-${firstName}-real`
          : `stored-${firstName}`;
        record.instance.setOption({
          series: [{
            id: firstId,
            markLine: {
              silent: true,
              symbol: 'none',
              label: { show: false },
              lineStyle: { color: theme.selection, width: 1.5, type: 'dashed' },
              data: [{ xAxis: coordinateValue }],
            },
          }],
        });
      }
    }
  }

  updateSampleLinks(index) {
    this.root.querySelectorAll('[data-sample-link]').forEach((link) => {
      const url = new URL(link.href, window.location.origin);
      url.searchParams.set('sample', String(index));
      link.href = `${url.pathname}${url.search}${url.hash}`;
    });
  }

  refreshTheme() {
    for (const record of this.chartRecords) this.renderRecord(record);
    if (this.sampleCount) this.selectSample(this.selectedSample, { updateUrl: false });
  }

  resizeCharts() {
    for (const record of this.chartRecords) record.instance.resize();
  }
}

document.querySelectorAll('[data-scientific-workspace]').forEach((root) => {
  const controller = new ScientificWorkspaceController(root);
  controller.init();
});
