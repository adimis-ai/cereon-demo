import { useCallback, useMemo } from "react";
import { useTheme } from "./contexts/theme-provider";
import { Dashboard, type DashboardSpec, DashboardProvider } from "@cereon/dashboard";

const API_BASE_URL = "http://localhost:8000";

function App() {
  const createQueryPayload = useCallback(
    (endpoint: string, customParams?: Record<string, any>) => ({
      method: "GET" as const,
      url: `${API_BASE_URL}/api/cards/overview/${endpoint}`,
      params: { ...customParams },
      timeout: 30000,
      retryAttempts: 3,
      retryDelay: 1000,
    }),
    []
  );

  const _isIsoDateString = (v: any) => {
    return typeof v === "string" && !Number.isNaN(Date.parse(String(v)));
  };

  const formatDateTick = (v: any) => {
    try {
      if (typeof v !== "string") return String(v ?? "");
      let s = v;
      const m = s.match(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.[^Z]*)?Z$/);
      if (m) {
        const prefix = m[1];
        const frac = m[2] || ""; // e.g. '.%f' or '.123456'
        if (frac) {
          const digits = frac.replace(/[^0-9]/g, "");
          if (digits.length > 0) {
            const trimmed = digits.slice(0, 6).padEnd(3, "0");
            s = `${prefix}.${trimmed}Z`;
          } else {
            s = `${prefix}Z`;
          }
        }
      }

      if (_isIsoDateString(s)) {
        const d = new Date(s);
        return d.toLocaleString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        });
      }
      return String(v ?? "");
    } catch (e) {
      return String(v ?? "");
    }
  };

  const formatNumber = (raw: any) => {
    if (raw === null || raw === undefined || raw === "") return "";
    const n = typeof raw === "number" ? raw : parseFloat(String(raw));
    if (Number.isNaN(n)) return String(raw);
    const abs = Math.abs(n);
    // Percent-like values in [-1,1]
    if (abs <= 1 && !Number.isInteger(n)) {
      return `${(n * 100).toFixed(1)}%`;
    }
    // Large numbers -> compact (1.2K, 3.4M)
    if (abs >= 1000) {
      return new Intl.NumberFormat(undefined, {
        notation: "compact",
        maximumFractionDigits: 2,
      }).format(n);
    }
    // Floats show 2 decimals, ints as locale string
    if (!Number.isInteger(n)) return n.toFixed(2);
    return n.toLocaleString();
  };

  const formatPrice = (raw: any) => {
    if (raw === null || raw === undefined || raw === "") return "";
    const n = typeof raw === "number" ? raw : parseFloat(String(raw));
    if (Number.isNaN(n)) return String(raw);
    return new Intl.NumberFormat(undefined, {
      maximumFractionDigits: 2,
    }).format(n);
  };

  const formatTimeWithSeconds = (v: any) => {
    try {
      // Accept string timestamps like ISO or numeric epoch
      let s: string | number = v as any;
      if (typeof v === "string") {
        // reuse the same normalization used for formatDateTick
        const m = v.match(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.[^Z]*)?Z$/);
        if (m) {
          const prefix = m[1];
          const frac = m[2] || "";
          if (frac) {
            const digits = frac.replace(/[^0-9]/g, "");
            if (digits.length > 0) {
              const trimmed = digits.slice(0, 6).padEnd(3, "0");
              s = `${prefix}.${trimmed}Z`;
            } else {
              s = `${prefix}Z`;
            }
          } else {
            s = `${prefix}Z`;
          }
        } else {
          s = v;
        }
      }

      const d = typeof s === "number" ? new Date(s) : new Date(String(s));
      if (Number.isNaN(d.getTime())) return String(v ?? "");
      return d.toLocaleTimeString(undefined, { hour12: false });
    } catch (e) {
      return String(v ?? "");
    }
  };

  const dashboardSpec: DashboardSpec = useMemo(() => {
    const bentoLayout = {
      strategy: "grid" as const,
      columns: 12,
      gap: 12,
      compact: false,
      autopack: true,
      preventCollision: true,
      enableDragDrop: true,
      enableResize: true,
      margin: [12, 12] as [number, number],
      containerPadding: [24, 24] as [number, number],
      rowHeight: 110,
    };

    const allReportCards = [
      // Top row - Key metrics
      {
        id: "liquidity_depth_number",
        title: "Total Liquidity Depth",
        description: "Current market liquidity depth across all orders",
        kind: "number",
        settings: { enableDownload: true },
        query: {
          variant: "http",
          payload: createQueryPayload("liquidity_depth_number"),
        },
        gridPosition: { x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      },
      {
        id: "counterparty_avg_kyc",
        title: "Average KYC Score",
        description: "Average Know Your Customer score across counterparties",
        kind: "number",
        query: {
          variant: "http",
          payload: createQueryPayload("counterparty_avg_kyc"),
        },
        gridPosition: { x: 3, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      },
      {
        id: "sector_exposure_pie",
        title: "Sector Exposure",
        description: "Distribution of instruments across sectors",
        kind: "pie",
        settings: {
          chartConfig: {
            type: "pie",
            dataKey: "value",
            nameKey: "label",
            variant: "donut",
            innerRadius: "40%",
            outerRadius: "80%",
            paddingAngle: 2,
            cornerRadius: 4,
            labelPosition: "outside",
            colors: [
              "var(--color-chart-1)",
              "var(--color-chart-2)",
              "var(--color-chart-3)",
              "var(--color-chart-4)",
              "var(--color-chart-5)",
              "var(--color-success)",
              "var(--color-warning)",
              "var(--color-destructive)",
            ],
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-chart-5)",
                  "var(--color-success)",
                  "var(--color-warning)",
                  "var(--color-destructive)",
                ],
              },
            },
            animation: {
              enabled: true,
              duration: 1000,
              easing: "ease-out",
            },
            legend: {
              enabled: true,
              position: "right",
              align: "center",
            },
          },
        },
        query: {
          variant: "http",
          payload: createQueryPayload("sector_exposure_pie"),
        },
        gridPosition: { x: 6, y: 0, w: 6, h: 4, minW: 4, minH: 3 },
      },

      // Second row - Volume and price analytics
      {
        id: "market_volume",
        title: "Market Volume Trends",
        description: "Trading volume aggregated by exchange or asset class",
        kind: "area",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "area",
            stacking: "normal",
            curve: "monotone",
            gradient: true,
            fillOpacity: 0.6,
            strokeWidth: 2,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-chart-5)",
                ],
              },
            },
            xAxis: {
              // volume charts from server use `date` as string
              tick: { formatter: formatDateTick },
              label: { value: "Date", position: "insideBottom", offset: -8 },
            },
            yAxis: { tick: { formatter: formatNumber } },
            series: [
              {
                dataKey: "LSE",
                name: "London Stock Exchange",
                color: "var(--color-chart-1)",
                strokeWidth: 2,
                fillOpacity: 0.6,
              },
              {
                dataKey: "NASDAQ",
                name: "NASDAQ",
                color: "var(--color-chart-2)",
                strokeWidth: 2,
                fillOpacity: 0.6,
              },
              {
                dataKey: "NYSE",
                name: "New York Stock Exchange",
                color: "var(--color-chart-3)",
                strokeWidth: 2,
                fillOpacity: 0.6,
              },
              {
                dataKey: "CBOE",
                name: "Chicago Board Options Exchange",
                color: "var(--color-chart-4)",
                strokeWidth: 2,
                fillOpacity: 0.6,
              },
            ],
            animation: {
              enabled: true,
              duration: 750,
              easing: "ease-out",
            },
          },
        },
        query: {
          variant: "http",
          payload: createQueryPayload("market_volume"),
        },
        gridPosition: { x: 0, y: 2, w: 6, h: 4, minW: 4, minH: 3 },
      },
      {
        id: "price_movement",
        title: "Price Movement",
        description: "Historical price movements for selected tickers",
        kind: "line",
        settings: {
          chartConfig: {
            type: "line",
            curve: "monotone",
            strokeWidth: 2,
            dots: true,
            dotSize: 4,
            connectNulls: true,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-chart-5)",
                ],
              },
            },
            xAxis: { tick: { formatter: formatDateTick } },
            yAxis: { tick: { formatter: formatPrice } },
            series: [
              {
                dataKey: "UCQ",
                name: "UCQ",
                color: "var(--color-chart-1)",
                strokeWidth: 2,
                dot: { size: 4 },
              },
              {
                dataKey: "VTN",
                name: "VTN",
                color: "var(--color-chart-2)",
                strokeWidth: 2,
                dot: { size: 4 },
              },
              {
                dataKey: "KTM",
                name: "KTM",
                color: "var(--color-chart-3)",
                strokeWidth: 2,
                dot: { size: 4 },
              },
              {
                dataKey: "QJLNP",
                name: "QJLNP",
                color: "var(--color-chart-4)",
                strokeWidth: 2,
                dot: { size: 4 },
              },
              {
                dataKey: "OAJ",
                name: "OAJ",
                color: "var(--color-chart-5)",
                strokeWidth: 2,
                dot: { size: 4 },
              },
            ],
            animation: {
              enabled: true,
              duration: 600,
              easing: "ease-in-out",
            },
            legend: {
              enabled: true,
              position: "top",
              align: "end",
            },
          },
        },
        query: {
          variant: "http",
          payload: createQueryPayload("price_movement"),
        },
        gridPosition: { x: 0, y: 6, w: 8, h: 4, minW: 6, minH: 3 },
      },
      {
        id: "top_instruments_by_volume",
        title: "Top Instruments by Volume",
        description: "Highest volume trading instruments",
        kind: "bar",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "bar",
            orientation: "vertical",
            barSize: 32,
            barGap: 4,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-chart-5)",
                ],
              },
            },
            series: [
              {
                dataKey: "volume",
                name: "Volume",
                color: "var(--color-chart-1)",
                radius: [2, 2, 0, 0],
              },
            ],
            animation: {
              enabled: true,
              duration: 800,
              easing: "ease-out",
            },
            yAxis: {
              label: {
                value: "Volume",
                position: "insideLeft",
                style: { textAnchor: "middle" },
              },
              tick: { formatter: formatNumber },
            },
            xAxis: {
              tick: {
                angle: -45,
                textAnchor: "end",
                formatter: (v: any) => String(v),
              },
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/top_instruments_by_volume`,
          },
        },
        gridPosition: { x: 8, y: 6, w: 4, h: 4, minW: 3, minH: 3 },
      },

      // Third row - Advanced analytics
      {
        id: "correlation_radar",
        title: "Correlation Analysis",
        description: "Correlation radar for selected instrument",
        kind: "radar",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "radar",
            polarGrid: {
              enabled: true,
              gridType: "polygon",
              radialLines: true,
              stroke: "var(--color-border)",
              strokeDasharray: "3 3",
              fillOpacity: 0.1,
            },
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                ],
              },
            },
            series: [
              {
                dataKey: "correlation",
                name: "Correlation",
                color: "var(--color-chart-1)",
                fill: "var(--color-chart-1)",
                opacity: 0.3,
                strokeWidth: 2,
              },
            ],
            animation: {
              enabled: true,
              duration: 1000,
              easing: "ease-in-out",
            },
            polarAngleAxis: {
              tick: {
                fontSize: 12,
                radius: 10,
              },
            },
            // Add tooltip formatter for correlation values (0-1)
            tooltip: { formatter: (value: any) => formatNumber(value) },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/correlation_radar`,
          },
        },
        gridPosition: { x: 0, y: 10, w: 6, h: 5, minW: 4, minH: 4 },
      },
      {
        id: "instrument_health_radial",
        title: "Instrument Health",
        description: "Multi-dimensional health assessment of instruments",
        kind: "radial",
        settings: {
          chartConfig: {
            type: "radial",
            innerRadius: "20%",
            outerRadius: "80%",
            theme: {
              colors: {
                custom: [
                  "var(--color-success)",
                  "var(--color-warning)",
                  "var(--color-destructive)",
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                ],
              },
            },
            series: [
              {
                dataKey: "health_score",
                name: "Health Score",
                color: "var(--color-chart-1)",
              },
            ],
            yAxis: { tick: { formatter: formatNumber } },
            animation: {
              enabled: true,
              duration: 1200,
              easing: "ease-out",
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/instrument_health_radial`,
          },
        },
        gridPosition: { x: 6, y: 10, w: 6, h: 5, minW: 4, minH: 4 },
      },

      // Fourth row - Additional charts
      {
        id: "signal_score_trends",
        title: "Signal Score Trends",
        description: "Trending signal scores over time",
        kind: "line",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "line",
            curve: "monotone",
            strokeWidth: 2,
            dots: true,
            dotSize: 3,
            connectNulls: false,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-chart-5)",
                ],
              },
            },
            series: [
              {
                dataKey: "momentum",
                name: "Momentum",
                color: "var(--color-chart-1)",
                strokeWidth: 2,
                dot: { size: 3 },
              },
              {
                dataKey: "value",
                name: "Value",
                color: "var(--color-chart-2)",
                strokeWidth: 2,
                dot: { size: 3 },
              },
              {
                dataKey: "quality",
                name: "Quality",
                color: "var(--color-chart-3)",
                strokeWidth: 2,
                dot: { size: 3 },
              },
              {
                dataKey: "low_vol",
                name: "Low Volatility",
                color: "var(--color-chart-4)",
                strokeWidth: 2,
                dot: { size: 3 },
              },
            ],
            animation: {
              enabled: true,
              duration: 700,
              easing: "ease-in-out",
            },
            legend: {
              enabled: true,
              position: "top",
              align: "center",
            },
            xAxis: { tick: { formatter: formatDateTick } },
            yAxis: {
              label: {
                value: "Signal Score",
                position: "insideLeft",
                style: { textAnchor: "middle" },
              },
              tick: { formatter: formatNumber },
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/signal_score_trends`,
          },
        },
        gridPosition: { x: 0, y: 15, w: 6, h: 4, minW: 4, minH: 3 },
      },
      {
        id: "vwap_vs_median_order_price",
        title: "VWAP vs Median Order Price",
        description: "Volume-weighted average price comparison",
        kind: "line",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "line",
            curve: "monotone",
            strokeWidth: 2,
            dots: true,
            dotSize: 4,
            connectNulls: true,
            theme: {
              colors: {
                custom: ["var(--color-chart-1)", "var(--color-chart-2)"],
              },
            },
            series: [
              {
                dataKey: "VWAP",
                name: "VWAP",
                color: "var(--color-chart-1)",
                strokeWidth: 2,
                dot: { size: 4 },
              },
              {
                dataKey: "MedianOrderPrice",
                name: "Median Order Price",
                color: "var(--color-chart-2)",
                strokeWidth: 2,
                strokeDasharray: "5 5",
                dot: { size: 4 },
              },
            ],
            animation: {
              enabled: true,
              duration: 600,
              easing: "ease-in-out",
            },
            legend: {
              enabled: true,
              position: "top",
              align: "end",
            },
          },
          filters: {
            schema: [
              [
                {
                  name: "limit",
                  label: "Limit",
                  variant: "number",
                  placeholder: "Number of rows to return",
                  defaultValue: 100,
                },
                {
                  name: "offset",
                  label: "Offset",
                  variant: "number",
                  placeholder: "Result offset (pagination)",
                  defaultValue: 0,
                },
              ],
              {
                name: "timeframe",
                label: "Timeframe",
                variant: "select",
                placeholder: "Select timeframe",
                defaultValue: "1d",
                options: [
                  { value: "1h", label: "1 hour" },
                  { value: "6h", label: "6 hours" },
                  { value: "12h", label: "12 hours" },
                  { value: "1d", label: "1 day" },
                  { value: "7d", label: "7 days" },
                  { value: "30d", label: "30 days" },
                ],
              },
              {
                name: "exchanges",
                label: "Exchanges",
                variant: "multi-select",
                placeholder: "Select exchanges",
                defaultValue: ["LSE", "NASDAQ"],
                options: [
                  { value: "LSE", label: "LSE" },
                  { value: "NASDAQ", label: "NASDAQ" },
                  { value: "NYSE", label: "NYSE" },
                  { value: "CBOE", label: "CBOE" },
                  { value: "BATS", label: "BATS" },
                ],
              },
            ],
            showClearAll: true,
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/vwap_vs_median_order_price`,
            params: {
              limit: "${{runtime.limit}}",
              offset: "${{runtime.offset}}",
            },
          },
        },
        gridPosition: { x: 6, y: 15, w: 6, h: 4, minW: 4, minH: 3 },
      },

      // Fifth row - More analytics
      {
        id: "trade_count_avg_size",
        title: "Trade Count & Average Size",
        description: "Daily trade count and average trade size",
        kind: "line",
        settings: {
          chartConfig: {
            type: "line",
            curve: "monotone",
            strokeWidth: 2,
            dots: true,
            dotSize: 3,
            theme: {
              colors: {
                custom: ["var(--color-chart-1)", "var(--color-chart-3)"],
              },
            },
            series: [
              {
                dataKey: "trade_count",
                name: "Trade Count",
                color: "var(--color-chart-1)",
                strokeWidth: 2,
              },
              {
                dataKey: "avg_qty",
                name: "Average Size",
                color: "var(--color-chart-3)",
                strokeWidth: 2,
                strokeDasharray: "3 3",
              },
            ],
            animation: {
              enabled: true,
              duration: 600,
              easing: "ease-out",
            },
            legend: {
              enabled: true,
              position: "top",
              align: "center",
            },
            xAxis: { tick: { formatter: formatDateTick } },
            yAxis: { tick: { formatter: formatNumber } },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/trade_count_avg_size`,
          },
        },
        gridPosition: { x: 0, y: 19, w: 4, h: 4, minW: 3, minH: 3 },
      },
      {
        id: "order_to_trade_conversion",
        title: "Order-to-Trade Conversion",
        description: "Conversion rates by asset class",
        kind: "bar",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "bar",
            orientation: "vertical",
            grouping: "grouped",
            barSize: 24,
            barGap: 4,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-success)",
                ],
              },
            },
            series: [
              {
                dataKey: "orders",
                name: "Orders",
                color: "var(--color-chart-1)",
                radius: [2, 2, 0, 0],
              },
              {
                dataKey: "trades",
                name: "Trades",
                color: "var(--color-chart-2)",
                radius: [2, 2, 0, 0],
              },
              {
                dataKey: "conversion",
                name: "Conversion Rate",
                color: "var(--color-success)",
                radius: [2, 2, 0, 0],
              },
            ],
            animation: {
              enabled: true,
              duration: 800,
              easing: "ease-out",
            },
            legend: {
              enabled: true,
              position: "top",
              align: "center",
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/order_to_trade_conversion`,
          },
        },
        gridPosition: { x: 4, y: 19, w: 4, h: 4, minW: 3, minH: 3 },
      },
      {
        id: "spread_distribution",
        title: "Spread Distribution",
        description: "Distribution of bid-ask spreads",
        kind: "bar",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "bar",
            orientation: "vertical",
            barSize: 32,
            barGap: 6,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-warning)",
                ],
              },
            },
            series: [
              {
                dataKey: "cnt",
                name: "Count",
                color: "var(--color-chart-2)",
                radius: [4, 4, 0, 0],
              },
            ],
            animation: {
              enabled: true,
              duration: 900,
              easing: "ease-out",
            },
            yAxis: {
              label: {
                value: "Count",
                position: "insideLeft",
                style: { textAnchor: "middle" },
              },
            },
            xAxis: {
              label: {
                value: "Spread Range",
                position: "insideBottom",
                offset: -10,
              },
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/spread_distribution`,
          },
        },
        gridPosition: { x: 8, y: 19, w: 4, h: 4, minW: 3, minH: 3 },
      },

      // Sixth row - Event analytics
      {
        id: "event_impact_chart",
        title: "Event Impact Analysis",
        description: "Price movement around market events",
        kind: "area",
        settings: {
          chartConfig: {
            type: "area",
            stacking: "none",
            curve: "monotone",
            gradient: true,
            fillOpacity: 0.4,
            strokeWidth: 2,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-warning)",
                  "var(--color-destructive)",
                ],
              },
            },
            series: [
              {
                dataKey: "price",
                name: "Price Movement",
                color: "var(--color-chart-1)",
                fill: "var(--color-chart-1)",
                opacity: 0.4,
                strokeWidth: 2,
                gradient: {
                  enabled: true,
                  colors: ["var(--color-chart-1)", "transparent"],
                  stops: [0, 1],
                },
              },
            ],
            animation: {
              enabled: true,
              duration: 800,
              easing: "ease-in-out",
            },
            xAxis: {
              label: {
                value: "Time",
                position: "insideBottom",
                offset: -10,
              },
              tick: { formatter: formatDateTick },
            },
            yAxis: {
              label: {
                value: "Price",
                position: "insideLeft",
                style: { textAnchor: "middle" },
              },
              tick: { formatter: formatPrice },
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/event_impact_chart`,
          },
        },
        gridPosition: { x: 0, y: 23, w: 8, h: 4, minW: 6, minH: 3 },
      },
      {
        id: "top_signals_leaderboard",
        title: "Top Signals Leaderboard",
        description: "Best performing trading signals",
        kind: "bar",
        settings: {
          enableDownload: true,
          chartConfig: {
            type: "bar",
            orientation: "horizontal",
            barSize: 28,
            barGap: 4,
            theme: {
              colors: {
                custom: [
                  "var(--color-success)",
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                ],
              },
            },
            series: [
              {
                dataKey: "score",
                name: "Score",
                color: "var(--color-success)",
                radius: [0, 3, 3, 0],
              },
            ],
            animation: {
              enabled: true,
              duration: 900,
              easing: "ease-out",
            },
            xAxis: {
              label: {
                value: "Performance Score",
                position: "insideBottom",
                offset: -10,
              },
            },
            yAxis: {
              tick: {
                fontSize: 11,
              },
            },
          },
        },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/top_signals_leaderboard`,
          },
        },
        gridPosition: { x: 8, y: 23, w: 4, h: 4, minW: 3, minH: 3 },
      },

      // Seventh row - Tables
      {
        id: "top_instruments_table",
        title: "Top Instruments Details",
        description: "Detailed view of top trading instruments",
        kind: "table",
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/top_instruments_table`,
          },
        },
        gridPosition: { x: 0, y: 27, w: 6, h: 6, minW: 4, minH: 4 },
      },
      {
        id: "counterparty_risk_snapshot",
        title: "Counterparty Risk Assessment",
        description: "Risk metrics for trading counterparties",
        kind: "table",
        settings: { enableDownload: true },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/counterparty_risk_snapshot`,
          },
        },
        gridPosition: { x: 6, y: 27, w: 6, h: 6, minW: 4, minH: 4 },
      },

      // Eighth row - More tables and alerts
      {
        id: "alerts_table",
        title: "Market Alerts",
        description: "Active alerts and negative sentiment events",
        kind: "table",
        settings: { enableDownload: true },
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/alerts_table`,
          },
        },
        gridPosition: { x: 0, y: 33, w: 6, h: 5, minW: 4, minH: 4 },
      },
      {
        id: "correlation_clusters",
        title: "Correlation Clusters",
        description: "Instrument groupings by sector correlation",
        kind: "table",
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/correlation_clusters`,
          },
        },
        gridPosition: { x: 6, y: 33, w: 6, h: 5, minW: 4, minH: 4 },
      },

      // Ninth row - Informational content
      {
        id: "event_impact_markdown",
        title: "Event Impact Summary",
        description: "Detailed event impact analysis",
        kind: "markdown",
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/event_impact_markdown`,
          },
        },
        gridPosition: { x: 0, y: 38, w: 6, h: 4, minW: 4, minH: 3 },
      },
      {
        id: "metadata_markdown",
        title: "Schema & Parameters Guide",
        description: "Graph schema and parameter documentation",
        kind: "markdown",
        query: {
          variant: "http",
          payload: {
            method: "GET",
            url: `${API_BASE_URL}/api/cards/overview/metadata_markdown`,
          },
        },
        gridPosition: { x: 6, y: 38, w: 6, h: 4, minW: 4, minH: 3 },
      },

      // Real-time streaming card - separate position
      {
        id: "price_movement_realtime",
        title: "Real-time Price Movement",
        description: "Live streaming price data",
        kind: "line",
        settings: {
          enableDownload: false,
          chartConfig: {
            type: "line",
            curve: "monotone",
            strokeWidth: 2,
            dots: false,
            connectNulls: true,
            theme: {
              colors: {
                custom: [
                  "var(--color-chart-1)",
                  "var(--color-chart-2)",
                  "var(--color-chart-3)",
                  "var(--color-chart-4)",
                  "var(--color-chart-5)",
                  "var(--color-success)",
                  "var(--color-warning)",
                ],
              },
            },
            series: [
              {
                dataKey: "price",
                name: "Price",
                color: "var(--color-chart-1)",
                strokeWidth: 2,
              },
            ],
            animation: {
              enabled: false,
            },
            legend: {
              enabled: true,
              position: "top",
              align: "end",
            },
            tooltip: {
              enabled: true,
              trigger: "hover",
              animation: {
                duration: 100,
              },
              formatter: (value: any) => formatPrice(value),
            },
            yAxis: {
              label: {
                value: "Price",
                position: "insideLeft",
                style: { textAnchor: "middle" },
              },
              tick: { formatter: formatPrice },
            },
            xAxis: {
              dataKey: "ts",
              label: {
                value: "Time",
                position: "insideBottom",
                offset: -10,
              },
              tick: { formatter: formatTimeWithSeconds },
            },
          },
        },
        query: {
          variant: "websocket",
          payload: {
            url: `ws://localhost:8000/api/cards/overview/price_movement_realtime`,
            topic: "price_updates",
            subscriptionId: "realtime-prices",
            heartbeatInterval: 30000,
            maxReconnectAttempts: 10,
          },
        },
        gridPosition: { x: 0, y: 42, w: 12, h: 5, minW: 8, minH: 4 },
      },
    ];

    const n = allReportCards.length;
    const t1 = Math.ceil(n / 3);
    const t2 = Math.ceil((2 * n) / 3);

    const first = allReportCards.slice(0, t1);
    const second = allReportCards.slice(t1, t2);
    const third = allReportCards.slice(t2);

    return {
      id: "cereon-overview",
      title: "Cereon Financial Analytics Dashboard",
      description:
        "Comprehensive market analytics and risk management dashboard",
      config: {
        animations: "smooth",
        defaultRefreshInterval: 5000,
        maxConcurrentQueries: 8,
      },
      reports: [
        {
          id: "overview_summary",
          title: "Market Overview — Summary",
          description: "High-level tiles and summary charts — bento layout.",
          layout: bentoLayout,
          reportCards: first,
        },
        {
          id: "overview_analytics",
          title: "Market Overview — Analytics",
          description:
            "Charts and analytics for deeper inspection — bento layout.",
          layout: bentoLayout,
          reportCards: second,
        },
        {
          id: "overview_data",
          title: "Market Overview — Data & Streams",
          description:
            "Tables, markdowns and real-time streams — bento layout.",
          layout: bentoLayout,
          reportCards: third,
        },
      ],
    } as DashboardSpec;
  }, [createQueryPayload]);

  const { theme, setTheme } = useTheme();

  return (
    <DashboardProvider
      spec={dashboardSpec}
      theme={theme}
      setTheme={setTheme}
      state={{
        activeReportId: "overview_summary",
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
