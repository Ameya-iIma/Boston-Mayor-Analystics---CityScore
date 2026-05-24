const API_BASE = "/api/v1";
const PERIODS = ["day", "week", "month", "quarter"];

const state = {
  overview: null,
  alerts: [],
  serviceAreas: [],
  freshness: null,
  metrics: [],
  cityHistory: [],
  cityFocusPeriod: "day",
  filters: {
    severity: "all",
    serviceArea: "all",
    query: "",
  },
  drawer: {
    metricName: null,
    detail: null,
    history: [],
    period: "day",
  },
};

const elements = {
  loadingScreen: document.getElementById("loadingScreen"),
  heroNote: document.getElementById("heroNote"),
  heroSummary: document.getElementById("heroSummary"),
  topCardGrid: document.getElementById("topCardGrid"),
  cityPeriodToggle: document.getElementById("cityPeriodToggle"),
  cityHistoryChart: document.getElementById("cityHistoryChart"),
  cityHistoryInsight: document.getElementById("cityHistoryInsight"),
  criticalAlerts: document.getElementById("criticalAlerts"),
  freshnessSummary: document.getElementById("freshnessSummary"),
  serviceAreaGrid: document.getElementById("serviceAreaGrid"),
  severityFilters: document.getElementById("severityFilters"),
  serviceAreaFilters: document.getElementById("serviceAreaFilters"),
  metricList: document.getElementById("metricList"),
  metricSearchInput: document.getElementById("metricSearchInput"),
  healthChip: document.getElementById("healthChip"),
  asOfChip: document.getElementById("asOfChip"),
  mastheadSubtitle: document.getElementById("mastheadSubtitle"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
  metricDrawer: document.getElementById("metricDrawer"),
  drawerServiceArea: document.getElementById("drawerServiceArea"),
  drawerTitle: document.getElementById("drawerTitle"),
  drawerDefinition: document.getElementById("drawerDefinition"),
  drawerStatStrip: document.getElementById("drawerStatStrip"),
  drawerPeriodToggle: document.getElementById("drawerPeriodToggle"),
  drawerChartShell: document.getElementById("drawerChartShell"),
  periodSnapshotGrid: document.getElementById("periodSnapshotGrid"),
  drawerReasons: document.getElementById("drawerReasons"),
};


document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadDashboard();
});


function bindEvents() {
  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
    }
  });

  elements.metricSearchInput.addEventListener("input", (event) => {
    state.filters.query = event.target.value.trim().toLowerCase();
    renderMetricList();
  });
}


async function loadDashboard({ refresh = false } = {}) {
  toggleLoading(true);
  try {
    if (refresh) {
      await fetchJson(`${API_BASE}/pipeline/refresh`, { method: "POST" });
    }

    const [overview, alerts, serviceAreas, freshness, metrics, cityHistory] = await Promise.all([
      fetchJson(`${API_BASE}/dashboard/overview`),
      fetchJson(`${API_BASE}/dashboard/alerts?limit=50`),
      fetchJson(`${API_BASE}/dashboard/service-areas`),
      fetchJson(`${API_BASE}/dashboard/freshness`),
      fetchJson(`${API_BASE}/metrics`),
      fetchJson(`${API_BASE}/dashboard/city-history?days=240`),
    ]);

    state.overview = overview;
    state.alerts = alerts;
    state.serviceAreas = serviceAreas;
    state.freshness = freshness;
    state.metrics = metrics;
    state.cityHistory = cityHistory;
    state.cityFocusPeriod = state.cityFocusPeriod || "day";

    renderDashboard();
  } catch (error) {
    console.error(error);
    renderLoadError(error);
  } finally {
    toggleLoading(false);
  }
}


async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (error) {
      // Ignore JSON parsing failures for non-JSON responses.
    }
    throw new Error(detail);
  }

  return response.json();
}


function renderDashboard() {
  renderHero();
  renderTopCards();
  renderCityHistory();
  renderCriticalAlerts();
  renderFreshness();
  renderServiceAreas();
  renderFilterControls();
  renderMetricList();
}


