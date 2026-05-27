const API_BASE = "/api/v1";
const PERIODS = ["day", "week", "month", "quarter"];
let resizeRerenderTimer = null;

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
  healthChip: document.getElementById("healthChip"),
  asOfChip: document.getElementById("asOfChip"),
  mastheadSubtitle: document.getElementById("mastheadSubtitle"),
  headlineStatus: document.getElementById("headlineStatus"),
  heroHeadline: document.getElementById("heroHeadline"),
  heroSupport: document.getElementById("heroSupport"),
  heroGuide: document.getElementById("heroGuide"),
  heroMeta: document.getElementById("heroMeta"),
  heroSummary: document.getElementById("heroSummary"),
  criticalAlerts: document.getElementById("criticalAlerts"),
  recommendationsList: document.getElementById("recommendationsList"),
  worstServicesList: document.getElementById("worstServicesList"),
  bestServicesList: document.getElementById("bestServicesList"),
  serviceAreaGrid: document.getElementById("serviceAreaGrid"),
  departmentSummary: document.getElementById("departmentSummary"),
  portfolioHealthPanel: document.getElementById("portfolioHealthPanel"),
  portfolioMix: document.getElementById("portfolioMix"),
  performanceBandsChart: document.getElementById("performanceBandsChart"),
  trendDistributionChart: document.getElementById("trendDistributionChart"),
  topCardGrid: document.getElementById("topCardGrid"),
  cityPeriodToggle: document.getElementById("cityPeriodToggle"),
  cityHistoryChart: document.getElementById("cityHistoryChart"),
  cityHistoryInsight: document.getElementById("cityHistoryInsight"),
  freshnessSummary: document.getElementById("freshnessSummary"),
  compositeLeadersList: document.getElementById("compositeLeadersList"),
  compositeLaggardsList: document.getElementById("compositeLaggardsList"),
  rankedServicesChart: document.getElementById("rankedServicesChart"),
  dataScopeSummary: document.getElementById("dataScopeSummary"),
  methodologyList: document.getElementById("methodologyList"),
  severityFilters: document.getElementById("severityFilters"),
  serviceAreaFilters: document.getElementById("serviceAreaFilters"),
  metricList: document.getElementById("metricList"),
  metricSearchInput: document.getElementById("metricSearchInput"),
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

  window.addEventListener("resize", () => {
    if (!state.overview) {
      return;
    }
    window.clearTimeout(resizeRerenderTimer);
    resizeRerenderTimer = window.setTimeout(() => {
      renderTopCards();
      renderCityHistory();
      if (state.drawer.detail) {
        renderDrawer();
      }
    }, 140);
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
      // ignore parse failures
    }
    throw new Error(detail);
  }

  return response.json();
}

function renderDashboard() {
  renderHero();
  renderUrgentAlerts();
  renderActionAgenda();
  renderPressureMap();
  renderPortfolioEvidence();
  renderCityMovement();
  renderBenchmarks();
  renderRanking();
  renderEvidencePack();
  renderFilterControls();
  renderMetricList();
}

function renderHero() {
  const brief = state.executiveBrief;
  const overview = state.overview;
  const status = brief?.headline_status || "mixed";
  const scope = brief?.data_scope;

  elements.healthChip.textContent = `Portfolio ${titleCase(status)}`;
  elements.healthChip.className = `status-chip ${statusToneClass(status)}`;
  elements.asOfChip.textContent = `As of: ${formatDate(overview?.as_of_date)}`;
  elements.headlineStatus.textContent = titleCase(status);
  elements.headlineStatus.className = `status-banner ${statusToneClass(status)}`;
  elements.heroHeadline.textContent = brief?.headline_text || "Preparing the state-of-city-services briefing.";
  elements.heroSupport.textContent =
    brief?.supporting_text || overview?.note || "Citywide context is not available yet.";

  elements.mastheadSubtitle.textContent = brief
    ? `${scope.services_ranked} ranked services across ${scope.snapshot_dates} recent Full Metric List snapshots.`
    : "Loading citywide service diagnostics.";

  elements.heroGuide.innerHTML = (brief?.score_guide || [])
    .map((item) => `<div class="guide-pill">${escapeHtml(item)}</div>`)
    .join("");

  elements.heroMeta.innerHTML = renderContextCards(scope, brief?.portfolio_health);

  elements.heroSummary.innerHTML = (brief?.kpi_cards || [])
    .map((item) => {
      const numeric = String(item.value).replace(/[^0-9.-]/g, "");
      const animateAttr = /^-?\d+(\.\d+)?$/.test(numeric) ? ` data-animate-number="${escapeHtml(numeric)}"` : "";
      return `
        <article class="summary-card">
          <span class="summary-label">${escapeHtml(item.label)}</span>
          <strong${animateAttr}>${escapeHtml(item.value)}</strong>
          <p class="summary-foot">${escapeHtml(item.detail)}</p>
        </article>
      `;
    })
    .join("");

  animateNumericElements(elements.heroSummary.querySelectorAll("[data-animate-number]"));
}

