import { jsx } from "react/jsx-runtime";
function Loading() {
  return /* @__PURE__ */ jsx("div", { className: "loading", children: "Loading\u2026" });
}
function ErrorState({ message }) {
  return /* @__PURE__ */ jsx("div", { className: "error-state", children: message });
}
export {
  ErrorState,
  Loading
};