function renderHero() {
  const overview = state.overview;
  const freshness = state.freshness;

  elements.healthChip.textContent = freshness?.actionable_alerts
    ? `${freshness.actionable_alerts} active alerts`
    : "No active alerts";
  elements.asOfChip.textContent = `As of: ${formatDate(overview?.as_of_date)}`;
  elements.mastheadSubtitle.textContent = `Tracking ${freshness?.metrics_total ?? 0} metrics across ${state.serviceAreas.length} service areas.`;
  elements.heroNote.textContent = overview?.note || "CityScore note unavailable.";

  const changeSummary = overview?.change_summary || {};
  const freshnessStats = [
    {
      label: "Actionable alerts",
      value: freshness?.actionable_alerts ?? 0,
      foot: "Red, amber, or data issues",
    },
    {
      label: "Improving metrics",
      value: changeSummary.improving_metrics ?? 0,
      foot: "Better than the previous valid score",
    },
    {
      label: "Worsening metrics",
      value: changeSummary.worsening_metrics ?? 0,
      foot: "Needs closer review today",
    },
    {
      label: "Coverage today",
      value: `${freshness?.metrics_with_selected_score ?? 0}/${freshness?.metrics_total ?? 0}`,
      foot: "Metrics with a current selected score",
    },
  ];

  elements.heroSummary.innerHTML = freshnessStats
    .map(
      (item) => `
        <article class="summary-tile">
          <span class="summary-label">${escapeHtml(item.label)}</span>
          <strong class="summary-value" data-animate-number="${escapeHtml(String(item.value))}">${escapeHtml(String(item.value))}</strong>
          <span class="summary-foot">${escapeHtml(item.foot)}</span>
        </article>
      `
    )
    .join("");

  animateNumericElements(elements.heroSummary.querySelectorAll("[data-animate-number]"));
}


function renderTopCards() {
  const cards = state.overview?.top_cards || [];
  elements.topCardGrid.innerHTML = cards
    .map((card) => {
      const points = getCityHistoryForPeriod(card.period_type).slice(-24);
      const deltaClass = (card.change ?? 0) >= 0 ? "up" : "down";
      return `
        <article class="top-card">
          <div class="top-card-label">
            <span class="period-name">${escapeHtml(titleCase(card.period_type))}</span>
            ${renderSeverityPill(card.status)}
          </div>
          <div class="score-line">
            <strong class="score-value" data-animate-number="${formatScore(card.score)}">${formatScore(card.score)}</strong>
            <span class="delta-chip ${deltaClass}">
              ${formatSigned(card.change)}
            </span>
          </div>
          <div class="sparkline-shell">
            ${renderSparkline(points.map((point) => point.score), {
              width: 360,
              height: 88,
              stroke: severityColor(card.status),
            })}
          </div>
          <div class="sparkline-caption">
            <span>Previous: ${formatScore(card.previous_score)}</span>
            <span>${points.length} points</span>
          </div>
        </article>
      `;
    })
    .join("");

  animateNumericElements(elements.topCardGrid.querySelectorAll("[data-animate-number]"));
}


function renderCityHistory() {
  const periodButtons = PERIODS.map(
    (period) => `
      <button
        type="button"
        class="chip-button ${state.cityFocusPeriod === period ? "is-active" : ""}"
        data-city-period="${period}"
      >
        ${escapeHtml(titleCase(period))}
      </button>
    `
  ).join("");

  elements.cityPeriodToggle.innerHTML = periodButtons;

  const points = getCityHistoryForPeriod(state.cityFocusPeriod);
  const latestPoint = points[points.length - 1];
  const previousPoint = points[points.length - 2];
  elements.cityHistoryChart.innerHTML = renderLargeChart({
    title: `${titleCase(state.cityFocusPeriod)} CityScore`,
    subtitle: `${points.length} observations in view`,
    values: points.map((point) => point.score),
    dates: points.map((point) => formatDate(point.as_of_date, { month: "short", day: "numeric" })),
    targetValue: 1,
    lineColor: "var(--forest-deep)",
  });

  elements.cityHistoryInsight.innerHTML = `
    <div class="insight-stat">
      <span class="insight-label">Current score</span>
      <strong class="insight-value">${formatScore(latestPoint?.score)}</strong>
    </div>
    <div class="insight-stat">
      <span class="insight-label">Change from previous</span>
      <strong class="insight-value">${formatSigned(latestPoint?.change)}</strong>
    </div>
    <div class="insight-stat">
      <span class="insight-label">Previous reading</span>
      <strong class="insight-value">${formatScore(previousPoint?.score)}</strong>
    </div>
    <div class="insight-stat">
      <span class="insight-label">Decision threshold</span>
      <strong class="insight-value">1.00</strong>
    </div>
  `;
}