function renderContextCards(scope, health) {
  if (!scope) {
    return `<div class="empty-state">Scope metadata is unavailable.</div>`;
  }

  const cards = [
    {
      label: "Source",
      value: scope.source_focus,
      foot: "Primary analytical dataset",
    },
    {
      label: "Window",
      value: `${formatDate(scope.analysis_start_date, { month: "short", day: "numeric" })} to ${formatDate(scope.analysis_end_date, { month: "short", day: "numeric" })}`,
      foot: `${scope.snapshot_dates} snapshot dates`,
    },
    {
      label: "Ranked",
      value: `${scope.services_ranked}/${scope.services_in_scope}`,
      foot: "Services with current scores",
    },
    {
      label: "Health Score",
      value: health ? `${Math.round(health.score)}` : "—",
      foot: health ? `${titleCase(health.verdict)} on the 0-100 portfolio scale` : "Portfolio score unavailable",
    },
  ];

  return cards
    .map(
      (item) => `
        <article class="context-card">
          <span class="mini-label">${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.value)}</strong>
          <p class="summary-foot">${escapeHtml(item.foot)}</p>
        </article>
      `
    )
    .join("");
}

function renderUrgentAlerts() {
  const alerts = state.overview?.critical_alerts || [];
  if (!alerts.length) {
    elements.criticalAlerts.innerHTML = `<div class="empty-state">No immediate exceptions are active right now.</div>`;
    return;
  }

  elements.criticalAlerts.innerHTML = alerts
    .map(
      (alert) => `
        <article class="alert-card ${escapeHtml(alert.severity)} is-clickable" data-open-metric="${escapeHtml(alert.metric_name)}">
          <div class="alert-head">
            <div>
              <h4 class="alert-title">${escapeHtml(alert.display_name)}</h4>
              <div class="alert-meta">
                <span>${escapeHtml(alert.service_area)}</span>
                <span>${escapeHtml(titleCase(alert.selected_period || "unknown"))}</span>
                <span>${formatDate(alert.as_of_date, { month: "short", day: "numeric" })}</span>
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
          <div class="signal-summary">
            ${(alert.alert_reasons || []).slice(0, 2).map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}
          </div>
        </article>
      `
    )
    .join("");
}

function renderActionAgenda() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.recommendationsList.innerHTML = `<div class="empty-state">Recommendations are unavailable.</div>`;
    elements.worstServicesList.innerHTML = `<div class="empty-state">Risk ranking is unavailable.</div>`;
    elements.bestServicesList.innerHTML = `<div class="empty-state">Strength ranking is unavailable.</div>`;
    return;
  }

  elements.recommendationsList.innerHTML = renderActionTiles(brief.recommendations, brief.worst_services);
  elements.worstServicesList.innerHTML = renderRankingBars(brief.worst_services, "worst");
  elements.bestServicesList.innerHTML = renderRankingBars(brief.best_services, "best");
}

function renderPressureMap() {
  renderServiceAreas();
  renderDepartmentSummary(state.executiveBrief?.department_summary || []);
}

function renderPortfolioEvidence() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.portfolioHealthPanel.innerHTML = `<div class="empty-state">Portfolio evidence is unavailable.</div>`;
    elements.portfolioMix.innerHTML = `<div class="empty-state">Portfolio mix is unavailable.</div>`;
    elements.performanceBandsChart.innerHTML = "";
    elements.trendDistributionChart.innerHTML = "";
    elements.topCardGrid.innerHTML = `<div class="empty-state">Current CityScore cards are unavailable.</div>`;
    return;
  }

  renderPortfolioHealthPanel(brief.portfolio_health);
  renderPortfolioMix(brief.portfolio_mix);
  renderPerformanceBandsChart(brief.performance_bands);
  renderTrendDistributionChart(brief.trend_distribution);
  renderTopCards();
}

function renderCityMovement() {
  renderCityHistory();
  renderFreshness();
}

function renderBenchmarks() {
  const brief = state.executiveBrief;
  if (!brief) {
    elements.compositeLeadersList.innerHTML = `<div class="empty-state">Composite benchmarks are unavailable.</div>`;
    elements.compositeLaggardsList.innerHTML = `<div class="empty-state">Composite benchmarks are unavailable.</div>`;
    return;
  }

  elements.compositeLeadersList.innerHTML = renderRankingBars(brief.composite_leaders, "best", {
    scoreLabel: "Composite score",
    trendLabel: "Momentum",
    scoreField: "composite_score",
    trendField: "trend_delta_wq",
    badgeField: "perf_band",
  });
  elements.compositeLaggardsList.innerHTML = renderRankingBars(brief.composite_laggards, "worst", {
    scoreLabel: "Composite score",
    trendLabel: "Momentum",
    scoreField: "composite_score",
    trendField: "trend_delta_wq",
    badgeField: "perf_band",
  });
}

