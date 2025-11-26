import { useMemo } from "react";
import { useTheme } from "./contexts/theme-provider";
import {
  Dashboard,
  type DashboardSpec,
  DashboardProvider,
} from "@cereon/dashboard";
import { getSaasMetricsReport } from "./reports/saas-metrics";

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
      reports: [getSaasMetricsReport(theme)],
    };
  }, []);

  return (
    <DashboardProvider
      spec={dashboardSpec}
      theme={theme}
      setTheme={setTheme}
      state={{
        activeReportId: "trading-view",
        additional: {
          theme: "dark",
          animations: "smooth",
        },
      }}
    >
      <Dashboard />
    </DashboardProvider>
  );
}

export default App;
