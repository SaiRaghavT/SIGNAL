import { jsx, jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { followUp } from "../api/workflow";
import { PageHeader } from "../components/ui/PageHeader";
function FollowupsPage() {
  const [caseId, setCaseId] = useState("");
  const [action, setAction] = useState("REQUEST_INFORMATION");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState("");
  const run = async () => {
    try {
      setResult(JSON.stringify(await followUp({ case_id: caseId, action, notes }), null, 2));
    } catch (e) {
      setResult(`Error: ${e.message}`);
    }
  };
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Follow-ups", subtitle: "PHA follow-up processing is persisted locally; external PHA interaction is simulated by the backend." }),
    /* @__PURE__ */ jsxs("div", { className: "panel form-grid", children: [
      /* @__PURE__ */ jsxs("label", { children: [
        "Case ID",
        /* @__PURE__ */ jsx("input", { value: caseId, onChange: (e) => setCaseId(e.target.value) })
      ] }),
      /* @__PURE__ */ jsxs("label", { children: [
        "Action",
        /* @__PURE__ */ jsxs("select", { value: action, onChange: (e) => setAction(e.target.value), children: [
          /* @__PURE__ */ jsx("option", { children: "REQUEST_INFORMATION" }),
          /* @__PURE__ */ jsx("option", { children: "INVESTIGATION" }),
          /* @__PURE__ */ jsx("option", { children: "OUTCOME_UPDATE" }),
          /* @__PURE__ */ jsx("option", { children: "CLOSE" })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("label", { children: [
        "Notes",
        /* @__PURE__ */ jsx("textarea", { value: notes, onChange: (e) => setNotes(e.target.value) })
      ] }),
      /* @__PURE__ */ jsx("button", { className: "primary", onClick: run, disabled: !caseId, children: "Process follow-up" }),
      result && /* @__PURE__ */ jsx("pre", { className: "result", children: result })
    ] })
  ] });
}
export {
  FollowupsPage
};