function renderCriticalAlerts() {
  const alerts = state.overview?.critical_alerts || [];
  if (!alerts.length) {
    elements.criticalAlerts.innerHTML = `<div class="empty-state">No priority alerts right now.</div>`;
    return;
  }

  elements.criticalAlerts.innerHTML = alerts
    .map(
      (alert) => `
        <article class="alert-card is-clickable" data-open-metric="${escapeHtml(alert.metric_name)}">
          <div class="alert-head">
            <div>
              <h4 class="alert-title">${escapeHtml(alert.display_name)}</h4>
              <div class="alert-meta">
                <span>${escapeHtml(alert.service_area)}</span>
                <span>${escapeHtml(titleCase(alert.selected_period || "unknown"))}</span>
                <span>${formatDate(alert.as_of_date)}</span>
              </div>
            </div>
            ${renderSeverityPill(alert.severity)}
          </div>
          <div class="kpi-strip">
            <div class="kpi-tile">
              <span class="kpi-label">Current score</span>
              <strong class="kpi-value">${formatScore(alert.current_score)}</strong>
            </div>
            <div class="kpi-tile">
              <span class="kpi-label">Change</span>
              <strong class="kpi-value">${formatSigned(alert.change_vs_previous)}</strong>
            </div>
          </div>
          <div class="alert-reasons">
            ${alert.alert_reasons.map((reason) => `<span class="reason-pill">${escapeHtml(reason)}</span>`).join("")}
          </div>
        </article>
      `
    )
    .join("");
}


function renderFreshness() {
  const freshness = state.freshness;
  if (!freshness) {
    elements.freshnessSummary.innerHTML = `<div class="empty-state">Freshness data unavailable.</div>`;
    return;
  }

  elements.freshnessSummary.innerHTML = `
    <div class="kpi-strip">
      <div class="kpi-tile">
        <span class="kpi-label">Metrics total</span>
        <strong class="kpi-value">${freshness.metrics_total}</strong>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Missing day scores</span>
        <strong class="kpi-value">${freshness.metrics_missing_day_score}</strong>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Selected scores ready</span>
        <strong class="kpi-value">${freshness.metrics_with_selected_score}</strong>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Stale metrics</span>
        <strong class="kpi-value">${freshness.stale_metrics}</strong>
      </div>
    </div>
    <div class="alert-reasons" style="margin-top: 1rem;">
      ${freshness.coverage_by_service_area
        .map(
          (item) => `
            <span class="reason-pill">
              ${escapeHtml(item.service_area)}: ${item.metrics_with_selected_score}/${item.total_metrics}
            </span>
          `
        )
        .join("")}
    </div>
  `;
}


function renderServiceAreas() {
  if (!state.serviceAreas.length) {
    elements.serviceAreaGrid.innerHTML = `<div class="empty-state">No service area summaries available.</div>`;
    return;
  }

  elements.serviceAreaGrid.innerHTML = state.serviceAreas
    .map((serviceArea) => {
      const total = serviceArea.metric_count || 1;
      const segments = [
        { key: "red", count: serviceArea.red_count },
        { key: "amber", count: serviceArea.amber_count },
        { key: "blue", count: serviceArea.blue_count },
        { key: "green", count: serviceArea.green_count },
      ];

      return `
        <article class="service-card is-clickable" data-filter-service-area="${escapeHtml(serviceArea.service_area)}">
          <div>
            <h4>${escapeHtml(serviceArea.service_area)}</h4>
            <div class="mini-meta">
              <span>${serviceArea.metric_count} metrics</span>
              <span>${serviceArea.red_count + serviceArea.amber_count} active concerns</span>
            </div>
          </div>
          <div class="service-score">${formatScore(serviceArea.selected_score_average)}</div>
          <div class="stacked-bar">
            ${segments
              .map(
                (segment) => `
                  <span class="${segment.key}" style="width:${(segment.count / total) * 100}%"></span>
                `
              )
              .join("")}
          </div>
          <div class="service-legend">
            <span>Red ${serviceArea.red_count}</span>
            <span>Amber ${serviceArea.amber_count}</span>
            <span>Blue ${serviceArea.blue_count}</span>
            <span>Green ${serviceArea.green_count}</span>
          </div>
        </article>
      `;
    })
    .join("");
}


