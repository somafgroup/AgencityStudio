import * as echarts from "echarts";

const root = document.querySelector("[data-research-workspace]");

if (root) {
  const rank = Number(root.dataset.spatialRank || 0);
  const timeCount = Number(root.dataset.timeCount || 0);
  const timeInput = root.querySelector("[data-research-time]");
  const spatialInput = root.querySelector("[data-research-spatial]");
  const representationSelect = root.querySelector("[data-research-representation]");
  const pointContainer = root.querySelector("[data-research-point]");
  const fieldElement = root.querySelector("[data-research-field-chart]");
  const traceElement = root.querySelector("[data-research-trace-chart]");
  const derivedElements = Array.from(root.querySelectorAll("[data-research-derived-chart]"));
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const charts = new Map();

  const state = {
    time: Number(root.dataset.selectedTime || 0),
    spatial: String(root.dataset.selectedSpatial || "")
      .split(",")
      .filter(Boolean)
      .map((item) => Number(item)),
  };

  const query = (params) => new URLSearchParams(params).toString();
  const clampTime = (value) => Math.max(0, Math.min(timeCount - 1, Number(value) || 0));
  const loadJson = async (url) => {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Research field data request failed.");
    return payload;
  };
  const chartFor = (element) => {
    if (!element) return null;
    if (!charts.has(element)) charts.set(element, echarts.init(element));
    return charts.get(element);
  };
  window.addEventListener("resize", () => charts.forEach((chart) => chart.resize()));

  const scalarText = (value) => {
    if (value && typeof value === "object" && Object.hasOwn(value, "real")) {
      return `${value.real} + ${value.imag}i · |phi|=${value.magnitude} · arg(phi)=${value.phase}`;
    }
    return String(value);
  };

  const syncInputs = () => {
    if (timeInput) timeInput.value = String(state.time);
    if (spatialInput) spatialInput.value = state.spatial.join(",");
  };

  const renderPoint = async () => {
    if (!pointContainer) return;
    try {
      const payload = await loadJson(`${root.dataset.pointUrl}?${query({ time: state.time, spatial: state.spatial.join(",") })}`);
      const coordinates = payload.coordinates.map((item) => `axis ${item.dimension}: index ${item.index} → ${item.value}`).join(" · ");
      pointContainer.innerHTML = `<p><strong>t[${payload.time_index}]</strong> = ${payload.time_value}</p><p class="muted text-xs mt-1">${coordinates}</p><table class="table mt-3"><tbody><tr><th>phi</th><td>${scalarText(payload.phi)}</td></tr>${payload.phi_dot === null ? "" : `<tr><th>phi_dot</th><td>${scalarText(payload.phi_dot)}</td></tr>`}</tbody></table>`;
    } catch (error) {
      pointContainer.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  const renderField = async () => {
    if (!fieldElement) return;
    const dimensions = rank >= 2 ? [0, 1] : [0];
    const fixed = [];
    for (let dimension = 0; dimension < rank; dimension += 1) {
      if (!dimensions.includes(dimension)) fixed.push(`${dimension}:${state.spatial[dimension] || 0}`);
    }
    try {
      const payload = await loadJson(`${root.dataset.sliceUrl}?${query({
        time: state.time,
        representation: representationSelect?.value || "magnitude",
        dims: dimensions.join(","),
        fixed: fixed.join(","),
      })}`);
      const chart = chartFor(fieldElement);
      if (payload.axes.length === 1) {
        chart.setOption({
          animation: !reducedMotion,
          tooltip: { trigger: "axis" },
          xAxis: { type: "category", data: payload.axes[0].map(String) },
          yAxis: { type: "value" },
          series: [{ type: "line", showSymbol: false, data: payload.values }],
        }, true);
      } else {
        const data = [];
        payload.values.forEach((row, firstPosition) => {
          row.forEach((value, secondPosition) => data.push([secondPosition, firstPosition, value]));
        });
        const flat = payload.values.flat();
        chart.setOption({
          animation: !reducedMotion,
          tooltip: { formatter: (item) => `axis0=${payload.axes[0][item.data[1]]}<br>axis1=${payload.axes[1][item.data[0]]}<br>phi=${item.data[2]}` },
          xAxis: { type: "category", data: payload.axes[1].map(String) },
          yAxis: { type: "category", data: payload.axes[0].map(String) },
          visualMap: { min: Math.min(...flat), max: Math.max(...flat), calculable: true, orient: "horizontal" },
          series: [{ type: "heatmap", data, progressive: 0 }],
        }, true);
      }
      const note = root.querySelector("[data-research-display-note]");
      if (note) note.textContent = `Display-only sampling at exact time index ${state.time}. No scientific array is downsampled in storage or analysis.`;
    } catch (error) {
      fieldElement.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  const renderTrace = async () => {
    if (!traceElement) return;
    try {
      const payload = await loadJson(`${root.dataset.traceUrl}?${query({ spatial: state.spatial.join(",") })}`);
      chartFor(traceElement).setOption({
        animation: !reducedMotion,
        tooltip: { trigger: "axis" },
        legend: { data: ["Re(phi)", "Im(phi)", "|phi|"] },
        xAxis: { type: "category", name: "field time", data: payload.time.map(String) },
        yAxis: { type: "value" },
        series: [
          { name: "Re(phi)", type: "line", showSymbol: false, data: payload.phi.real },
          { name: "Im(phi)", type: "line", showSymbol: false, data: payload.phi.imag },
          { name: "|phi|", type: "line", showSymbol: false, data: payload.phi.magnitude },
        ],
      }, true);
    } catch (error) {
      traceElement.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  const renderDerived = async (element) => {
    const seriesName = element.dataset.series;
    try {
      const payload = await loadJson(`${root.dataset.derivedUrl}?${query({ series: seriesName })}`);
      chartFor(element).setOption({
        animation: !reducedMotion,
        tooltip: { trigger: "axis" },
        xAxis: { type: "category", name: "field time", data: payload.time.map(String) },
        yAxis: { type: "value", name: seriesName },
        series: [{ name: seriesName, type: "line", showSymbol: false, data: payload.values }],
      }, true);
    } catch (error) {
      element.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  const refresh = () => {
    state.time = clampTime(timeInput?.value || state.time);
    const parsed = String(spatialInput?.value || "").split(",").filter((item) => item.trim() !== "").map((item) => Number(item.trim()));
    if (parsed.length === rank && parsed.every(Number.isInteger)) state.spatial = parsed;
    syncInputs();
    renderPoint();
    renderField();
    renderTrace();
  };

  root.querySelector("[data-research-apply]")?.addEventListener("click", refresh);
  representationSelect?.addEventListener("change", renderField);
  root.querySelector("[data-time-prev]")?.addEventListener("click", () => { state.time = clampTime(state.time - 1); syncInputs(); refresh(); });
  root.querySelector("[data-time-next]")?.addEventListener("click", () => { state.time = clampTime(state.time + 1); syncInputs(); refresh(); });
  root.querySelector("[data-space-prev]")?.addEventListener("click", () => { state.spatial[0] = Math.max(0, (state.spatial[0] || 0) - 1); syncInputs(); refresh(); });
  root.querySelector("[data-space-next]")?.addEventListener("click", () => { state.spatial[0] = (state.spatial[0] || 0) + 1; syncInputs(); refresh(); });

  syncInputs();
  renderPoint();
  renderField();
  renderTrace();
  derivedElements.forEach(renderDerived);
}
