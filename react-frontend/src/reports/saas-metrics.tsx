import type {
  DashboardReportSpec,
  CardGridPosition,
  AnyDashboardReportCardSpec,
  DashboardTheme,
} from "@cereon/dashboard";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const getSaasMetricsReport = (
  theme: DashboardTheme
): DashboardReportSpec => {
  const id = "saas_metrics";
  const title = "SaaS Metrics Demo";

  // Futuristic bento-box layout: mix of small KPI tiles and larger charts
  const cards: AnyDashboardReportCardSpec<
    Record<string, any>,
    Record<string, any>
  >[] = [
    {
      id: "summary",
      kind: "markdown",
      title: "Dashboard Summary",
      panel: false,
      transparent: true,
      gridPosition: { x: 0, y: 0, w: 12, h: 1 } as CardGridPosition,
      settings: {
        defaultContent:
          "This dashboard presents a compact SaaS metrics demo showcasing key financial, product, and system-health indicators, including MRR, user activity, revenue trends, plan distributions, feature usage, churn cohorts, and real-time performance signals. It combines fast-updating KPIs with streaming line/area charts and multi-dimensional visualizations to illustrate how Cereon dashboards handle live data, complex compositions, and diverse metric types in a single unified report.",
        markdownTheme: "auto",
        enableTables: true,
      },
    },
    {
      id: "mrr_overview",
      kind: "number",
      title: "Monthly Recurring Revenue",
      gridPosition: { x: 0, y: 0, w: 3, h: 2 } as CardGridPosition,
      settings: {
        number: {
          large: true,
          showTrend: true,
          format: "currency",
          currency: "USD",
          decimals: 0,
          valueColor: "primary",
        },
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/mrr_overview`,
          method: "GET",
          params: {},
        },
      },
    },
    {
      id: "saas_user_growth",
      kind: "number",
      title: "Daily Active Users",
      gridPosition: { x: 3, y: 0, w: 3, h: 2 } as CardGridPosition,
      settings: {
        number: {
          showTrend: true,
          format: "number",
          decimals: 0,
          unit: "users",
          valueColor: "success",
        },
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/saas_user_growth`,
          method: "GET",
        },
      },
    },
    {
      id: "revenue_trend",
      kind: "recharts:line",
      title: "Revenue Trend",
      description: "MRR / New / Expansion over time",
      gridPosition: { x: 8, y: 4, w: 6, h: 8 } as CardGridPosition,
      settings: {
        chartConfig: {
          type: "line",
          curve: "monotone",
          series: [
            { dataKey: "mrr", name: "MRR", color: "#3b82f6" },
            { dataKey: "new", name: "New", color: "#10b981" },
            { dataKey: "expansion", name: "Expansion", color: "#f97316" },
          ],
          tooltip: { enabled: true },
          legend: { enabled: true },
        },
        
      },
      query: {
        variant: "streaming-http",
        payload: {
          url: `${API_BASE_URL}/cards/revenue_trend`,
          method: "GET",
          streamFormat: "ndjson",
          streamDelimiter: "\n",
          params: {},
        },
      },
    },
    {
      id: "revenue_area_trend",
      kind: "recharts:area",
      title: "Cumulative Revenue",
      description: "Cumulative revenue and rolling bands",
      gridPosition: { x: 0, y: 12, w: 6, h: 8 } as CardGridPosition,

      settings: {
        chartConfig: {
          type: "area",
          stacking: "none",
          curve: "natural",
          series: [
            {
              dataKey: "cumulative_mrr",
              name: "Cumulative MRR",
              color: "#3b82f6",
              gradient: { enabled: true },
            },
            {
              dataKey: "rolling_new",
              name: "Rolling New (7d)",
              color: "#10b981",
            },
          ],
          tooltip: { enabled: true },
          legend: { enabled: false },
        },
        
      },
      query: {
        variant: "streaming-http",
        payload: {
          url: `${API_BASE_URL}/cards/revenue_area_trend`,
          method: "GET",
          streamFormat: "ndjson",
          streamDelimiter: "\n",
          params: {},
        },
      },
    },
    {
      id: "plans_breakdown",
      kind: "recharts:bar",
      title: "Plans Breakdown",
      description: "Active users & seats per plan",
      gridPosition: { x: 8, y: 4, w: 6, h: 8 } as CardGridPosition,
      settings: {
        chartConfig: {
          type: "bar",
          grouping: "grouped",
          xAxis: { label: { value: "plan" } },
          series: [
            { dataKey: "active_users", name: "Active Users", color: "#06b6d4" },
            { dataKey: "seats", name: "Seats", color: "#ef4444" },
          ],
          tooltip: { enabled: true },
          legend: { enabled: true },
        },
        
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/plans_breakdown`,
          method: "GET",
          params: {},
        },
      },
    },
    {
      id: "revenue_share_pie",
      kind: "recharts:pie",
      title: "Revenue Share",
      description: "Revenue share by product/plan/channel",
      gridPosition: { x: 6, y: 12, w: 3, h: 8 } as CardGridPosition,
      settings: {
        chartConfig: {
          type: "pie",
          variant: "donut",
          nameKey: "name",
          valueKey: "value",
          innerRadius: "40%",
          outerRadius: "80%",
          colors: ["#3b82f6", "#10b981", "#f97316", "#a78bfa"],
          tooltip: { enabled: true },
          legend: { enabled: true },
        },
        
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/revenue_share_pie`,
          method: "GET",
          params: {},
        },
      },
    },
    {
      id: "health_radial",
      kind: "recharts:radial",
      title: "System Health",
      description: "Online / Degraded / Offline",
      gridPosition: { x: 9, y: 12, w: 3, h: 8 } as CardGridPosition,
      settings: {
        chartConfig: {
          type: "radial",
          variant: "bar",
          series: [
            { dataKey: "online", name: "Online", color: "#10b981" },
            { dataKey: "degraded", name: "Degraded", color: "#f97316" },
            { dataKey: "offline", name: "Offline", color: "#ef4444" },
            { dataKey: "maintenance", name: "Maintenance", color: "#60a5fa" },
            { dataKey: "unknown", name: "Unknown", color: "#94a3b8" },
          ],
          tooltip: { enabled: true },
          legend: { enabled: true },
          outerRadius: "100%",
          innerRadius: "40%",
        },
        
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/health_radial`,
          method: "GET",
          params: {},
        },
      },
    },
    {
      id: "feature_usage_radar",
      kind: "recharts:radar",
      title: "Feature Usage",
      description: "Multi-dimension usage profile",
      gridPosition: { x: 0, y: 18, w: 6, h: 6 } as CardGridPosition,
      settings: {
        chartConfig: {
          type: "radar",
          polarAngleAxis: { label: { value: "subject" } },
          series: [
            { dataKey: "core", name: "Core", color: "#3b82f6" },
            { dataKey: "advanced", name: "Advanced", color: "#f97316" },
          ],
          tooltip: { enabled: true },
          legend: { enabled: true },
        },
        
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/feature_usage_radar`,
          method: "GET",
          params: {},
        },
      },
    },
    {
      id: "churn_cohort",
      kind: "table",
      title: "Churn Cohort",
      description: "Cohort retention matrix",
      gridPosition: { x: 0, y: 16, w: 6, h: 8 } as CardGridPosition,
      settings: {
        table: { enablePagination: true },
        filters: {
          schema: [
            {
              name: "cohort_month",
              label: "Cohort Month",
              variant: "select",
              options: [
                { label: "All", value: "" },
                { label: "2025-01", value: "2025-01" },
                { label: "2025-02", value: "2025-02" },
                { label: "2025-03", value: "2025-03" },
              ],
            },
          ],
        },
      },
      query: {
        variant: "http",
        payload: {
          url: `${API_BASE_URL}/cards/churn_cohort`,
          method: "GET",
          params: {
            filters: { cohort_month: "${{ runtime.filters.cohort_month }}" },
          },
        },
      },
    },
    // Streaming version of the churn cohort table to demonstrate streaming-http
    {
      id: "churn_cohort_stream",
      kind: "table",
      title: "Churn Cohort (Streaming)",
      description: "Cohort retention matrix (streaming)",
      gridPosition: { x: 6, y: 16, w: 6, h: 8 } as CardGridPosition,
      settings: {
        table: { enablePagination: true },
        filters: {
          schema: [
            {
              name: "cohort_month",
              label: "Cohort Month",
              variant: "select",
              options: [
                { label: "All", value: "" },
                { label: "2025-01", value: "2025-01" },
                { label: "2025-02", value: "2025-02" },
                { label: "2025-03", value: "2025-03" },
              ],
            },
          ],
        },
      },
      query: {
        variant: "streaming-http",
        payload: {
          url: `${API_BASE_URL}/cards/churn_cohort_stream`,
          method: "GET",
          streamFormat: "ndjson",
          streamDelimiter: "\n",
          params: {
            filters: { cohort_month: "${{ runtime.filters.cohort_month }}" },
          },
        },
      },
    },
  ];

  return {
    id,
    title,
    theme,
    layout: {
      strategy: "grid",
      columns: 12,
      rowHeight: 60,
      margin: [16, 16],
    },
    reportCards: cards,
  };
};
