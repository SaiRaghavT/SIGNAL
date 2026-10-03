import { jsx } from "react/jsx-runtime";
function StatusBadge({ value }) {
  const v = (value || "UNKNOWN").toLowerCase().replace(/[_-]/g, " ");
  return /* @__PURE__ */ jsx("span", { className: `status status-${v.replace(/\s+/g, "-")}`, children: v });
}
export {
  StatusBadge
};
