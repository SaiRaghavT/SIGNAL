import { jsx, jsxs } from "react/jsx-runtime";
import { PageHeader } from "../components/ui/PageHeader";
function AnalyticsPage() {
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Cluster / Analytics", subtitle: "Population-level analysis is available through POST /api/clusters/analyze." }),
    /* @__PURE__ */ jsxs("div", { className: "panel", children: [
      /* @__PURE__ */ jsx("h3", { children: "Backend capability" }),
      /* @__PURE__ */ jsx("p", { children: "This screen intentionally does not fabricate charts or historical metrics. Use the cluster analysis action with an appropriate backend request payload." })
    ] })
  ] });
}
export {
  AnalyticsPage
};
