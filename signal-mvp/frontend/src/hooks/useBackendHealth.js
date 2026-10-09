import { useEffect, useState } from "react";
import { request } from "../api/client.js";

const HEALTH_CHECK_INTERVAL_MS = 30_000;

export function useBackendHealth() {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    let active = true;

    async function checkHealth() {
      try {
        const response = await request("/health");
        if (active) setStatus(response?.status === "ok" ? "online" : "offline");
      } catch {
        if (active) setStatus("offline");
      }
    }

    checkHealth();
    const intervalId = window.setInterval(checkHealth, HEALTH_CHECK_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  return status;
}
