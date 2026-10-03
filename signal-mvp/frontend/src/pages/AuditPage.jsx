import { jsx, jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { auditEvent } from "../api/workflow";
import { PageHeader } from "../components/ui/PageHeader";
function AuditPage() {
  const [body, setBody] = useState('{"entity_type":"case","entity_id":"CASE-ID","event_type":"UI_ACTION","actor_type":"user","actor_id":"reporting_user","source_agent":"frontend","status":"SUCCESS","description":"Frontend audit event","metadata":{}}');
  const [result, setResult] = useState("");
  return /* @__PURE__ */ jsxs("section", { children: [
    /* @__PURE__ */ jsx(PageHeader, { title: "Technical / Audit", subtitle: "Write an audit event through the backend audit ledger." }),
    /* @__PURE__ */ jsxs("div", { className: "panel", children: [
      /* @__PURE__ */ jsx("textarea", { className: "code-input", value: body, onChange: (e) => setBody(e.target.value) }),
      /* @__PURE__ */ jsx("button", { className: "primary", onClick: async () => {
        try {
          setResult(JSON.stringify(await auditEvent(JSON.parse(body)), null, 2));
        } catch (e) {
          setResult(`Error: ${e.message}`);
        }
      }, children: "Create audit event" }),
      result && /* @__PURE__ */ jsx("pre", { className: "result", children: result })
    ] })
  ] });
}
export {
  AuditPage
};
