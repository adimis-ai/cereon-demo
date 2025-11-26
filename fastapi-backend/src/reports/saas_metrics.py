# fastapi-backend/src/reports/saas_metrics.py
# | Card Name             | Visual Type  | Transport      | Purpose / Data Shown                                    |
# | --------------------- | ------------ | -------------- | ------------------------------------------------------- |
# | MrrOverviewCard       | number       | http           | Core KPIs: MRR, ARR, MRR Δ%, churn %, as_of             |
# | SaasUserGrowthCard    | number       | http           | DAU / WAU / MAU, activation rate, new users             |
# | RevenueTrendCard      | line_chart   | streaming-http | Time-series: MRR / New / Expansion over time            |
# | RevenueAreaTrendCard  | area_chart   | streaming-http | Cumulative revenue / rolling revenue bands              |
# | PlansBreakdownCard    | bar_chart    | http           | Active users & seats per pricing plan                   |
# | RevenueSharePieCard   | pie_chart    | http           | Revenue share by product / plan / channel               |
# | FeatureUsageRadarCard | radar_chart  | http           | Multi-dimension usage profile per feature set           |
# | HealthRadialCard      | radial_chart | http           | System health score (online %, degraded %, offline %)   |
# | ChurnCohortCard       | table        | http           | Cohort retention matrix (cohort_month × month_offset %) |