function renderFilterControls() {
  const severityOptions = ["all", "red", "amber", "blue", "green"];
  elements.severityFilters.innerHTML = severityOptions
    .map(
      (severity) => `
        <button
          type="button"
          class="chip-button ${state.filters.severity === severity ? "is-active" : ""}"
          data-filter-severity="${severity}"
        >
          ${escapeHtml(titleCase(severity))}
        </button>
      `
    )
    .join("");

  const serviceOptions = ["all", ...state.serviceAreas.map((item) => item.service_area)];
  elements.serviceAreaFilters.innerHTML = serviceOptions
    .map(
      (serviceArea) => `
        <button
          type="button"
          class="chip-button ${state.filters.serviceArea === serviceArea ? "is-active" : ""}"
          data-filter-service-area="${escapeHtml(serviceArea)}"
        >
          ${escapeHtml(serviceArea === "all" ? "All Areas" : serviceArea)}
        </button>
      `
    )
    .join("");
}


function renderMetricList() {
  const filteredMetrics = state.metrics.filter((metric) => {
    const matchesSeverity =
      state.filters.severity === "all" || metric.severity === state.filters.severity;
    const matchesServiceArea =
      state.filters.serviceArea === "all" || metric.service_area === state.filters.serviceArea;
    const query = state.filters.query;
    const matchesQuery =
      !query ||
      metric.metric_name.toLowerCase().includes(query) ||
      metric.display_name.toLowerCase().includes(query) ||
      metric.service_area.toLowerCase().includes(query);
    return matchesSeverity && matchesServiceArea && matchesQuery;
  });

  if (!filteredMetrics.length) {
    elements.metricList.innerHTML = `<div class="empty-state">No metrics match the current filters.</div>`;
    return;
  }

  elements.metricList.innerHTML = filteredMetrics
    .map(
      (metric) => `
        <article class="metric-row is-clickable" data-open-metric="${escapeHtml(metric.metric_name)}">
          <div class="metric-name-cell">
            <strong>${escapeHtml(metric.display_name)}</strong>
            <span>${escapeHtml(metric.service_area)} · ${escapeHtml(metric.owner_department)}</span>
          </div>
          <div class="metric-period">${escapeHtml(titleCase(metric.selected_period || "n/a"))}</div>
          <div class="metric-value">${formatScore(metric.current_score)}</div>
          <div class="metric-change">${formatSigned(metric.change_vs_previous)}</div>
          <div class="metric-severity">${renderSeverityPill(metric.severity)}</div>
        </article>
      `
    )
    .join("");
}


async function openMetricDrawer(metricName) {
  state.drawer.metricName = metricName;
  state.drawer.detail = null;
  state.drawer.history = [];
  renderDrawerLoading(metricName);
  document.body.classList.add("drawer-open");
  elements.drawerBackdrop.classList.add("is-open");
  elements.metricDrawer.classList.add("is-open");
  elements.metricDrawer.setAttribute("aria-hidden", "false");

  try {
    const detail = await fetchJson(`${API_BASE}/metrics/${encodeURIComponent(metricName)}`);
    const period = detail.selected_period || "week";
    const history = await fetchJson(
      `${API_BASE}/metrics/${encodeURIComponent(metricName)}/history?period_type=${period}&days=180`
    );

    state.drawer.detail = detail;
    state.drawer.period = period;
    state.drawer.history = history;
    renderDrawer();
  } catch (error) {
    console.error(error);
    elements.drawerDefinition.textContent = `Unable to load metric details: ${error.message}`;
  }
}


