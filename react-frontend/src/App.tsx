import { useEffect, useMemo } from "react";
import { useTheme } from "./contexts/theme-provider";
import {
  Dashboard,
  type DashboardSpec,
  DashboardProvider,
  useDashboard,
  NumberCard,
  MarkdownCard,
} from "@cereon/dashboard";
import { getSaasMetricsReport } from "./reports/saas-metrics";
import * as charts from "@cereon/recharts";
import { getOverviewReport } from "./reports/overview";
import TableCard from "./cards/table";

function CardRegistrar() {
  const { registerCard } = useDashboard();

  useEffect(() => {
    registerCard("recharts:line", charts.LineChartCard);
    registerCard("recharts:area", charts.AreaChartCard);
    registerCard("recharts:bar", charts.BarChartCard);
    registerCard("recharts:pie", charts.PieChartCard);
    registerCard("recharts:radar", charts.RadarChartCard);
    registerCard("recharts:radial", charts.RadialChartCard);
    registerCard("table", TableCard);
    registerCard("number", NumberCard);
    registerCard("markdown", MarkdownCard);
  }, []);

  return null;
}

function App() {
  const { theme, setTheme } = useTheme();

  const dashboardSpec: DashboardSpec = useMemo(() => {
    return {
      id: "cereon-demo",
      title: "Cereon Demo Dashboard",
      description: "A demo dashboard showcasing various widgets and reports.",
      config: {
        animations: "smooth",
        defaultRefreshInterval: 5000,
        maxConcurrentQueries: 8,
        theme: theme,
      },
      reports: [getOverviewReport(theme), getSaasMetricsReport(theme)],
    };
  }, []);

  return (
    <DashboardProvider
      spec={dashboardSpec}
      theme={theme}
      setTheme={setTheme}
      state={{
        activeReportId: "overview",
        additional: {
          theme: "dark",
          animations: "smooth",
        },
      }}
    >
      <CardRegistrar />
      <Dashboard />
    </DashboardProvider>
  );
}

export default App;
