const API_BASE = "/api/v1";
const PERIODS = ["day", "week", "month", "quarter"];

const state = {
  executiveBrief: null,
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
  headlineStatus: document.getElementById("headlineStatus"),
  heroHeadline: document.getElementById("heroHeadline"),
  heroSupport: document.getElementById("heroSupport"),
  heroGuide: document.getElementById("heroGuide"),
  heroSummary: document.getElementById("heroSummary"),
  portfolioHealthPanel: document.getElementById("portfolioHealthPanel"),
  performanceBandsChart: document.getElementById("performanceBandsChart"),
  trendDistributionChart: document.getElementById("trendDistributionChart"),
  dataScopeSummary: document.getElementById("dataScopeSummary"),
  portfolioMix: document.getElementById("portfolioMix"),
  bestServicesList: document.getElementById("bestServicesList"),
  worstServicesList: document.getElementById("worstServicesList"),
  compositeLeadersList: document.getElementById("compositeLeadersList"),
  compositeLaggardsList: document.getElementById("compositeLaggardsList"),
  rankedServicesChart: document.getElementById("rankedServicesChart"),
  departmentSummary: document.getElementById("departmentSummary"),
  recommendationsList: document.getElementById("recommendationsList"),
  methodologyList: document.getElementById("methodologyList"),
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

    const [executiveBrief, overview, alerts, serviceAreas, freshness, metrics, cityHistory] = await Promise.all([
      fetchJson(`${API_BASE}/dashboard/executive-brief`),
      fetchJson(`${API_BASE}/dashboard/overview`),
      fetchJson(`${API_BASE}/dashboard/alerts?limit=50`),
      fetchJson(`${API_BASE}/dashboard/service-areas`),
      fetchJson(`${API_BASE}/dashboard/freshness`),
      fetchJson(`${API_BASE}/metrics`),
      fetchJson(`${API_BASE}/dashboard/city-history?days=240`),
    ]);

    state.executiveBrief = executiveBrief;
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
  renderPortfolioDiagnostics();
  renderExecutiveScope();
  renderExecutiveRankings();
  renderCompositeRankings();
  renderPortfolioDetails();
  renderExecutiveStrategy();
  renderTopCards();
  renderCityHistory();
  renderCriticalAlerts();
  renderFreshness();
  renderServiceAreas();
  renderFilterControls();
  renderMetricList();
}


function renderHero() {
  const brief = state.executiveBrief;
  const overview = state.overview;
  const freshness = state.freshness;

  const status = brief?.headline_status || "mixed";
  elements.healthChip.textContent = `Portfolio ${titleCase(status)}`;
  elements.healthChip.className = `status-chip ${statusToneClass(status)}`;
  elements.asOfChip.textContent = `As of: ${formatDate(overview?.as_of_date)}`;
  elements.mastheadSubtitle.textContent = brief
    ? `Using ${brief.data_scope.services_ranked} ranked services across ${brief.data_scope.snapshot_dates} recent Full Metric List snapshots.`
    : `Tracking ${freshness?.metrics_total ?? 0} metrics across ${state.serviceAreas.length} service areas.`;

  elements.headlineStatus.textContent = titleCase(status);
  elements.headlineStatus.className = `status-banner ${statusToneClass(status)}`;
  elements.heroHeadline.textContent =
    brief?.headline_text || "Preparing the state-of-city-services briefing.";
  elements.heroSupport.textContent =
    brief?.supporting_text || overview?.note || "CityScore context unavailable.";

  elements.heroGuide.innerHTML = (brief?.score_guide || [])
    .map((item) => `<span class="reason-pill">${escapeHtml(item)}</span>`)
    .join("");

  const heroCards = brief?.kpi_cards || [];
  elements.heroSummary.innerHTML = heroCards
    .map(
      (item) => {
        const value = String(item.value);
        const animateAttr = /^-?\d+(\.\d+)?$/.test(value)
          ? ` data-animate-number="${escapeHtml(value)}"`
          : "";
        return `
        <article class="summary-tile">
          <span class="summary-label">${escapeHtml(item.label)}</span>
          <strong class="summary-value"${animateAttr}>${escapeHtml(value)}</strong>
          <span class="summary-foot">${escapeHtml(item.detail)}</span>
        </article>
      `;
      }
    )
    .join("");

  animateNumericElements(elements.heroSummary.querySelectorAll("[data-animate-number]"));
}


