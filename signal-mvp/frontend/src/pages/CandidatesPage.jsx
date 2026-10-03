import { jsx, jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { detectCandidates } from "../api/detection";
import { PageHeader } from "../components/ui/PageHeader";
function CandidatesPage() {
  const [id, setId] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const run = async () => {
    setError("");
    try {
      setResult(JSON.stringify(await detectCandidates(id), null, 2));
    } catch (e) {
      setError(e.message);
    }
  };
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Candidates", subtitle: "Run candidate detection for a canonical patient. The backend currently exposes this as an action, not a candidate history list." }),
    /* @__PURE__ */ jsxs("div", { className: "panel form-grid", children: [
      /* @__PURE__ */ jsxs("label", { children: [
        "Patient UUID",
        /* @__PURE__ */ jsx("input", { value: id, onChange: (e) => setId(e.target.value) })
      ] }),
      /* @__PURE__ */ jsx("button", { className: "primary", onClick: run, disabled: !id, children: "Detect candidates" }),
      error && /* @__PURE__ */ jsx("div", { className: "error-state", children: error }),
      result && /* @__PURE__ */ jsx("pre", { className: "result", children: result })
    ] })
  ] });
}
export {
  CandidatesPage
};
