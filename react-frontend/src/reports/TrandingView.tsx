import * as React from "react";
import type {
  DashboardReportSpec,
  DashboardReportCardSpec,
  CardGridPosition,
} from "@cereon/dashboard";

/**
 * Lightweight React wrapper that ensures tv.js is loaded once and constructs
 * a TradingView.widget instance inside a container div.
 */
function TradingViewWidget({
  id,
  widgetOptions,
}: {
  id: string;
  widgetOptions: Record<string, any>;
}) {
  React.useEffect(() => {
    // ensure global namespace
    const win = window as any;

    function createWidget() {
      try {
        // Avoid double-creation for same container
        if (!document.getElementById(id)) return;
        // TradingView.widget will attach to the container id
        // Merge container_id into options
        const opts = { ...widgetOptions, container_id: id };
        // eslint-disable-next-line @typescript-eslint/no-unsafe-call
        new win.TradingView.widget(opts);
      } catch (err) {
        // swallow; host app should handle logging if necessary
        // (no-op: placing a console.warn for dev visibility)
        // eslint-disable-next-line no-console
        console.warn("TradingView.widget init failed:", err);
      }
    }

    if (win.TradingView && typeof win.TradingView.widget === "function") {
      createWidget();
      return;
    }

    // load script once
    const existing = document.querySelector(
      'script[data-tradingview="tv.js"]'
    ) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", createWidget, { once: true });
      return;
    }
    const s = document.createElement("script");
    s.setAttribute("data-tradingview", "tv.js");
    s.src = "https://s3.tradingview.com/tv.js";
    s.async = true;
    s.onload = createWidget;
    document.head.appendChild(s);
    // no cleanup of script; widget stays mounted as long as div exists
  }, [id, widgetOptions]);

  // container for TradingView to render into
  return (
    <div
      id={id}
      style={{
        width: "100%",
        height: "100%",
        minHeight: 200,
        boxSizing: "border-box",
      }}
    />
  );
}

/**
 * Helper to create grid position in a simple bento layout (3 columns).
 * row increments every three items.
 */
function makeGridPosition(
  index: number,
  colCount = 3,
  itemHeight = 6
): CardGridPosition {
  const col = index % colCount;
  const row = Math.floor(index / colCount);
  return {
    x: col * 4,
    y: row * itemHeight,
    w: 4,
    h: itemHeight,
    minW: 3,
    minH: 4,
  };
}

/**
 * Render function used for each card: wraps Widget in a small bento cell.
 * Uses the DashboardReportCardSpec.renderCard signature.
 */
function makeRenderCard(widgetId: string, widgetOptions: Record<string, any>) {
  const id = `tv_${widgetId.replace(/\s+/g, "-").toLowerCase()}`;
  return () => {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          justifyContent: "stretch",
          height: "100%",
          padding: 8,
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            flex: 1,
            borderRadius: 8,
            overflow: "hidden",
            background: "var(--card-bg, #fff)",
          }}
        >
          <TradingViewWidget id={id} widgetOptions={widgetOptions} />
        </div>
      </div>
    );
  };
}

/**
 * All major TradingView widgets (per TradingView docs). For each widget I
 * provide a minimal/typical widgetOptions object. You can tweak each options
 * object (symbols, themes, widths) as needed when embedding in your app.
 *
 * Source: TradingView widgets index & docs. :contentReference[oaicite:1]{index=1}
 */