function renderPortfolioDiagnostics() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.portfolioHealthPanel.innerHTML = `<div class="empty-state">Portfolio diagnostics unavailable.</div>`;
    elements.performanceBandsChart.innerHTML = `<div class="empty-state">Performance bands unavailable.</div>`;
    elements.trendDistributionChart.innerHTML = `<div class="empty-state">Trend distribution unavailable.</div>`;
    return;
  }

  renderPortfolioHealthPanel(brief.portfolio_health);
  renderPerformanceBandsChart(brief.performance_bands);
  renderTrendDistributionChart(brief.trend_distribution);
}


function renderPortfolioHealthPanel(health) {
  if (!health) {
    elements.portfolioHealthPanel.innerHTML = `<div class="empty-state">Portfolio health score unavailable.</div>`;
    return;
  }

  const scorePercent = Math.max(0, Math.min(health.score, 100));
  elements.portfolioHealthPanel.innerHTML = `
    <div class="health-score-layout">
      <div class="health-gauge-shell">
        <div class="health-gauge" style="--score:${scorePercent}; --tone:${health.verdict_color};">
          <div class="health-gauge-core">
            <strong>${escapeHtml(String(Math.round(health.score)))}</strong>
            <span>/ 100</span>
            <div class="health-gauge-verdict">${escapeHtml(titleCase(health.verdict))}</div>
          </div>
        </div>
        <div class="health-footnote">
          <span>${formatPercent(health.pass_rate_pct / 100)} at or above target</span>
          <span>${formatPercent(health.below_target_pct / 100)} below target</span>
        </div>
      </div>
      <div class="health-components">
        ${(health.components || [])
          .map(
            (component) => `
              <article class="health-component-card">
                <div class="health-component-head">
                  <span class="summary-label">${escapeHtml(component.label)}</span>
                  <strong class="health-component-score">${formatSigned(component.score)}</strong>
                </div>
                <p class="strategy-copy">${escapeHtml(component.detail)}</p>
              </article>
            `
          )
          .join("")}
        <article class="health-component-card">
          <div class="health-component-head">
            <span class="summary-label">Central Tendency</span>
            <strong class="health-component-score">${formatScore(health.median_score)}</strong>
          </div>
          <p class="strategy-copy">Median service score with mean at ${formatScore(health.mean_score)} across ${health.total_services} rankable services.</p>
        </article>
      </div>
    </div>
  `;
}


function renderPerformanceBandsChart(bands) {
  if (!bands?.length) {
    elements.performanceBandsChart.innerHTML = `<div class="empty-state">Performance band data unavailable.</div>`;
    return;
  }

  const total = bands.reduce((sum, item) => sum + Number(item.count || 0), 0) || 1;
  let start = 0;
  const slices = bands
    .filter((item) => item.count > 0)
    .map((item) => {
      const ratio = Number(item.count) / total;
      const end = start + ratio;
      const color = performanceBandColor(item.band);
      const slice = `${color} ${start * 100}% ${end * 100}%`;
      start = end;
      return slice;
    })
    .join(", ");

  elements.performanceBandsChart.innerHTML = `
    <div class="distribution-layout">
      <div class="donut-shell">
        <div class="distribution-donut" style="--distribution:${slices || 'rgba(13,83,14,0.12) 0% 100%'};">
          <div class="distribution-donut-core">
            <strong>${total}</strong>
            <span>services</span>
          </div>
        </div>
      </div>
      <div class="distribution-legend">
        ${bands
          .map(
            (item) => `
              <article class="legend-row">
                <div class="legend-title">
                  <span class="legend-dot" style="background:${performanceBandColor(item.band)}"></span>
                  <strong>${escapeHtml(item.band)}</strong>
                </div>
                <div class="legend-meta">
                  <span>${item.count}</span>
                  <span>${formatPercent(item.percentage / 100)}</span>
                  <span>${escapeHtml(item.threshold)}</span>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}


