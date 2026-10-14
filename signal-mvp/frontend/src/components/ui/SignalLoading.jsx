import React from "react";

export function SignalLoading({
  title = "Loading",
  message = "Retrieving current information.",
  animate = true,
  className = "",
}) {
  return (
    <div
      className={`signal-loading ${className}`.trim()}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {animate && (
        <span className="signal-loading-mark" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      )}
      {title && <strong>{title}</strong>}
      {message && <span>{message}</span>}
    </div>
  );
}
