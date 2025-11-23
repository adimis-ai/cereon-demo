import React, { useEffect, useRef, useMemo } from "react";
import { createChart, ColorType, AreaSeries } from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  AreaSeriesPartialOptions,
  Time,
  WhitespaceData,
  AreaData,
} from "lightweight-charts";
import type {
  BaseCardProps,
  BaseDashboardCardRecord,
  CommonCardSettings,
} from "@cereon/dashboard";

export type SeriesDescriptor = {
  id: string;
  name?: string;
  visible?: boolean;
  options?: AreaSeriesPartialOptions;
};

export interface AreaChartSettings extends CommonCardSettings {
  series: SeriesDescriptor[];
  chartOptions?: Parameters<typeof createChart>[1];
  height?: number;
  fitContentOnUpdate?: boolean;
  onChartReady?: (chart: IChartApi) => void;
}

export interface AreaChartRecord extends BaseDashboardCardRecord {
  kind: "tlwc:area";
  data: Record<string, Array<AreaData<Time> | WhitespaceData<Time>>>;
}

export interface AreaChartProps
  extends BaseCardProps<
    "tlwc:area",
    { "tlwc:area": AreaChartSettings },
    { "tlwc:area": AreaChartRecord }
  > {}

export const AreaChartComponent: React.FC<AreaChartProps> = ({
  card,
  records,
  className,
  reportId,
}) => {
  const {
    series,
    chartOptions = {},
    height = 300,
    fitContentOnUpdate = true,
    onChartReady,
  } = card.settings as AreaChartSettings;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesMapRef = useRef<Map<string, ISeriesApi<"Area">>>(new Map());
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const seriesById = useMemo(() => {
    const map = new Map<string, SeriesDescriptor>();
    for (const s of series) map.set(s.id, s);
    return map;
  }, [series]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: "#000000", type: ColorType.Solid },
        textColor: "#d1d4dc",
      },
      ...chartOptions,
    });

    chartRef.current = chart;

    resizeObserverRef.current = new ResizeObserver(() => {
      if (!chartRef.current || !containerRef.current) return;
      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
      });
    });

    resizeObserverRef.current.observe(containerRef.current);
    onChartReady?.(chart);

    return () => {
      resizeObserverRef.current?.disconnect();
      seriesMapRef.current.forEach((s) => {
        try {
          chart.removeSeries(s);
        } catch {}
      });
      seriesMapRef.current.clear();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const existingMap = seriesMapRef.current;

    for (const [id, sRef] of existingMap.entries()) {
      const incoming = seriesById.get(id);
      if (!incoming || incoming.visible === false) {
        try {
          chart.removeSeries(sRef);
        } catch {}
        existingMap.delete(id);
      }
    }

    for (const descriptor of series) {
      if (descriptor.visible === false) {
        const existing = existingMap.get(descriptor.id);
        if (existing) {
          try {
            chart.removeSeries(existing);
          } catch {}
          existingMap.delete(descriptor.id);
        }
        continue;
      }

      const existing = existingMap.get(descriptor.id);
      const opts: AreaSeriesPartialOptions = {
        ...descriptor.options,
        title: descriptor.name ?? descriptor.id,
      };

      // Gather data for this series from all records
      const merged: Array<AreaData<Time> | WhitespaceData<Time>> = [];
      for (const rec of records) {
        // Ensure record has the expected shape
        const r = rec as AreaChartRecord;
        if (!r || !r.data) continue;
        const seriesData = r.data?.[descriptor.id];
        if (!Array.isArray(seriesData)) continue;
        for (const p of seriesData) {
          // push as-is; deduping happens below based on `time`
          merged.push(p);
        }
      }

      if (merged.length > 0) {
        // Deduplicate by time: use a Map keyed by time (string | number | { year, month.. })
        const keyed = new Map<string, AreaData<Time> | WhitespaceData<Time>>();
        for (const pt of merged) {
          try {
            const key = typeof pt.time === "object" ? JSON.stringify(pt.time) : String(pt.time);
            keyed.set(key, pt);
          } catch {
            // fallback: stringify
            keyed.set(String(pt.time), pt);
          }
        }

        const deduped = Array.from(keyed.values()).sort((a, b) => {
          const ta: any = a.time as any;
          const tb: any = b.time as any;
          if (typeof ta === "number" && typeof tb === "number") return ta - tb;
          const sa = typeof ta === "object" ? JSON.stringify(ta) : String(ta);
          const sb = typeof tb === "object" ? JSON.stringify(tb) : String(tb);
          return sa < sb ? -1 : sa > sb ? 1 : 0;
        });

        if (!existing) {
          const s = chart.addSeries(AreaSeries, opts);
          s.setData(deduped as AreaData<Time>[]);
          existingMap.set(descriptor.id, s);
        } else {
          try {
            existing.applyOptions(opts);
          } catch {}
          existing.setData(deduped as AreaData<Time>[]);
        }
      } else {
        // no data for this series across records
        if (!existing) {
          const s = chart.addSeries(AreaSeries, opts);
          s.setData([]);
          existingMap.set(descriptor.id, s);
        } else {
          try {
            existing.applyOptions(opts);
          } catch {}
          existing.setData([]);
        }
      }
    }

    if (fitContentOnUpdate) {
      try {
        chart.timeScale().fitContent();
      } catch {}
    }
  }, [series, seriesById, fitContentOnUpdate]);

  return (
    <div
      key={`${reportId}-${card.id}-[tlwc:area]-chart`}
      ref={containerRef}
      style={{ width: "100%", height }}
      className={className}
    />
  );
};

export default AreaChartComponent;
