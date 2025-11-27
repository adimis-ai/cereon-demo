import type {
  DashboardReportSpec,
  CardGridPosition,
  AnyDashboardReportCardSpec,
  DashboardTheme,
} from "@cereon/dashboard";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const getOverviewReport = (
  theme: DashboardTheme
): DashboardReportSpec => {
  const id = "overview";
  const title = "Packages Overview";

  const cards: AnyDashboardReportCardSpec<
    Record<string, any>,
    Record<string, any>
  >[] = [];
  cards.push({
    id: "overview_summary",
    kind: "markdown",
    title: "Project Summary",
    panel: false,
    transparent: true,
    gridPosition: { x: 0, y: 0, w: 12, h: 2 } as CardGridPosition,
    settings: {
      defaultContent: `# Cereon Packages Overview

This demo uses three packages that work together to deliver full-stack dashboards: **@cereon/dashboard** provides the frontend layout system and card infrastructure, **@cereon/recharts** adds chart components that plug directly into those cards, and **cereon-sdk** supplies the Python backend layer for typed, real-time card endpoints. In short: dashboard = UI, recharts = visualizations, sdk = backend data layer.`,
      markdownTheme: "auto",
      enableTables: true,
    },
  });

  cards.push({
    id: "packages_commits_line",
    kind: "recharts:line",
    title: "Repository Commits (30d)",
    description: "Daily commits across repositories",
    gridPosition: { x: 0, y: 4, w: 6, h: 7 } as CardGridPosition,
    settings: {
      chartConfig: {
        type: "line",
        curve: "monotone",
        series: [
          {
            dataKey: "cereon-dashboard",
            name: "cereon-dashboard",
            color: "var(--chart-1)",
            gradient: { enabled: true },
          },
          {
            dataKey: "cereon-recharts",
            name: "cereon-recharts",
            color: "var(--chart-2)",
            gradient: { enabled: true },
          },
          {
            dataKey: "cereon-sdk",
            name: "cereon-sdk",
            color: "var(--chart-3)",
            gradient: { enabled: true },
          },
        ],
        tooltip: { enabled: true },
        legend: { enabled: true },
      },
    },
    query: {
      variant: "http",
      payload: {
        url: `${API_BASE_URL}/cards/packages_commits_line?days=30`,
        method: "GET",
      },
    },
  });

  cards.push({
    id: "packages_downloads_area",
    kind: "recharts:area",
    title: "Package Downloads (30d)",
    description: "Daily downloads (synthetic when upstream unavailable)",
    gridPosition: { x: 6, y: 4, w: 6, h: 7 } as CardGridPosition,
    settings: {
      chartConfig: {
        type: "area",
        stacking: "none",
        curve: "natural",
        series: [
          {
            dataKey: "cereon-dashboard",
            name: "cereon-dashboard",
            color: "var(--chart-1)",
            gradient: { enabled: true },
          },
          {
            dataKey: "cereon-recharts",
            name: "cereon-recharts",
            color: "var(--chart-2)",
            gradient: { enabled: true },
          },
          {
            dataKey: "cereon-sdk",
            name: "cereon-sdk",
            color: "var(--chart-3)",
            gradient: { enabled: true },
          },
        ],
        tooltip: { enabled: true },
        legend: { enabled: true },
      },
    },
    query: {
      variant: "http",
      payload: {
        url: `${API_BASE_URL}/cards/packages_downloads_area?days=30`,
        method: "GET",
      },
    },
  });

  cards.push({
    id: "packages_likes_bar",
    kind: "recharts:bar",
    title: "Repository Stars",
    description: "Daily repo stars (mock: time-series over last 365+ days).",
    gridPosition: { x: 0, y: 14, w: 12, h: 7 } as CardGridPosition,
    settings: {
      chartConfig: {
        type: "bar",
        grouping: "grouped",
        responsive: true,
        xAxis: {
          label: { value: "date" },
          tick: { fontSize: 11, color: "var(--muted-foreground)" },
        },
        yAxis: {
          label: { value: "stars" },
          tick: { fontSize: 11, color: "var(--muted-foreground)" },
        },
        series: [
          {
            dataKey: "cereon-dashboard",
            name: "cereon-dashboard",
            color: "var(--chart-1)",
            gradient: { enabled: true },
          },
          {
            dataKey: "cereon-recharts",
            name: "cereon-recharts",
            color: "var(--chart-2)",
            gradient: { enabled: true },
          },
          {
            dataKey: "cereon-sdk",
            name: "cereon-sdk",
            color: "var(--chart-3)",
            gradient: { enabled: true },
          },
        ],
        tooltip: { enabled: true },
        legend: { enabled: true, position: "top" },
        barSize: 8,
        barGap: 4,
        barCategoryGap: "20%",
      },
    },
    query: {
      variant: "http",
      payload: {
        url: `${API_BASE_URL}/cards/packages_likes_bar`,
        method: "GET",
      },
    },
  });

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
