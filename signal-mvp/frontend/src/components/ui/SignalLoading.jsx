import React from "react";

export function SignalLoading({ title = "Loading", message = "Retrieving current information.", animate = true }) {
  return (
    <div className="signal-loading" role="status" aria-live="polite" aria-atomic="true">
      {animate && <span className="signal-loading-mark" aria-hidden="true"><i /><i /><i /></span>}
      <strong>{title}</strong>
      <span>{message}</span>
    </div>
  );
}
