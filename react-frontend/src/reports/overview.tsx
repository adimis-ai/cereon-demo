import type {
  DashboardReportSpec,
  CardGridPosition,
  AnyDashboardReportCardSpec,
  DashboardTheme,
} from "@cereon/dashboard";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/* TODO: Like a senior react ts developer, just like saas analytics report, create an overview report with these cards:

Report Cards Layout Diagram:
|       Summary Markdown Card       |
| Line Chart Card | Area Chart Card |
|           Bar Chart Card          |
*/

export const getOverviewReport = (
  theme: DashboardTheme
): DashboardReportSpec => {
  const id = "overview";
  const title = "Packages Overview";

  const cards: AnyDashboardReportCardSpec<
    Record<string, any>,
    Record<string, any>
  >[] = [];
  // Summary markdown at top, full width
  cards.push({
    id: "overview_summary",
    kind: "markdown",
    title: "Project Summary",
    panel: false,
    transparent: true,
    gridPosition: { x: 0, y: 0, w: 12, h: 3.5 } as CardGridPosition,
    settings: {
      defaultContent: `# Cereon Projects Overview\n\nThis dashboard highlights key signals for the Cereon open-source projects: ` +
        "`@cereon/dashboard`, `@cereon/recharts`, and `cereon-sdk`.\n\n" +
        "- Area chart: package downloads (last 30 days)\n" +
        "- Line chart: commit activity (last 30 days)\n" +
        "- Horizontal bar chart: repository stars (current)\n\n" +
        "Data refreshes periodically from the demo backend.",
      markdownTheme: "auto",
      enableTables: true,
    },
  });

  // Left: Line chart (commits), Right: Area chart (downloads)
  cards.push({
    id: "packages_commits_line",
    kind: "recharts:line",
    title: "Repository Commits (30d)",
    description: "Daily commits across repositories",
    gridPosition: { x: 0, y: 4, w: 6, h: 10 } as CardGridPosition,
    settings: {
      chartConfig: {
        type: "line",
        curve: "monotone",
        series: [
          { dataKey: "@cereon/dashboard", name: "dashboard", color: "#3b82f6" },
          { dataKey: "@cereon/recharts", name: "recharts", color: "#10b981" },
          { dataKey: "cereon-sdk", name: "sdk", color: "#f97316" },
        ],
        tooltip: { enabled: true },
        legend: { enabled: true },
      },
    },
    query: {
      variant: "http",
      payload: { url: `${API_BASE_URL}/cards/packages_commits_line?days=30`, method: "GET" },
    },
  });

  cards.push({
    id: "packages_downloads_area",
    kind: "recharts:area",
    title: "Package Downloads (30d)",
    description: "Daily downloads (synthetic when upstream unavailable)",
    gridPosition: { x: 6, y: 4, w: 6, h: 10 } as CardGridPosition,
    settings: {
      chartConfig: {
        type: "area",
        stacking: "none",
        curve: "natural",
        series: [
          { dataKey: "@cereon/dashboard", name: "dashboard", color: "#3b82f6" },
          { dataKey: "@cereon/recharts", name: "recharts", color: "#10b981" },
          { dataKey: "cereon-sdk", name: "sdk", color: "#f97316" },
        ],
        tooltip: { enabled: true },
        legend: { enabled: true },
      },
    },
    query: {
      variant: "http",
      payload: { url: `${API_BASE_URL}/cards/packages_downloads_area?days=30`, method: "GET" },
    },
  });

  // Full-width horizontal bar chart for likes/stars
  cards.push({
    id: "packages_likes_bar",
    kind: "recharts:bar",
    title: "Repository Stars",
    description: "Current GitHub stars for each repository",
    gridPosition: { x: 0, y: 14, w: 12, h: 8 } as CardGridPosition,
    settings: {
      chartConfig: {
        type: "bar-horizontal",
        xAxis: { label: { value: "stars" } },
        series: [{ dataKey: "value", name: "stars", color: "#06b6d4" }],
        tooltip: { enabled: true },
        legend: { enabled: false },
      },
    },
    query: {
      variant: "http",
      payload: { url: `${API_BASE_URL}/cards/packages_likes_bar`, method: "GET" },
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