function renderTrendDistributionChart(items) {
  if (!items?.length) {
    elements.trendDistributionChart.innerHTML = `<div class="empty-state">Trend distribution unavailable.</div>`;
    return;
  }

  const maxCount = Math.max(...items.map((item) => Number(item.count || 0)), 1);
  elements.trendDistributionChart.innerHTML = `
    <div class="trend-stack">
      ${items
        .map((item) => {
          const width = (Number(item.count || 0) / maxCount) * 100;
          return `
            <article class="trend-row-card">
              <div class="trend-row-head">
                <strong>${escapeHtml(item.label)}</strong>
                <span>${item.count} services · ${formatPercent(item.percentage / 100)}</span>
              </div>
              <div class="animated-bar">
                <span class="${slugify(item.label)}" style="--target-width:${width}%"></span>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}


function renderExecutiveScope() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.dataScopeSummary.innerHTML = `<div class="empty-state">Executive scope is unavailable.</div>`;
    elements.portfolioMix.innerHTML = `<div class="empty-state">Portfolio mix is unavailable.</div>`;
    return;
  }

  const scope = brief.data_scope;
  const scopeStats = [
    { label: "Source Focus", value: scope.source_focus, foot: "Primary analytical dataset" },
    {
      label: "Data Period",
      value: `${formatDate(scope.analysis_start_date, { month: "short", day: "numeric" })} to ${formatDate(scope.analysis_end_date, { month: "short", day: "numeric" })}`,
      foot: `${scope.snapshot_dates} snapshot dates in the Full Metric List`,
    },
    {
      label: "Services Ranked",
      value: `${scope.services_ranked}/${scope.services_in_scope}`,
      foot: "Services with a current score suitable for ranking",
    },
    {
      label: "Download Date",
      value: formatDate(scope.download_date),
      foot: "Documented because CityScore feeds can update over time",
    },
  ];

  elements.dataScopeSummary.innerHTML = `
    <div class="scope-grid">
      ${scopeStats
        .map(
          (item) => `
            <article class="scope-card">
              <span class="summary-label">${escapeHtml(item.label)}</span>
              <strong class="scope-value">${escapeHtml(item.value)}</strong>
              <span class="summary-foot">${escapeHtml(item.foot)}</span>
            </article>
          `
        )
        .join("")}
    </div>
    <p class="scope-note">${escapeHtml(scope.reading_note)}</p>
  `;

  const total = Object.values(brief.portfolio_mix || {}).reduce((sum, value) => sum + Number(value || 0), 0) || 1;
  elements.portfolioMix.innerHTML = `
    <div class="portfolio-mix-list">
      ${Object.entries(brief.portfolio_mix || {})
        .map(([bucket, count]) => {
          const share = (Number(count || 0) / total) * 100;
          return `
            <article class="mix-card">
              <div class="mix-head">
                <div>
                  <strong>${escapeHtml(bucket)}</strong>
                  <span>${formatPercent(share / 100)} of services</span>
                </div>
                ${renderConsultingBucketPill(bucket)}
              </div>
              <div class="mix-value">${escapeHtml(String(count))}</div>
              <div class="mix-bar"><span style="width:${share}%"></span></div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}


function renderExecutiveRankings() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.bestServicesList.innerHTML = `<div class="empty-state">Best-service ranking unavailable.</div>`;
    elements.worstServicesList.innerHTML = `<div class="empty-state">Worst-service ranking unavailable.</div>`;
    return;
  }

  elements.bestServicesList.innerHTML = renderRankedServiceCards(brief.best_services, "best");
  elements.worstServicesList.innerHTML = renderRankedServiceCards(brief.worst_services, "worst");
}


function renderCompositeRankings() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.compositeLeadersList.innerHTML = `<div class="empty-state">Operational standouts unavailable.</div>`;
    elements.compositeLaggardsList.innerHTML = `<div class="empty-state">Pressure-point ranking unavailable.</div>`;
    return;
  }

  elements.compositeLeadersList.innerHTML = renderRankedServiceCards(brief.composite_leaders, "best", {
    scoreLabel: "Portfolio score",
    trendLabel: "Momentum",
    scoreField: "composite_score",
    trendField: "trend_delta_wq",
    badgeField: "perf_band",
  });
  elements.compositeLaggardsList.innerHTML = renderRankedServiceCards(brief.composite_laggards, "worst", {
    scoreLabel: "Portfolio score",
    trendLabel: "Momentum",
    scoreField: "composite_score",
    trendField: "trend_delta_wq",
    badgeField: "perf_band",
  });
}