async function changeDrawerPeriod(period) {
  if (!state.drawer.metricName) {
    return;
  }
  state.drawer.period = period;
  elements.drawerChartShell.innerHTML = `<div class="chart-placeholder">Loading ${titleCase(period)} trend...</div>`;

  try {
    state.drawer.history = await fetchJson(
      `${API_BASE}/metrics/${encodeURIComponent(state.drawer.metricName)}/history?period_type=${period}&days=180`
    );
    renderDrawer();
  } catch (error) {
    console.error(error);
    elements.drawerChartShell.innerHTML = `<div class="chart-placeholder">${escapeHtml(error.message)}</div>`;
  }
}


function renderDrawerLoading(metricName) {
  elements.drawerServiceArea.textContent = "Loading metric";
  elements.drawerTitle.textContent = metricName;
  elements.drawerDefinition.textContent = "Pulling historical movement and the latest alert context.";
  elements.drawerStatStrip.innerHTML = "";
  elements.drawerPeriodToggle.innerHTML = "";
  elements.drawerChartShell.innerHTML = `<div class="chart-placeholder">Loading metric drill-down...</div>`;
  elements.periodSnapshotGrid.innerHTML = "";
  elements.drawerReasons.innerHTML = "";
}


function renderDrawer() {
  const detail = state.drawer.detail;
  if (!detail) {
    return;
  }

  elements.drawerServiceArea.textContent = detail.service_area;
  elements.drawerTitle.textContent = detail.display_name;
  elements.drawerDefinition.textContent = detail.definition;

  elements.drawerStatStrip.innerHTML = [
    {
      label: "Current score",
      value: formatScore(detail.current_score),
    },
    {
      label: "Change",
      value: formatSigned(detail.change_vs_previous),
    },
    {
      label: "Rolling 14",
      value: formatScore(detail.rolling_mean_14),
    },
    {
      label: "Target",
      value: formatScore(detail.target),
    },
  ]
    .map(
      (item) => `
        <article class="drawer-stat-tile">
          <span class="stat-label">${escapeHtml(item.label)}</span>
          <strong class="stat-value">${escapeHtml(item.value)}</strong>
        </article>
      `
    )
    .join("");

  elements.drawerPeriodToggle.innerHTML = PERIODS.map(
    (period) => `
      <button
        type="button"
        class="chip-button ${state.drawer.period === period ? "is-active" : ""}"
        data-drawer-period="${period}"
      >
        ${escapeHtml(titleCase(period))}
      </button>
    `
  ).join("");

  elements.drawerChartShell.innerHTML = renderLargeChart({
    title: `${detail.display_name} · ${titleCase(state.drawer.period)}`,
    subtitle: `${state.drawer.history.length} points over the recent window`,
    values: state.drawer.history.map((point) => point.score),
    dates: state.drawer.history.map((point) => formatDate(point.as_of_date, { month: "short", day: "numeric" })),
    targetValue: detail.target ?? 1,
    lineColor: severityColor(detail.severity),
  });

  elements.periodSnapshotGrid.innerHTML = detail.period_snapshots
    .map(
      (snapshot) => `
        <article class="period-card">
          <span class="period-card-label">${escapeHtml(titleCase(snapshot.period_type))}</span>
          <div class="period-card-value">${formatScore(snapshot.score)}</div>
          <div class="mini-meta">
            <span>Primary ${formatScore(snapshot.primary_value)}</span>
            <span>Secondary ${formatScore(snapshot.secondary_value)}</span>
          </div>
        </article>
      `
    )
    .join("");

  elements.drawerReasons.innerHTML = (detail.alert_reasons || [])
    .map((reason) => `<span class="reason-pill">${escapeHtml(reason)}</span>`)
    .join("");
}


function closeDrawer() {
  document.body.classList.remove("drawer-open");
  elements.drawerBackdrop.classList.remove("is-open");
  elements.metricDrawer.classList.remove("is-open");
  elements.metricDrawer.setAttribute("aria-hidden", "true");
}


