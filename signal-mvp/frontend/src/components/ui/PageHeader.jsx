import { jsx, jsxs } from "react/jsx-runtime";
function PageHeader({ title, subtitle, children }) {
  return /* @__PURE__ */ jsxs("div", { className: "page-header", children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("h2", { children: title }),
      subtitle && /* @__PURE__ */ jsx("p", { children: subtitle })
    ] }),
    children && /* @__PURE__ */ jsx("div", { children })
  ] });
}
export {
  PageHeader
};