function renderRanking() {
  const items = state.executiveBrief?.ranked_service_table || [];
  if (!items.length) {
    elements.rankedServicesChart.innerHTML = `<div class="empty-state">Full service ranking is unavailable.</div>`;
    return;
  }

  const sorted = [...items].sort((a, b) => Number(b.composite_score || -Infinity) - Number(a.composite_score || -Infinity));
  const maxScore = Math.max(...sorted.map((item) => Number(item.composite_score || 0)), 1);

  elements.rankedServicesChart.innerHTML = `
    <div class="ranked-bars">
      ${sorted
        .map((item, index) => {
          const width = Math.max(4, (Number(item.composite_score || 0) / maxScore) * 100);
          return `
            <article class="ranked-bar-row is-clickable" data-open-metric="${escapeHtml(item.metric_name)}">
              <div class="ranked-bar-meta">
                <div class="ranked-bar-title">
                  <span class="rank-badge small">${index + 1}</span>
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
                <span>Composite ${formatScore(item.composite_score)}</span>
                <span>Current ${formatScore(item.current_score)}</span>
                <span>Momentum ${formatSigned(item.trend_delta_wq ?? item.recent_trend)}</span>
                <span>Gap ${formatSigned(item.gap_to_target)}</span>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderEvidencePack() {
  renderDataScope();
  renderMethodology();
}

function renderActionTiles(items, risks = []) {
  if (!items?.length) {
    return `<div class="empty-state">No leadership actions are available.</div>`;
  }

  return items
    .map((item, index) => {
      const matchedRisk = risks.find((risk) => item.action_title.toLowerCase().includes(risk.display_name.toLowerCase()));
      const signalWidth = matchedRisk
        ? Math.max(12, Math.min(100, Math.abs(Number(matchedRisk.gap_to_target || 0)) * 100))
        : 40 + index * 12;

      return `
        <article class="action-tile">
          <div class="alert-head">
            <div>
              <h4 class="alert-title">${escapeHtml(item.action_title)}</h4>
              <div class="alert-meta">
                <span>${escapeHtml(item.service_area)}</span>
                <span>${escapeHtml(item.owner)}</span>
              </div>
            </div>
            ${renderPriorityPill(item.priority)}
          </div>
          <div class="action-metrics">
            <div class="action-stat">
              <span class="kpi-label">Risk signal</span>
              <strong>${matchedRisk ? formatScore(matchedRisk.current_score) : "—"}</strong>
            </div>
            <div class="action-stat">
              <span class="kpi-label">Momentum</span>
              <strong>${matchedRisk ? formatSigned(matchedRisk.recent_trend ?? matchedRisk.trend_delta_wq) : "—"}</strong>
            </div>
            <div class="action-stat">
              <span class="kpi-label">Priority</span>
              <strong>${escapeHtml(item.priority)}</strong>
            </div>
          </div>
          <div class="action-track"><span style="--target-width:${signalWidth}%"></span></div>
          <p class="strategy-copy">${escapeHtml(truncateText(item.recommendation, 120))}</p>
        </article>
      `;
    })
    .join("");
}

function renderRankingBars(items, mode, options = {}) {
  if (!items?.length) {
    return `<div class="empty-state">No services are available for this view.</div>`;
  }

  const {
    scoreLabel = "Current score",
    trendLabel = "Recent trend",
    scoreField = "current_score",
    trendField = "recent_trend",
    badgeField = "classification",
  } = options;

  const maxScore = Math.max(...items.map((item) => Number(item[scoreField] || 0)), 1);
  const maxRisk = Math.max(...items.map((item) => Math.abs(Number(item.gap_to_target || 0))), 0.5);

  return items
    .map(
      (item, index) => `
        <article class="ranking-bar-card ${mode} is-clickable" data-open-metric="${escapeHtml(item.metric_name)}">
          <div class="ranking-bar-head">
            <div class="ranking-bar-title">
              <div class="rank-badge">${item.rank || index + 1}</div>
              <div>
                <h4 class="alert-title">${escapeHtml(item.display_name)}</h4>
                <div class="alert-meta">
                  <span>${escapeHtml(item.service_area)}</span>
                  <span>${escapeHtml(titleCase(item.selected_period || "unknown"))}</span>
                </div>
              </div>
            </div>
            ${renderContextPill(item[badgeField], badgeField)}
          </div>
          <div class="ranking-bar-track ${mode}">
            <span class="ranking-bar-fill ${mode}" style="--target-width:${
              mode === "best"
                ? Math.max(8, (Number(item[scoreField] || 0) / maxScore) * 100)
                : Math.max(8, (Math.abs(Number(item.gap_to_target || 0)) / maxRisk) * 100)
            }%"></span>
          </div>
          <div class="ranking-bar-stats">
            <span><strong>${escapeHtml(scoreLabel)}:</strong> ${formatScore(item[scoreField])}</span>
            <span><strong>${escapeHtml(trendLabel)}:</strong> ${formatSigned(item[trendField])}</span>
            <span><strong>Gap:</strong> ${formatSigned(item.gap_to_target)}</span>
          </div>
        </article>
      `
    )
    .join("");
}

function renderPortfolioHealthPanel(health) {
  if (!health) {
    elements.portfolioHealthPanel.innerHTML = `<div class="empty-state">Portfolio health is unavailable.</div>`;
    return;
  }

  const scorePercent = Math.max(0, Math.min(Number(health.score || 0), 100));
  elements.portfolioHealthPanel.innerHTML = `
    <div class="health-score-layout">
      <div class="health-gauge-shell">
        <div class="health-gauge" style="--score:${scorePercent}; --tone:${health.verdict_color};">
          <div class="health-gauge-core">
            <strong>${Math.round(scorePercent)}</strong>
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
            <span class="summary-label">Central tendency</span>
            <strong class="health-component-score">${formatScore(health.median_score)}</strong>
          </div>
          <p class="strategy-copy">Median service score, with mean at ${formatScore(health.mean_score)} across ${health.total_services} rankable services.</p>
        </article>
      </div>
    </div>
  `;
}

function renderPortfolioMix(mix) {
  const entries = Object.entries(mix || {});
  if (!entries.length) {
    elements.portfolioMix.innerHTML = `<div class="empty-state">Portfolio mix is unavailable.</div>`;
    return;
  }

  const total = entries.reduce((sum, [, count]) => sum + Number(count || 0), 0) || 1;
  elements.portfolioMix.innerHTML = `
    <div class="portfolio-mix-list">
      ${entries
        .map(([bucket, count]) => {
          const share = (Number(count || 0) / total) * 100;
          return `
            <article class="mix-card">
              <div class="mix-head">
                <div>
                  <strong>${escapeHtml(bucket)}</strong>
                  <div class="alert-meta">
                    <span>${formatPercent(share / 100)} of services</span>
                    <span>${count} services</span>
                  </div>
                </div>
                ${renderConsultingBucketPill(bucket)}
              </div>
              <div class="mix-bar"><span class="${slugify(bucket)}" style="--target-width:${share}%"></span></div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPerformanceBandsChart(bands) {
  if (!bands?.length) {
    elements.performanceBandsChart.innerHTML = `<div class="empty-state">Performance bands are unavailable.</div>`;
    return;
  }

  const total = bands.reduce((sum, item) => sum + Number(item.count || 0), 0) || 1;
  let start = 0;
  const slices = bands
    .filter((item) => item.count > 0)
    .map((item) => {
      const ratio = Number(item.count) / total;
      const end = start + ratio;
      const slice = `${performanceBandColor(item.band)} ${start * 100}% ${end * 100}%`;
      start = end;
      return slice;
    })
    .join(", ");

  elements.performanceBandsChart.innerHTML = `
    <div class="distribution-layout">
      <div class="distribution-donut" style="--distribution:${slices || "rgba(13,83,14,0.12) 0% 100%"};">
        <div class="distribution-donut-core">
          <strong>${total}</strong>
          <span>services</span>
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
    elements.trendDistributionChart.innerHTML = `<div class="empty-state">Trend distribution is unavailable.</div>`;
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

function renderTopCards() {
  const cards = state.overview?.top_cards || [];
  if (!cards.length) {
    elements.topCardGrid.innerHTML = `<div class="empty-state">Current CityScore cards are unavailable.</div>`;
    return;
  }

  const compact = isCompactViewport();
  const sparklineWidth = compact ? 300 : 320;
  const sparklineHeight = compact ? 112 : 84;

  elements.topCardGrid.innerHTML = cards
    .map((card) => {
      const points = getCityHistoryForPeriod(card.period_type).slice(-18);
      const deltaClass = Number(card.change || 0) >= 0 ? "up" : "down";
      return `
        <article class="top-card">
          <div class="top-card-head">
            <div>
              <span class="period-name">${escapeHtml(titleCase(card.period_type))}</span>
            </div>
            ${renderSeverityPill(card.status)}
          </div>
          <div class="score-line">
            <strong class="score-value" data-animate-number="${formatScore(card.score)}">${formatScore(card.score)}</strong>
            <span class="delta-chip ${deltaClass}">${formatSigned(card.change)}</span>
          </div>
          <div class="sparkline-shell">
            ${renderSparkline(points.map((point) => point.score), {
              width: sparklineWidth,
              height: sparklineHeight,
              stroke: severityColor(card.status),
            })}
          </div>
          <div class="sparkline-caption">
            <span>Previous ${formatScore(card.previous_score)}</span>
            <span>${points.length} points</span>
          </div>
        </article>
      `;
    })
    .join("");

  animateNumericElements(elements.topCardGrid.querySelectorAll("[data-animate-number]"));
}

function renderCityHistory() {
  elements.cityPeriodToggle.innerHTML = PERIODS.map(
    (period) => `
      <button type="button" class="chip-button ${state.cityFocusPeriod === period ? "is-active" : ""}" data-city-period="${period}">
        ${escapeHtml(titleCase(period))}
      </button>
    `
  ).join("");

  const points = getCityHistoryForPeriod(state.cityFocusPeriod);
  if (!points.length) {
    elements.cityHistoryChart.innerHTML = `<div class="chart-placeholder">City trajectory is unavailable for this period.</div>`;
    elements.cityHistoryInsight.innerHTML = "";
    return;
  }

  const latestPoint = points[points.length - 1];
  const previousPoint = points[points.length - 2];

  elements.cityHistoryChart.innerHTML = renderLargeChart({
    title: `${titleCase(state.cityFocusPeriod)} CityScore`,
    subtitle: `${points.length} observations in the current view`,
    values: points.map((point) => point.score),
    dates: points.map((point) => formatDate(point.as_of_date, { month: "short", day: "numeric" })),
    targetValue: 1,
    lineColor: "var(--forest-deep)",
  });

  elements.cityHistoryInsight.innerHTML = `
    <div class="insight-stat">
      <span class="kpi-label">Current score</span>
      <strong class="insight-value">${formatScore(latestPoint?.score)}</strong>
    </div>
    <div class="insight-stat">
      <span class="kpi-label">Change from previous</span>
      <strong class="insight-value">${formatSigned(latestPoint?.change)}</strong>
    </div>
    <div class="insight-stat">
      <span class="kpi-label">Previous reading</span>
      <strong class="insight-value">${formatScore(previousPoint?.score)}</strong>
    </div>
    <div class="insight-stat">
      <span class="kpi-label">Decision threshold</span>
      <strong class="insight-value">1.00</strong>
    </div>
  `;
}

function renderFreshness() {
  const freshness = state.freshness;
  if (!freshness) {
    elements.freshnessSummary.innerHTML = `<div class="empty-state">Reporting coverage is unavailable.</div>`;
    return;
  }

  elements.freshnessSummary.innerHTML = `
    <div class="kpi-strip">
      <div class="kpi-tile">
        <span class="kpi-label">Metrics total</span>
        <strong class="kpi-value">${freshness.metrics_total}</strong>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Selected scores ready</span>
        <strong class="kpi-value">${freshness.metrics_with_selected_score}</strong>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Missing day scores</span>
        <strong class="kpi-value">${freshness.metrics_missing_day_score}</strong>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Stale metrics</span>
        <strong class="kpi-value">${freshness.stale_metrics}</strong>
      </div>
    </div>
    <div class="guide-list guide-list-inline" style="margin-top:1rem;">
      ${freshness.coverage_by_service_area
        .map(
          (item) => `
            <div class="guide-pill">
              ${escapeHtml(item.service_area)} · ${item.metrics_with_selected_score}/${item.total_metrics} with current selected scores
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderServiceAreas() {
  if (!state.serviceAreas.length) {
    elements.serviceAreaGrid.innerHTML = `<div class="empty-state">Service-area coverage is unavailable.</div>`;
    return;
  }

  elements.serviceAreaGrid.innerHTML = state.serviceAreas
    .map((serviceArea) => {
      const total = serviceArea.metric_count || 1;
      const score = Number(serviceArea.selected_score_average || 0);
      const tone = serviceArea.red_count > 0 ? "risk" : score >= 1 ? "steady" : "watch";
      return `
        <article class="service-card ${tone} is-clickable" data-filter-service-area="${escapeHtml(serviceArea.service_area)}">
          <div class="service-card-head">
            <div>
              <h4 class="alert-title">${escapeHtml(serviceArea.service_area)}</h4>
              <div class="mini-meta">
                <span>${serviceArea.metric_count} metrics</span>
                <span>${serviceArea.red_count + serviceArea.amber_count} active concerns</span>
              </div>
            </div>
            <div class="service-score">${formatScore(serviceArea.selected_score_average)}</div>
          </div>
          <div class="stacked-bar">
            <span class="red" style="width:${(serviceArea.red_count / total) * 100}%"></span>
            <span class="amber" style="width:${(serviceArea.amber_count / total) * 100}%"></span>
            <span class="blue" style="width:${(serviceArea.blue_count / total) * 100}%"></span>
            <span class="green" style="width:${(serviceArea.green_count / total) * 100}%"></span>
          </div>
          <div class="mini-meta">
            <span>Red ${serviceArea.red_count}</span>
            <span>Amber ${serviceArea.amber_count}</span>
            <span>Blue ${serviceArea.blue_count}</span>
            <span>Green ${serviceArea.green_count}</span>
          </div>
          <div class="micro-bars">
            <span class="micro-bar red" style="--target-width:${(serviceArea.red_count / total) * 100}%"></span>
            <span class="micro-bar amber" style="--target-width:${(serviceArea.amber_count / total) * 100}%"></span>
            <span class="micro-bar green" style="--target-width:${(serviceArea.green_count / total) * 100}%"></span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderDepartmentSummary(items) {
  if (!items?.length) {
    elements.departmentSummary.innerHTML = `<div class="empty-state">Department view is unavailable.</div>`;
    return;
  }

  const sorted = [...items].sort(
    (a, b) => Number(b.priority_intervention_count || 0) - Number(a.priority_intervention_count || 0)
  );

  elements.departmentSummary.innerHTML = sorted
    .map(
      (item) => `
        <article class="department-card">
          <div class="alert-head">
            <div>
              <h4 class="alert-title">${escapeHtml(item.department)}</h4>
              <div class="alert-meta">
                <span>${item.metric_count} metrics</span>
                <span>${item.priority_intervention_count} priority interventions</span>
                <span>${item.below_target_count} below target</span>
              </div>
            </div>
            <strong class="department-score">${formatScore(item.composite_score_average)}</strong>
          </div>
          <div class="animated-bar">
            <span class="${item.priority_intervention_count > 0 ? "priority-intervention" : "leading"}" style="--target-width:${Math.max(4, (Number(item.priority_intervention_count || 0) / Math.max(item.metric_count || 1, 1)) * 100)}%"></span>
          </div>
          <div class="department-metrics">
            <span>${item.at_or_above_target_count} above target</span>
            <span>${item.below_target_count} below target</span>
          </div>
        </article>
      `
    )
    .join("");
}

function renderDataScope() {
  const scope = state.executiveBrief?.data_scope;
  if (!scope) {
    elements.dataScopeSummary.innerHTML = `<div class="empty-state">Scope and timing metadata are unavailable.</div>`;
    return;
  }

  const stats = [
    ["Source focus", scope.source_focus, "Primary analytical dataset"],
    [
      "Analysis period",
      `${formatDate(scope.analysis_start_date, { month: "short", day: "numeric" })} to ${formatDate(scope.analysis_end_date, { month: "short", day: "numeric" })}`,
      `${scope.snapshot_dates} recent snapshots`,
    ],
    ["Services ranked", `${scope.services_ranked}/${scope.services_in_scope}`, "Current scores suitable for ranking"],
    ["Download date", formatDate(scope.download_date), "Documented because CityScore updates over time"],
  ];

  elements.dataScopeSummary.innerHTML = `
    <div class="scope-grid">
      ${stats
        .map(
          ([label, value, foot]) => `
            <article class="scope-card">
              <span class="scope-label">${escapeHtml(label)}</span>
              <strong>${escapeHtml(value)}</strong>
              <p class="summary-foot">${escapeHtml(foot)}</p>
            </article>
          `
        )
        .join("")}
    </div>
    <p class="scope-note strategy-copy">${escapeHtml(scope.reading_note)}</p>
  `;
}

function renderMethodology() {
  const items = state.executiveBrief?.methodology || [];
  if (!items.length) {
    elements.methodologyList.innerHTML = `<div class="empty-state">Methodology is unavailable.</div>`;
    return;
  }

  elements.methodologyList.innerHTML = items
    .slice(0, 4)
    .map(
      (item, index) => `
        <article class="method-card">
          <div class="method-index">${index + 1}</div>
          <h4 class="alert-title">${escapeHtml(item.title)}</h4>
          <p class="strategy-copy">${escapeHtml(truncateText(item.description, 120))}</p>
        </article>
      `
    )
    .join("");
}

function renderFilterControls() {
  const severityOptions = ["all", "red", "amber", "blue", "green"];
  elements.severityFilters.innerHTML = severityOptions
    .map(
      (severity) => `
        <button type="button" class="chip-button ${state.filters.severity === severity ? "is-active" : ""}" data-filter-severity="${severity}">
          ${escapeHtml(titleCase(severity))}
        </button>
      `
    )
    .join("");

  const serviceOptions = ["all", ...state.serviceAreas.map((item) => item.service_area)];
  elements.serviceAreaFilters.innerHTML = serviceOptions
    .map(
      (serviceArea) => `
        <button type="button" class="chip-button ${state.filters.serviceArea === serviceArea ? "is-active" : ""}" data-filter-service-area="${escapeHtml(serviceArea)}">
          ${escapeHtml(serviceArea === "all" ? "All areas" : serviceArea)}
        </button>
      `
    )
    .join("");
}

function renderMetricList() {
  const metrics = state.metrics.filter((metric) => {
    const matchesSeverity = state.filters.severity === "all" || metric.severity === state.filters.severity;
    const matchesServiceArea =
      state.filters.serviceArea === "all" || metric.service_area === state.filters.serviceArea;
    const query = state.filters.query;
    const matchesQuery =
      !query ||
      metric.metric_name.toLowerCase().includes(query) ||
      metric.display_name.toLowerCase().includes(query) ||
      metric.service_area.toLowerCase().includes(query) ||
      (metric.department || "").toLowerCase().includes(query);
    return matchesSeverity && matchesServiceArea && matchesQuery;
  });

  if (!metrics.length) {
    elements.metricList.innerHTML = `<div class="empty-state">No services match the current filters.</div>`;
    return;
  }

  elements.metricList.innerHTML = metrics
    .map(
      (metric) => `
        <article class="metric-row is-clickable" data-open-metric="${escapeHtml(metric.metric_name)}">
          <div class="metric-name-cell">
            <strong>${escapeHtml(metric.display_name)}</strong>
            <span>${escapeHtml(metric.department || metric.service_area)} · ${escapeHtml(metric.owner_department)} · ${escapeHtml(metric.consulting_bucket || "Unclassified")}</span>
          </div>
          <div class="metric-field">
            <span class="field-label">Period</span>
            <span class="metric-period">${escapeHtml(titleCase(metric.selected_period || "n/a"))}</span>
          </div>
          <div class="metric-field">
            <span class="field-label">Current</span>
            <span class="metric-value">${formatScore(metric.current_score)}</span>
          </div>
          <div class="metric-field">
            <span class="field-label">Change</span>
            <span class="metric-change">${formatSigned(metric.change_vs_previous)}</span>
          </div>
          <div class="metric-field metric-field-severity">
            <span class="field-label">Severity</span>
            <span>${renderSeverityPill(metric.severity)}</span>
          </div>
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
  elements.drawerDefinition.textContent = "Pulling historical movement and the latest context.";
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

  const stats = [
    ["Current score", formatScore(detail.current_score)],
    ["Change", formatSigned(detail.change_vs_previous)],
    ["Rolling 14", formatScore(detail.rolling_mean_14)],
    ["Target", formatScore(detail.target)],
    ["Recent trend", formatSigned(detail.recent_trend)],
    ["Composite", formatScore(detail.composite_score)],
  ];

  elements.drawerStatStrip.innerHTML = stats
    .map(
      ([label, value]) => `
        <article class="drawer-stat-tile">
          <span class="kpi-label">${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </article>
      `
    )
    .join("");

  elements.drawerPeriodToggle.innerHTML = PERIODS.map(
    (period) => `
      <button type="button" class="chip-button ${state.drawer.period === period ? "is-active" : ""}" data-drawer-period="${period}">
        ${escapeHtml(titleCase(period))}
      </button>
    `
  ).join("");

  elements.drawerChartShell.innerHTML = renderLargeChart({
    title: `${detail.display_name} · ${titleCase(state.drawer.period)}`,
    subtitle: `${state.drawer.history.length} observations in the selected window`,
    values: state.drawer.history.map((point) => point.score),
    dates: state.drawer.history.map((point) => formatDate(point.as_of_date, { month: "short", day: "numeric" })),
    targetValue: detail.target ?? 1,
    lineColor: severityColor(detail.severity),
  });

  elements.periodSnapshotGrid.innerHTML = (detail.period_snapshots || [])
    .map(
      (snapshot) => `
        <article class="period-card">
          <span class="kpi-label">${escapeHtml(titleCase(snapshot.period_type))}</span>
          <div class="period-card-value">${formatScore(snapshot.score)}</div>
          <div class="mini-meta">
            <span>Primary ${formatScore(snapshot.primary_value)}</span>
            <span>Secondary ${formatScore(snapshot.secondary_value)}</span>
          </div>
        </article>
      `
    )
    .join("");

  const reasons = [];
  if (detail.consulting_bucket) {
    reasons.push(renderConsultingBucketPill(detail.consulting_bucket));
  }
  if (detail.perf_band) {
    reasons.push(renderPerformanceBandPill(detail.perf_band));
  }
  reasons.push(...(detail.alert_reasons || []).map((reason) => `<div class="guide-pill">${escapeHtml(reason)}</div>`));
  elements.drawerReasons.innerHTML = reasons.join("");
}

function closeDrawer() {
  document.body.classList.remove("drawer-open");
  elements.drawerBackdrop.classList.remove("is-open");
  elements.metricDrawer.classList.remove("is-open");
  elements.metricDrawer.setAttribute("aria-hidden", "true");
}

function handleDocumentClick(event) {
  if (event.target.closest('[data-action="refresh"]')) {
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

  if (event.target.closest('[data-action="close-drawer"]') || event.target === elements.drawerBackdrop) {
    closeDrawer();
  }
}

function toggleLoading(isLoading) {
  elements.loadingScreen.classList.toggle("is-hidden", !isLoading);
}

function renderLoadError(error) {
  elements.healthChip.textContent = "Data unavailable";
  elements.healthChip.className = "status-chip concerning";
  elements.asOfChip.textContent = "As of: --";
  elements.headlineStatus.textContent = "Unavailable";
  elements.headlineStatus.className = "status-banner concerning";
  elements.heroHeadline.textContent = "The mayor's briefing could not be loaded.";
  elements.heroSupport.textContent = error.message;
  elements.heroGuide.innerHTML = "";
  elements.heroMeta.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  elements.heroSummary.innerHTML = `<div class="empty-state">Executive KPI cards are unavailable.</div>`;
  elements.criticalAlerts.innerHTML = `<div class="empty-state">Unable to render current exceptions.</div>`;
}

function getCityHistoryForPeriod(period) {
  return state.cityHistory.filter((item) => item.period_type === period);
}

function renderLargeChart({ title, subtitle, values, dates, targetValue, lineColor }) {
  const validValues = values.filter((value) => typeof value === "number");
  if (!validValues.length) {
    return `<div class="chart-placeholder">Not enough data to draw this trend.</div>`;
  }

  const compact = isCompactViewport();
  const width = compact ? 700 : 760;
  const height = compact ? 360 : 300;
  const padding = compact ? 22 : 18;
  const lineStrokeWidth = compact ? 3.5 : 4;
  const markerRadius = compact ? 5 : 6;
  const markerStrokeWidth = compact ? 2.5 : 3;
  const path = buildLinePath(values, width, height, padding);
  const areaPath = buildAreaPath(values, width, height, padding);
  const minValue = Math.min(...validValues, targetValue ?? Math.min(...validValues));
  const maxValue = Math.max(...validValues, targetValue ?? Math.max(...validValues));
  const targetY =
    typeof targetValue === "number"
      ? projectY(targetValue, minValue, maxValue, height, padding)
      : null;
  const latestValue = values[values.length - 1];
  const chartId = slugify(`${title}-${subtitle}`);

  return `
    <div class="chart-title">
      <h4>${escapeHtml(title)}</h4>
      <span>${escapeHtml(subtitle)}</span>
    </div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)} chart">
      <defs>
        <linearGradient id="areaGradient-${chartId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${lineColor}" stop-opacity="0.24"></stop>
          <stop offset="100%" stop-color="${lineColor}" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="rgba(255,255,255,0.18)"></rect>
      ${targetY !== null ? `<line x1="${padding}" y1="${targetY}" x2="${width - padding}" y2="${targetY}" stroke="rgba(154,106,25,0.55)" stroke-dasharray="6 6" stroke-width="2"></line>` : ""}
      <path d="${areaPath}" fill="url(#areaGradient-${chartId})"></path>
      <path class="chart-line" pathLength="100" d="${path}" fill="none" stroke="${lineColor}" stroke-width="${lineStrokeWidth}" stroke-linecap="round" stroke-linejoin="round"></path>
      <circle cx="${projectX(values.length - 1, values.length, width, padding)}" cy="${projectY(latestValue, minValue, maxValue, height, padding)}" r="${markerRadius}" fill="${lineColor}" stroke="rgba(255,255,255,0.95)" stroke-width="${markerStrokeWidth}"></circle>
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

function isCompactViewport() {
  return window.matchMedia("(max-width: 900px)").matches;
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

function renderPriorityPill(priority) {
  return `<span class="priority-pill ${slugify(priority || "medium")}">${escapeHtml(priority || "Medium")}</span>`;
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
      return "#9a3630";
    case "amber":
      return "#9a6a19";
    case "blue":
      return "#44647f";
    default:
      return "#0d530e";
  }
}

function performanceBandColor(band) {
  switch (band) {
    case "CRITICAL":
      return "#b43027";
    case "AT RISK":
      return "#d88f1f";
    case "NEAR MISS":
      return "#f0d060";
    case "ON TARGET":
      return "#7ab84b";
    case "EXCEEDING":
      return "#236947";
    default:
      return "rgba(13,83,14,0.18)";
  }
}

function truncateText(value, maxLength) {
  const text = String(value || "");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1).trim()}…`;
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
  const rounded = Number(numeric.toFixed(2));
  if (rounded === 0 || Object.is(rounded, -0)) {
    return "0.00";
  }
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(2)}`;
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