function handleDocumentClick(event) {
  const refreshButton = event.target.closest('[data-action="refresh"]');
  if (refreshButton) {
    loadDashboard({ refresh: true });
    return;
  }

  const openMetricTarget = event.target.closest("[data-open-metric]");
  if (openMetricTarget) {
    openMetricDrawer(openMetricTarget.dataset.openMetric);
    return;
  }

  const severityFilterTarget = event.target.closest("[data-filter-severity]");
  if (severityFilterTarget) {
    state.filters.severity = severityFilterTarget.dataset.filterSeverity;
    renderFilterControls();
    renderMetricList();
    return;
  }

  const serviceAreaTarget = event.target.closest("[data-filter-service-area]");
  if (serviceAreaTarget) {
    state.filters.serviceArea = serviceAreaTarget.dataset.filterServiceArea;
    renderFilterControls();
    renderMetricList();
    return;
  }

  const cityPeriodTarget = event.target.closest("[data-city-period]");
  if (cityPeriodTarget) {
    state.cityFocusPeriod = cityPeriodTarget.dataset.cityPeriod;
    renderCityHistory();
    return;
  }

  const drawerPeriodTarget = event.target.closest("[data-drawer-period]");
  if (drawerPeriodTarget) {
    changeDrawerPeriod(drawerPeriodTarget.dataset.drawerPeriod);
    return;
  }

  if (
    event.target.closest('[data-action="close-drawer"]') ||
    event.target === elements.drawerBackdrop
  ) {
    closeDrawer();
  }
}


function toggleLoading(isLoading) {
  elements.loadingScreen.classList.toggle("is-hidden", !isLoading);
}


function renderLoadError(error) {
  elements.healthChip.textContent = "Data unavailable";
  elements.heroNote.textContent = `Dashboard load failed: ${error.message}`;
  elements.topCardGrid.innerHTML = `<div class="empty-state">Unable to render top cards.</div>`;
}


function getCityHistoryForPeriod(period) {
  return state.cityHistory.filter((item) => item.period_type === period);
}


function renderLargeChart({ title, subtitle, values, dates, targetValue, lineColor }) {
  const validValues = values.filter((value) => typeof value === "number");
  if (!validValues.length) {
    return `<div class="chart-placeholder">Not enough data to draw this trend.</div>`;
  }

  const width = 760;
  const height = 280;
  const padding = 18;
  const path = buildLinePath(values, width, height, padding);
  const areaPath = buildAreaPath(values, width, height, padding);
  const minValue = Math.min(...validValues, targetValue ?? Math.min(...validValues));
  const maxValue = Math.max(...validValues, targetValue ?? Math.max(...validValues));
  const targetY =
    typeof targetValue === "number"
      ? projectY(targetValue, minValue, maxValue, height, padding)
      : null;
  const latestValue = values[values.length - 1];

  return `
    <div class="chart-title">
      <h4>${escapeHtml(title)}</h4>
      <span>${escapeHtml(subtitle)}</span>
    </div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)} chart">
      <defs>
        <linearGradient id="areaGradient-${slugify(title)}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${lineColor}" stop-opacity="0.26"></stop>
          <stop offset="100%" stop-color="${lineColor}" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="rgba(255,255,255,0.24)"></rect>
      ${targetY !== null ? `<line x1="${padding}" y1="${targetY}" x2="${width - padding}" y2="${targetY}" stroke="rgba(157,107,21,0.6)" stroke-dasharray="6 6" stroke-width="2"></line>` : ""}
      <path d="${areaPath}" fill="url(#areaGradient-${slugify(title)})"></path>
      <path d="${path}" fill="none" stroke="${lineColor}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
      <circle cx="${projectX(values.length - 1, values.length, width, padding)}" cy="${projectY(latestValue, minValue, maxValue, height, padding)}" r="6" fill="${lineColor}" stroke="rgba(255,255,255,0.95)" stroke-width="3"></circle>
    </svg>
    <div class="chart-caption">
      <span>${escapeHtml(dates[0] || "Start")}</span>
      <span>Threshold ${typeof targetValue === "number" ? formatScore(targetValue) : "n/a"}</span>
      <span>${escapeHtml(dates[dates.length - 1] || "Latest")}</span>
    </div>
  `;
}


