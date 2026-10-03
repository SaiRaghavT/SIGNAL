import { jsx, jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases } from "../api/cases";
import { PageHeader } from "../components/ui/PageHeader";
import { Loading, ErrorState } from "../components/ui/Loading";
import { StatusBadge } from "../components/ui/StatusBadge";
function CasesPage() {
  const [data, setData] = useState();
  const [error, setError] = useState("");
  useEffect(() => {
    listCases().then(setData).catch((e) => setError(e.message));
  }, []);
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Cases", subtitle: "Persisted case snapshots exposed by the backend." }),
    /* @__PURE__ */ jsx("div", { className: "panel", children: error ? /* @__PURE__ */ jsx(ErrorState, { message: error }) : !data ? /* @__PURE__ */ jsx(Loading, {}) : /* @__PURE__ */ jsxs("table", { children: [
      /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
        /* @__PURE__ */ jsx("th", { children: "Case" }),
        /* @__PURE__ */ jsx("th", { children: "Disease" }),
        /* @__PURE__ */ jsx("th", { children: "Jurisdiction" }),
        /* @__PURE__ */ jsx("th", { children: "Status" }),
        /* @__PURE__ */ jsx("th", { children: "Reportability" }),
        /* @__PURE__ */ jsx("th", { children: "Updated" })
      ] }) }),
      /* @__PURE__ */ jsx("tbody", { children: data.items.map((c) => /* @__PURE__ */ jsxs("tr", { children: [
        /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(Link, { to: `/cases/${c.case_id}`, children: c.case_id }) }),
        /* @__PURE__ */ jsx("td", { children: c.disease || "\u2014" }),
        /* @__PURE__ */ jsx("td", { children: c.jurisdiction || "\u2014" }),
        /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(StatusBadge, { value: c.status }) }),
        /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx(StatusBadge, { value: c.reportability_decision }) }),
        /* @__PURE__ */ jsx("td", { children: new Date(c.updated_at).toLocaleString() })
      ] }, c.case_id)) })
    ] }) })
  ] });
}
export {
  CasesPage
};
