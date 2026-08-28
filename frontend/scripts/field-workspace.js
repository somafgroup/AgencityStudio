import * as echarts from "echarts";

const root = document.querySelector("[data-field-workspace]");

if (root) {
  const rank = Number(root.dataset.spatialRank || 0);
  const timeCount = Number(root.dataset.timeCount || 0);
  const timeInput = root.querySelector("[data-field-time]");
  const spatialInput = root.querySelector("[data-field-spatial]");
  const applyButton = root.querySelector("[data-field-apply]");
  const pointContainer = root.querySelector("[data-field-point]");
  const chartElement = root.querySelector("[data-field-chart]");
  const traceElement = root.querySelector("[data-field-trace-chart]");
  const representationSelect = root.querySelector("[data-field-representation]");

  const state = {
    time: Number(root.dataset.selectedTime || 0),
    spatial: String(root.dataset.selectedSpatial || "")
      .split(",")
      .filter((item) => item !== "")
      .map((item) => Number(item)),
  };

  const clampTime = (value) => Math.max(0, Math.min(timeCount - 1, Number(value) || 0));
  const currentRepresentation = () => representationSelect?.value || (chartElement?.dataset.series === "u" ? "value" : "magnitude");

  const syncInputs = () => {
    timeInput.value = String(state.time);
    spatialInput.value = state.spatial.join(",");
  };

  const query = (params) => new URLSearchParams(params).toString();
  const loadJson = async (url) => {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Field data request failed.");
    return payload;
  };

  const scalarText = (value) => {
    if (value && typeof value === "object" && Object.hasOwn(value, "real")) {
      return `${value.real} + ${value.imag}i · |·|=${value.magnitude} · arg=${value.phase}`;
    }
    return String(value);
  };

  const renderPoint = async () => {
    try {
      const payload = await loadJson(`${root.dataset.pointUrl}?${query({ time: state.time, spatial: state.spatial.join(",") })}`);
      const rows = Object.entries(payload.values)
        .map(([name, value]) => `<tr><th class="text-left pr-4">${name}</th><td>${scalarText(value)}</td></tr>`)
        .join("");
      const coordinates = payload.coordinates
        .map((item) => `${item.name}${item.unit ? ` [${item.unit}]` : ""}: index ${item.index} → ${scalarText(item.value)}`)
        .join(" · ");
      pointContainer.innerHTML = `<p class="text-sm"><strong>t[${payload.time_index}]</strong> = ${scalarText(payload.time_value)}</p><p class="muted text-xs mt-1">${coordinates}</p><table class="table mt-3"><tbody>${rows}</tbody></table>`;
    } catch (error) {
      pointContainer.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  let chart = null;
  const ensureChart = (element) => {
    if (!element) return null;
    if (!chart) {
      chart = echarts.init(element);
      window.addEventListener("resize", () => chart?.resize());
    }
    return chart;
  };

  const renderFieldChart = async () => {
    if (!chartElement) return;
    const instance = ensureChart(chartElement);
    const seriesName = chartElement.dataset.series;
    const representation = currentRepresentation();
    try {
      if (rank === 1) {
        const payload = await loadJson(`${root.dataset.heatmapUrl}?${query({ series: seriesName, representation })}`);
        const data = [];
        payload.values.forEach((row, timePosition) => {
          row.forEach((value, spacePosition) => data.push([spacePosition, timePosition, value]));
        });
        instance.setOption({
          animation: false,
          tooltip: {
            formatter: (item) => `t=${payload.time[item.data[1]]}<br>space=${payload.space[item.data[0]]}<br>${seriesName}=${item.data[2]}`,
          },
          xAxis: { type: "category", name: "space", data: payload.space.map(String) },
          yAxis: { type: "category", name: "time", data: payload.time.map(String) },
          visualMap: { min: Math.min(...payload.values.flat()), max: Math.max(...payload.values.flat()), calculable: true, orient: "horizontal" },
          series: [{ type: "heatmap", data, progressive: 0 }],
        }, true);
        instance.off("click");
        instance.on("click", (event) => {
          state.time = payload.time_indices[event.data[1]];
          state.spatial[0] = payload.space_indices[event.data[0]];
          syncInputs();
          renderPoint();
        });
        const note = root.querySelector("[data-display-note]");
        if (note) note.textContent = `Display-only index sampling: exact shape ${payload.exact_shape.join(" × ")}; exact point inspection remains full resolution.`;
      } else {
        const dimensions = rank >= 2 ? [0, 1] : [0];
        const fixed = [];
        for (let dimension = 0; dimension < rank; dimension += 1) {
          if (!dimensions.includes(dimension)) fixed.push(`${dimension}:${state.spatial[dimension] || 0}`);
        }
        const payload = await loadJson(`${root.dataset.sliceUrl}?${query({
          series: seriesName,
          representation,
          time: state.time,
          dims: dimensions.join(","),
          fixed: fixed.join(","),
        })}`);
        if (payload.axes.length === 1) {
          instance.setOption({
            animation: false,
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
          instance.setOption({
            animation: false,
            tooltip: {
              formatter: (item) => `axis0=${payload.axes[0][item.data[1]]}<br>axis1=${payload.axes[1][item.data[0]]}<br>${seriesName}=${item.data[2]}`,
            },
            xAxis: { type: "category", data: payload.axes[1].map(String) },
            yAxis: { type: "category", data: payload.axes[0].map(String) },
            visualMap: { min: Math.min(...payload.values.flat()), max: Math.max(...payload.values.flat()), calculable: true, orient: "horizontal" },
            series: [{ type: "heatmap", data, progressive: 0 }],
          }, true);
          instance.off("click");
          instance.on("click", (event) => {
            state.spatial[0] = payload.display_indices[0][event.data[1]];
            state.spatial[1] = payload.display_indices[1][event.data[0]];
            syncInputs();
            renderPoint();
          });
        }
        const note = root.querySelector("[data-display-note]");
        if (note) note.textContent = `Display-only sampled slice at exact time index ${state.time}. No spatial averaging or interpolation.`;
      }
    } catch (error) {
      chartElement.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  const renderTrace = async () => {
    if (!traceElement) return;
    const instance = ensureChart(traceElement);
    try {
      const payload = await loadJson(`${root.dataset.traceUrl}?${query({ spatial: state.spatial.join(",") })}`);
      instance.setOption({
        animation: false,
        tooltip: { trigger: "axis" },
        legend: { data: ["u", "|beta_obs|", "|b_obs|"] },
        xAxis: { type: "category", name: "t", data: payload.time.map(String) },
        yAxis: { type: "value" },
        series: [
          { name: "u", type: "line", showSymbol: false, data: payload.u },
          { name: "|beta_obs|", type: "line", showSymbol: false, data: payload.beta_obs.magnitude },
          { name: "|b_obs|", type: "line", showSymbol: false, data: payload.b_obs.magnitude },
        ],
      }, true);
    } catch (error) {
      traceElement.innerHTML = `<div class="alert alert-error">${error.message}</div>`;
    }
  };

  const refresh = () => {
    state.time = clampTime(timeInput.value);
    const parsed = spatialInput.value.split(",").filter((item) => item.trim() !== "").map((item) => Number(item.trim()));
    if (parsed.length === rank && parsed.every(Number.isInteger)) state.spatial = parsed;
    syncInputs();
    renderPoint();
    renderFieldChart();
    renderTrace();
  };

  applyButton?.addEventListener("click", refresh);
  representationSelect?.addEventListener("change", renderFieldChart);
  root.querySelector("[data-time-prev]")?.addEventListener("click", () => { state.time = clampTime(state.time - 1); syncInputs(); refresh(); });
  root.querySelector("[data-time-next]")?.addEventListener("click", () => { state.time = clampTime(state.time + 1); syncInputs(); refresh(); });
  root.querySelector("[data-space-prev]")?.addEventListener("click", () => { state.spatial[0] = Math.max(0, (state.spatial[0] || 0) - 1); syncInputs(); refresh(); });
  root.querySelector("[data-space-next]")?.addEventListener("click", () => { state.spatial[0] = (state.spatial[0] || 0) + 1; syncInputs(); refresh(); });
  root.addEventListener("keydown", (event) => {
    if (!event.altKey) return;
    if (event.key === "ArrowLeft") { event.preventDefault(); state.time = clampTime(state.time - 1); syncInputs(); refresh(); }
    if (event.key === "ArrowRight") { event.preventDefault(); state.time = clampTime(state.time + 1); syncInputs(); refresh(); }
    if (event.key === "ArrowUp") { event.preventDefault(); state.spatial[0] = Math.max(0, (state.spatial[0] || 0) - 1); syncInputs(); refresh(); }
    if (event.key === "ArrowDown") { event.preventDefault(); state.spatial[0] = (state.spatial[0] || 0) + 1; syncInputs(); refresh(); }
  });

  syncInputs();
  renderPoint();
  renderFieldChart();
  renderTrace();
}