export function getTradingViewReport(): DashboardReportSpec {
  // list of widgets with a small canonical options object (adjust as required)
  const widgets: { id: string; title: string; options: Record<string, any> }[] =
    [
      {
        id: "advanced-chart",
        title: "Advanced Real-Time Chart",
        options: {
          // example default: symbol + autosize
          symbol: "NASDAQ:AAPL",
          interval: "D",
          timezone: "Etc/UTC",
          theme: "light",
          style: "1",
          locale: "en",
          toolbar_bg: "#f1f3f6",
          withdateranges: true,
          allow_symbol_change: true,
          details: true,
          hide_side_toolbar: false,
          studies_overrides: {},
        },
      },
      {
        id: "symbol-overview",
        title: "Symbol Overview",
        options: {
          symbol: "NASDAQ:AAPL",
          width: "100%",
          height: "100%",
          locale: "en",
          colorTheme: "light",
        },
      },
      {
        id: "mini-chart",
        title: "Mini Chart",
        options: {
          symbol: "NASDAQ:MSFT",
          width: "100%",
          height: "220",
          locale: "en",
          colorTheme: "light",
        },
      },
      {
        id: "market-overview",
        title: "Market Overview",
        options: {
          // Market Overview widget uses dedicated constructor options (example)
          locale: "en",
          colorTheme: "light",
          showChart: true,
        },
      },
      {
        id: "stock-market",
        title: "Stock Market (Hot Lists)",
        options: {
          // placeholder options for hot lists
          colorTheme: "light",
          exchanges: ["NYSE", "NASDAQ"],
        },
      },
      {
        id: "market-data",
        title: "Market Data",
        options: { colorTheme: "light", width: "100%", height: "350" },
      },
      {
        id: "ticker-tape",
        title: "Ticker Tape",
        options: {
          symbols: [
            { proName: "NASDAQ:AAPL", title: "AAPL" },
            { proName: "NASDAQ:MSFT", title: "MSFT" },
            { proName: "NASDAQ:TSLA", title: "TSLA" },
          ],
          colorTheme: "light",
          isTransparent: false,
          displayMode: "adaptive",
        },
      },
      {
        id: "ticker",
        title: "Ticker (horizontal)",
        options: {
          symbols: [
            { proName: "NASDAQ:AAPL", title: "AAPL" },
            { proName: "NASDAQ:GOOGL", title: "GOOGL" },
          ],
          colorTheme: "light",
        },
      },
      {
        id: "single-ticker",
        title: "Single Ticker",
        options: {
          symbol: "NASDAQ:AMZN",
          colorTheme: "light",
          width: "100%",
          height: "60",
        },
      },
      {
        id: "stock-heatmap",
        title: "Stock Heatmap",
        options: {
          type: "stock",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "crypto-heatmap",
        title: "Crypto Coins Heatmap",
        options: {
          type: "crypto",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "etf-heatmap",
        title: "ETF Heatmap",
        options: {
          type: "etf",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "forex-cross-rates",
        title: "Forex Cross Rates",
        options: {
          type: "forex",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "forex-heatmap",
        title: "Forex Heatmap",
        options: {
          type: "forex-heatmap",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "screener",
        title: "Screener",
        options: {
          defaultColumn: "overview",
          colorTheme: "light",
          locale: "en",
        },
      },
      {
        id: "crypto-market",
        title: "Cryptocurrency Market",
        options: {
          default: "crypto",
          colorTheme: "light",
          width: "100%",
          height: "350",
        },
      },
      {
        id: "symbol-info",
        title: "Symbol Info",
        options: {
          symbol: "NASDAQ:TSLA",
          colorTheme: "light",
          width: "100%",
          height: "320",
        },
      },
      {
        id: "technical-analysis",
        title: "Technical Analysis",
        options: {
          symbol: "NASDAQ:TSLA",
          interval: "60",
          colorTheme: "light",
          width: "100%",
          height: "360",
        },
      },
      {
        id: "fundamental-data",
        title: "Fundamental Data",
        options: {
          symbol: "NASDAQ:GOOGL",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "company-profile",
        title: "Company Profile",
        options: {
          symbol: "NASDAQ:GOOGL",
          colorTheme: "light",
          width: "100%",
          height: "260",
        },
      },
      {
        id: "top-stories",
        title: "Top Stories (News)",
        options: {
          feed: "market",
          colorTheme: "light",
          width: "100%",
          height: "300",
        },
      },
      {
        id: "economic-calendar",
        title: "Economic Calendar",
        options: {
          colorTheme: "light",
          width: "100%",
          height: "400",
          locale: "en",
        },
      },
    ];

  // Build reportCards array using bento layout mapping
  const reportCards = widgets.map((w, i) => {
    const gridPosition = makeGridPosition(i, 3, 6);
    const card: DashboardReportCardSpec<string, any, any> = {
      kind: "tradingview-widget",
      id: `tradingview.${w.id}`,
      title: w.title,
      description: `TradingView widget: ${w.title}`,
      gridPosition,
      settings: { enableDownload: false, gridPosition },
      renderCard: makeRenderCard(w.id, w.options),
      "aria-label": `TradingView widget ${w.title}`,
    };
    return card as any;
  });

  return {
    id: "trading-view",
    title: "Trading View",
    description: "Displays trading data using TradingView widgets.",
    reportCards,
    layout: {
      strategy: "grid",
      columns: 12,
      gap: 12,
      rowHeight: 30,
    },
  };
}
