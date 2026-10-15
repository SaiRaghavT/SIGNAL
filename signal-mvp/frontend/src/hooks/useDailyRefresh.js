import { useEffect, useState } from "react";

function currentDayKey() {
  const now = new Date();
  return `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
}

function millisecondsUntilNextDay() {
  const now = new Date();
  const nextDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  return Math.max(1, nextDay.getTime() - now.getTime());
}

export function useDailyRefresh() {
  const [day, setDay] = useState(currentDayKey);

  useEffect(() => {
    let timer;
    const refreshIfDayChanged = () => {
      const nextDay = currentDayKey();
      setDay((currentDay) => (currentDay === nextDay ? currentDay : nextDay));
    };
    const scheduleNextRefresh = () => {
      timer = window.setTimeout(() => {
        refreshIfDayChanged();
        scheduleNextRefresh();
      }, millisecondsUntilNextDay());
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") refreshIfDayChanged();
    };

    scheduleNextRefresh();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  return day;
}
