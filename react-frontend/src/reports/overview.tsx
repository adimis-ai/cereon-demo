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
  const title = "Overview";

  const cards: AnyDashboardReportCardSpec<
    Record<string, any>,
    Record<string, any>
  >[] = [];

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
