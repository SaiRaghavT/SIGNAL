import { useEffect, useState } from "react";
import { request } from "../api/client.js";
import { PageHeader } from "../components/ui/PageHeader.jsx";
import "../styles/analytics.css";

const EMPTY = "No data available";
const entries = (value) => Object.entries(value || {}).filter(([, count]) => Number.isFinite(Number(count)));
const total = (value) => entries(value).reduce((sum, [, count]) => sum + Number(count), 0);
const label = (value) => String(value).replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());

function DistributionCard({ title, values }) {
  const rows = entries(values);
  const max = Math.max(0, ...rows.map(([, count]) => Number(count)));
  return <section className="analytics-card">
    <h3>{title}</h3>
    {rows.length ? <div className="analytics-bars">{rows.map(([name, count]) => <div className="analytics-bar-row" key={name}>
      <span>{label(name)}</span><div className="analytics-bar-track"><i style={{ width: `${max ? Number(count) / max * 100 : 0}%` }} /></div><strong>{count}</strong>
    </div>)}</div> : <p className="analytics-empty">{EMPTY}</p>}
  </section>;
}

function MetricRows({ items }) {
  return <div className="analytics-metric-rows">{items.map(([name, value]) => <div key={name}>
    <span>{name}</span><strong>{value ?? EMPTY}</strong>
  </div>)}</div>;
}

export function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      request("/api/analytics/summary"),
      request("/api/analytics/cases"),
      request("/api/analytics/reporting"),
      request("/api/analytics/submissions"),
      request("/api/analytics/deadlines"),
    ]).then(([summary, cases, reporting, submissions, deadlines]) => {
      if (active) setData({ summary, cases, reporting, submissions, deadlines });
    }).catch((loadError) => {
      if (active) setError(loadError?.message || "Analytics data could not be loaded.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const statuses = data?.submissions?.by_status || {};
  const dispatched = Number(statuses.SUBMITTED || 0) + Number(statuses.ACKNOWLEDGED || 0);
  const kpis = [
    ["Reporting Cases", data?.summary?.cases],
    ["Reported", statuses.ACKNOWLEDGED ?? null],
    ["On-Time Rate", null],
    ["Avg Report Time", null],
  ];
  const deadlineStatuses = data?.deadlines?.by_status || {};
  const onTime = deadlineStatuses.ON_TIME ?? deadlineStatuses.ON_TIME_REPORTED;
  const atRisk = deadlineStatuses.AT_RISK ?? deadlineStatuses.UPCOMING;
  const late = deadlineStatuses.LATE ?? deadlineStatuses.OVERDUE;

  return <section className="analytics-page">
    <PageHeader title="Analytics" subtitle="Monitor reporting volume, timeliness, completeness, submission performance, and workload trends." />
    <div className="analytics-scope" aria-label="Analytics scope">All available data <span>Filters are not supported by the current analytics API</span></div>
    {loading ? <div className="analytics-state" role="status">Loading analytics…</div> : error ? <div className="analytics-error" role="alert">{error}</div> : <>
      <div className="analytics-kpis">{kpis.map(([name, value]) => <article className="analytics-card analytics-kpi" key={name}>
        <span>{name}</span><strong>{value == null ? EMPTY : name === "Avg Report Time" ? value : name === "On-Time Rate" ? `${value}%` : value}</strong>
      </article>)}</div>

      <section className="analytics-section">
        <div className="analytics-section-heading"><h2>Reporting Volume</h2><p>Reporting activity over the selected period.</p></div>
        <div className="analytics-card analytics-empty-card">No trend data available</div>
      </section>

      <div className="analytics-grid-two">
        <DistributionCard title="Cases by Condition" values={data?.cases?.by_disease} />
        <DistributionCard title="Cases by Jurisdiction" values={data?.cases?.by_jurisdiction} />
      </div>

      <section className="analytics-section">
        <div className="analytics-section-heading"><h2>Reporting Timeliness</h2><p>Performance against configured reporting deadlines.</p></div>
        <div className="analytics-grid-two">
          <article className="analytics-card"><h3>Deadline Performance</h3><MetricRows items={[["On time", onTime], ["At risk", atRisk], ["Late", late]]} /></article>
          <article className="analytics-card"><h3>Reporting Lifecycle</h3><div className="analytics-lifecycle">{["Detection", "Patient", "Case", "Queue", "Dispatch", "Acknowledgement"].map((stage, index) => <div key={stage}>
            {index > 0 && <span className="analytics-arrow" aria-hidden="true">›</span>}<span className="analytics-stage">{stage}</span><strong>{EMPTY}</strong>
          </div>)}</div></article>
        </div>
      </section>

      <section className="analytics-section">
        <div className="analytics-section-heading"><h2>Data Quality &amp; Completeness</h2><p>Availability of required reporting information.</p></div>
        <div className="analytics-grid-two">
          <article className="analytics-card"><h3>Reporting Completeness</h3><MetricRows items={[["Complete", null], ["Partial", null], ["Incomplete", null]]} /></article>
          <article className="analytics-card"><h3>Missing Information</h3><p className="analytics-empty">{EMPTY}</p></article>
        </div>
      </section>

      <section className="analytics-section">
        <div className="analytics-section-heading"><h2>Submission Performance</h2><p>Dispatch and acknowledgement outcomes.</p></div>
        <article className="analytics-card"><h3>Submission Outcomes</h3><MetricRows items={[
          ["Dispatched", dispatched],
          ["Acknowledged", statuses.ACKNOWLEDGED ?? null],
          ["Pending", statuses.SUBMITTED ?? null],
          ["Failed", Object.keys(statuses).length ? total({ FAILED: statuses.FAILED, REJECTED: statuses.REJECTED }) : null],
          ["Retry Required", statuses.RETRY_REQUIRED ?? null],
        ]} /></article>
      </section>
    </>}
  </section>;
}