function renderPortfolioDetails() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.rankedServicesChart.innerHTML = `<div class="empty-state">Ranked service chart unavailable.</div>`;
    elements.departmentSummary.innerHTML = `<div class="empty-state">Department summary unavailable.</div>`;
    return;
  }

  renderRankedServicesChart(brief.ranked_service_table);
  renderDepartmentSummary(brief.department_summary);
}


function renderExecutiveStrategy() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.recommendationsList.innerHTML = `<div class="empty-state">Recommendations unavailable.</div>`;
    elements.methodologyList.innerHTML = `<div class="empty-state">Methodology unavailable.</div>`;
    return;
  }

  elements.recommendationsList.innerHTML = (brief.recommendations || [])
    .map(
      (item) => `
        <article class="strategy-card">
          <div class="alert-head">
            <div>
              <h4 class="alert-title">${escapeHtml(item.action_title)}</h4>
              <div class="alert-meta">
                <span>${escapeHtml(item.service_area)}</span>
                <span>${escapeHtml(item.owner)}</span>
              </div>
            </div>
            <span class="priority-pill ${slugify(item.priority)}">${escapeHtml(item.priority)}</span>
          </div>
          <p class="strategy-copy"><strong>Why:</strong> ${escapeHtml(item.evidence)}</p>
          <p class="strategy-copy"><strong>Action:</strong> ${escapeHtml(item.recommendation)}</p>
          <p class="strategy-copy"><strong>Next step:</strong> ${escapeHtml(item.next_step)}</p>
        </article>
      `
    )
    .join("");

  elements.methodologyList.innerHTML = (brief.methodology || [])
    .map(
      (item) => `
        <article class="method-card">
          <h4 class="alert-title">${escapeHtml(item.title)}</h4>
          <p class="strategy-copy">${escapeHtml(item.description)}</p>
        </article>
      `
    )
    .join("");
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
            <span>${escapeHtml(metric.department || metric.service_area)} · ${escapeHtml(metric.owner_department)} · ${escapeHtml(metric.consulting_bucket || "Unclassified")} · ${escapeHtml(metric.perf_band || "Unknown")}</span>
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
  elements.drawerDefinition.textContent = `${detail.definition} ${detail.department ? `Grouped in ${detail.department}.` : ""}`;

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
    {
      label: "Recent trend",
      value: formatSigned(detail.recent_trend),
    },
    {
      label: "Portfolio score",
      value: formatScore(detail.composite_score),
    },
    {
      label: "Perf band",
      value: detail.perf_band || "—",
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

  elements.drawerReasons.innerHTML = [
    detail.consulting_bucket ? renderConsultingBucketPill(detail.consulting_bucket) : "",
    detail.perf_band ? renderPerformanceBandPill(detail.perf_band) : "",
    ...(detail.alert_reasons || []).map((reason) => `<span class="reason-pill">${escapeHtml(reason)}</span>`),
  ]
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
  elements.heroHeadline.textContent = "Dashboard load failed.";
  elements.heroSupport.textContent = error.message;
  elements.topCardGrid.innerHTML = `<div class="empty-state">Unable to render top cards.</div>`;
}


function renderRankedServiceCards(items, mode, options = {}) {
  if (!items?.length) {
    return `<div class="empty-state">No ranked services available.</div>`;
  }

  const {
    scoreLabel = "Current score",
    trendLabel = "Recent trend",
    scoreField = "current_score",
    trendField = "recent_trend",
    badgeField = "classification",
  } = options;

  return items
    .map(
      (item, index) => `
        <article class="ranking-card ${mode} is-clickable" data-open-metric="${escapeHtml(item.metric_name)}">
          <div class="alert-head">
            <div>
              <div class="rank-badge">${item.rank || index + 1}</div>
              <h4 class="alert-title">${escapeHtml(item.display_name)}</h4>
              <div class="alert-meta">
                <span>${escapeHtml(item.department || item.service_area)}</span>
                <span>${escapeHtml(item.owner_department)}</span>
                <span>${escapeHtml(titleCase(item.selected_period || "unknown"))}</span>
              </div>
            </div>
            ${renderContextPill(item[badgeField], badgeField)}
          </div>
          <div class="kpi-strip">
            <div class="kpi-tile">
              <span class="kpi-label">${escapeHtml(scoreLabel)}</span>
              <strong class="kpi-value">${formatScore(item[scoreField])}</strong>
            </div>
            <div class="kpi-tile">
              <span class="kpi-label">${escapeHtml(trendLabel)}</span>
              <strong class="kpi-value">${formatSigned(item[trendField])}</strong>
            </div>
          </div>
          <p class="strategy-copy">${escapeHtml(item.evidence)}</p>
        </article>
      `
    )
    .join("");
}


