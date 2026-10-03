import { jsx, jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { getDashboardSummary, getHealth } from "../api/dashboard";
import { PageHeader } from "../components/ui/PageHeader";
import { Loading, ErrorState } from "../components/ui/Loading";
function DashboardPage() {
  const [data, setData] = useState();
  const [error, setError] = useState("");
  const [health, setHealth] = useState("checking");
  useEffect(() => {
    Promise.all([getDashboardSummary(), getHealth()]).then(([d, h]) => {
      setData(d);
      setHealth(h.status);
    }).catch((e) => setError(e.message));
  }, []);
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Dashboard", subtitle: "Live workflow summary from the SIGNAL backend." }),
    /* @__PURE__ */ jsxs("div", { className: "connection", children: [
      /* @__PURE__ */ jsx("span", { className: `dot ${health === "ok" ? "ok" : ""}` }),
      " API ",
      health
    ] }),
    error ? /* @__PURE__ */ jsx(ErrorState, { message: error }) : !data ? /* @__PURE__ */ jsx(Loading, {}) : /* @__PURE__ */ jsx("div", { className: "kpi-grid", children: Object.entries({ Cases: data.cases, "Reportable Cases": data.reportable_cases, "Needs Review": data.needs_review, "Submitted": data.submitted_cases, "Follow-ups": data.follow_up_cases, "Upcoming Deadlines": data.upcoming_deadlines }).map(([k, v]) => /* @__PURE__ */ jsxs("div", { className: "kpi", children: [
      /* @__PURE__ */ jsx("span", { children: k }),
      /* @__PURE__ */ jsx("strong", { children: v })
    ] }, k)) }),
    /* @__PURE__ */ jsxs("div", { className: "panel", children: [
      /* @__PURE__ */ jsx("h3", { children: "Workflow" }),
      /* @__PURE__ */ jsxs("div", { className: "flow", children: [
        /* @__PURE__ */ jsx("span", { children: "Ingestion" }),
        /* @__PURE__ */ jsx("b", { children: "\u2192" }),
        /* @__PURE__ */ jsx("span", { children: "Canonical Data" }),
        /* @__PURE__ */ jsx("b", { children: "\u2192" }),
        /* @__PURE__ */ jsx("span", { children: "Detection" }),
        /* @__PURE__ */ jsx("b", { children: "\u2192" }),
        /* @__PURE__ */ jsx("span", { children: "Reportability" }),
        /* @__PURE__ */ jsx("b", { children: "\u2192" }),
        /* @__PURE__ */ jsx("span", { children: "Case" }),
        /* @__PURE__ */ jsx("b", { children: "\u2192" }),
        /* @__PURE__ */ jsx("span", { children: "Reporting" }),
        /* @__PURE__ */ jsx("b", { children: "\u2192" }),
        /* @__PURE__ */ jsx("span", { children: "Submission" })
      ] })
    ] })
  ] });
}
export {
  DashboardPage
};