function renderSparkline(values, { width, height, stroke }) {
  const validValues = values.filter((value) => typeof value === "number");
  if (!validValues.length) {
    return `<div class="chart-placeholder">No trend data yet.</div>`;
  }

  const padding = 8;
  const path = buildLinePath(values, width, height, padding);
  const areaPath = buildAreaPath(values, width, height, padding);
  const latestValue = values[values.length - 1];
  const minValue = Math.min(...validValues);
  const maxValue = Math.max(...validValues);

  return `
    <svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <defs>
        <linearGradient id="spark-fill-${Math.random().toString(36).slice(2)}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${stroke}" stop-opacity="0.22"></stop>
          <stop offset="100%" stop-color="${stroke}" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <path d="${areaPath}" fill="rgba(48,109,41,0.12)"></path>
      <path d="${path}" fill="none" stroke="${stroke}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
      <circle cx="${projectX(values.length - 1, values.length, width, padding)}" cy="${projectY(latestValue, minValue, maxValue, height, padding)}" r="4.5" fill="${stroke}" stroke="rgba(255,255,255,0.9)" stroke-width="2"></circle>
    </svg>
  `;
}


function buildLinePath(values, width, height, padding) {
  const validValues = values.filter((value) => typeof value === "number");
  const minValue = Math.min(...validValues);
  const maxValue = Math.max(...validValues);

  return values
    .map((value, index) => {
      const x = projectX(index, values.length, width, padding);
      const y = projectY(value, minValue, maxValue, height, padding);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}


function buildAreaPath(values, width, height, padding) {
  const validValues = values.filter((value) => typeof value === "number");
  const minValue = Math.min(...validValues);
  const maxValue = Math.max(...validValues);
  const baseline = height - padding;
  const startX = projectX(0, values.length, width, padding);
  const endX = projectX(values.length - 1, values.length, width, padding);
  const linePath = buildLinePath(values, width, height, padding);
  return `${linePath} L ${endX} ${baseline} L ${startX} ${baseline} Z`;
}


function projectX(index, length, width, padding) {
  if (length <= 1) {
    return width / 2;
  }
  return padding + (index * (width - padding * 2)) / (length - 1);
}


function projectY(value, minValue, maxValue, height, padding) {
  if (typeof value !== "number") {
    return height - padding;
  }
  if (minValue === maxValue) {
    return height / 2;
  }
  const ratio = (value - minValue) / (maxValue - minValue);
  return height - padding - ratio * (height - padding * 2);
}


function animateNumericElements(nodes) {
  nodes.forEach((node) => {
    const rawTarget = node.dataset.animateNumber;
    if (!/^-?\d+(\.\d+)?$/.test(rawTarget)) {
      return;
    }
    const targetValue = parseFloat(rawTarget);
    if (Number.isNaN(targetValue)) {
      return;
    }
    const startTime = performance.now();
    const duration = 900;
    const decimalPlaces = rawTarget.includes(".") ? Math.min(rawTarget.split(".")[1].length, 2) : 0;

    function tick(timestamp) {
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = targetValue * eased;
      node.textContent = current.toFixed(decimalPlaces);
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        node.textContent = rawTarget;
      }
    }

    requestAnimationFrame(tick);
  });
}


function renderSeverityPill(severity) {
  return `<span class="severity-pill ${escapeHtml(severity || "blue")}">${escapeHtml(titleCase(severity || "unknown"))}</span>`;
}


function severityColor(severity) {
  switch (severity) {
    case "red":
      return "#8f2c2c";
    case "amber":
      return "#9d6b15";
    case "blue":
      return "#355f82";
    default:
      return "#0d530e";
  }
}


function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(2);
}


function formatSigned(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const numeric = Number(value);
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`;
}


function formatDate(value, options = {}) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    ...options,
  }).format(date);
}


function titleCase(value) {
  if (!value) {
    return "Unknown";
  }
  return String(value)
    .replace(/_/g, " ")
    .split(" ")
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}


function slugify(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-");
}


function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
