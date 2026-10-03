import { jsx, jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { trackSubmission, acknowledge, retrySubmission } from "../api/workflow";
import { PageHeader } from "../components/ui/PageHeader";
function SubmissionsPage() {
  const [id, setId] = useState("");
  const [result, setResult] = useState("");
  const run = async (fn) => {
    try {
      setResult(JSON.stringify(await fn(), null, 2));
    } catch (e) {
      setResult(`Error: ${e.message}`);
    }
  };
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Submissions", subtitle: "Submission actions available in the backend. No submission-list endpoint is currently exposed." }),
    /* @__PURE__ */ jsxs("div", { className: "panel form-grid", children: [
      /* @__PURE__ */ jsxs("label", { children: [
        "Submission ID",
        /* @__PURE__ */ jsx("input", { value: id, onChange: (e) => setId(e.target.value) })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "button-row", children: [
        /* @__PURE__ */ jsx("button", { className: "primary", onClick: () => run(() => trackSubmission(id)), children: "Track" }),
        /* @__PURE__ */ jsx("button", { onClick: () => run(() => acknowledge(id)), children: "Process acknowledgement" }),
        /* @__PURE__ */ jsx("button", { onClick: () => run(() => retrySubmission(id)), children: "Retry" })
      ] }),
      result && /* @__PURE__ */ jsx("pre", { className: "result", children: result })
    ] })
  ] });
}
export {
  SubmissionsPage
};
