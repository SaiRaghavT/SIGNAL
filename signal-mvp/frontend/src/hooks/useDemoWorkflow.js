import { useCallback, useEffect, useState } from "react";
import {
  completeDemoWorkflowStage,
  demoWorkflowChangeEvent,
  readDemoWorkflow,
  resetDemoWorkflow,
} from "../state/demoWorkflow.js";

export function useDemoWorkflow(caseId) {
  const [snapshot, setSnapshot] = useState(() => readDemoWorkflow(caseId));

  useEffect(() => {
    setSnapshot(readDemoWorkflow(caseId));
    const update = (event) => {
      if (!event?.detail?.caseId || event.detail.caseId === caseId) {
        setSnapshot(readDemoWorkflow(caseId));
      }
    };
    const eventName = demoWorkflowChangeEvent();
    window.addEventListener(eventName, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(eventName, update);
      window.removeEventListener("storage", update);
    };
  }, [caseId]);

  const reset = useCallback(() => resetDemoWorkflow(caseId), [caseId]);
  const complete = useCallback((stage) => completeDemoWorkflowStage(caseId, stage), [caseId]);
  return { active: Boolean(snapshot), stages: snapshot?.stages || {}, reset, complete };
}