function renderRankedServicesChart(items) {
  if (!items?.length) {
    elements.rankedServicesChart.innerHTML = `<div class="empty-state">No ranked service data available.</div>`;
    return;
  }

  const maxScore = Math.max(...items.map((item) => Number(item.composite_score || 0)), 1);
  elements.rankedServicesChart.innerHTML = `
    <div class="ranked-bars">
      ${items
        .map((item) => {
          const width = (Number(item.composite_score || 0) / maxScore) * 100;
          return `
            <article class="ranked-bar-row is-clickable" data-open-metric="${escapeHtml(item.metric_name)}">
              <div class="ranked-bar-meta">
                <div class="ranked-bar-title">
                  <span class="rank-badge small">${item.rank}</span>
                  <strong>${escapeHtml(item.display_name)}</strong>
                </div>
                <div class="alert-meta">
                  <span>${escapeHtml(item.department || item.service_area)}</span>
                  <span>${escapeHtml(item.trend_label || "Unknown")}</span>
                  <span>${escapeHtml(item.perf_band || "Unknown")}</span>
                </div>
              </div>
              <div class="ranked-bar-track">
                <span class="ranked-bar-fill ${slugify(item.perf_band || "unknown")}" style="--target-width:${width}%"></span>
              </div>
              <div class="ranked-bar-stats">
                <span>Score ${formatScore(item.composite_score)}</span>
                <span>Gap ${formatSigned(item.gap_to_target)}</span>
                <span>Momentum ${formatSigned(item.trend_delta_wq)}</span>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}


function renderDepartmentSummary(items) {
  if (!items?.length) {
    elements.departmentSummary.innerHTML = `<div class="empty-state">No department summary available.</div>`;
    return;
  }

  elements.departmentSummary.innerHTML = `
    <div class="department-stack">
      ${items
        .map((item) => `
          <article class="department-card">
            <div class="alert-head">
              <div>
                <h4 class="alert-title">${escapeHtml(item.department)}</h4>
                <div class="alert-meta">
                  <span>${item.metric_count} metrics</span>
                  <span>${item.at_or_above_target_count} at or above target</span>
                  <span>${item.priority_intervention_count} priority interventions</span>
                </div>
              </div>
              <strong class="department-score">${formatScore(item.composite_score_average)}</strong>
            </div>
            <div class="animated-bar">
              <span class="leading" style="--target-width:${Math.max(0, (Number(item.at_or_above_target_count || 0) / Math.max(item.metric_count || 1, 1)) * 100)}%"></span>
            </div>
            <p class="strategy-copy">${item.below_target_count} services in this grouping remain below the target threshold.</p>
          </article>
        `)
        .join("")}
    </div>
  `;
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
      <path class="chart-line" pathLength="100" d="${path}" fill="none" stroke="${lineColor}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
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
      <path class="chart-line" pathLength="100" d="${path}" fill="none" stroke="${stroke}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
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


function renderConsultingBucketPill(bucket) {
  if (!bucket) {
    return "";
  }
  return `<span class="bucket-pill ${slugify(bucket)}">${escapeHtml(bucket)}</span>`;
}


function renderPerformanceBandPill(band) {
  if (!band) {
    return "";
  }
  return `<span class="band-pill ${slugify(band)}">${escapeHtml(band)}</span>`;
}


function renderContextPill(value, kind) {
  if (!value) {
    return "";
  }
  if (kind === "perf_band") {
    return renderPerformanceBandPill(value);
  }
  return renderConsultingBucketPill(value);
}


function statusToneClass(status) {
  switch (status) {
    case "healthy":
      return "healthy";
    case "concerning":
      return "concerning";
    default:
      return "mixed";
  }
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


function performanceBandColor(band) {
  switch (band) {
    case "CRITICAL":
      return "#CC0000";
    case "AT RISK":
      return "#E8A020";
    case "NEAR MISS":
      return "#F0D060";
    case "ON TARGET":
      return "#8BC34A";
    case "EXCEEDING":
      return "#217346";
    default:
      return "rgba(13,83,14,0.18)";
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


function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return `${(Number(value) * 100).toFixed(0)}%`;
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
