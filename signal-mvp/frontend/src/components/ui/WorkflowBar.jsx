import { ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function WorkflowBar({
  current,
  previousSteps = [],
  backPath,
  backLabel = "Back",
}) {
  const navigate = useNavigate();

  const steps = [
    ...previousSteps,
    {
      key: current,
      label: current,
    },
  ];

  const handleBack = () => {
    if (backPath) {
      navigate(backPath);
    } else {
      navigate(-1);
    }
  };

  return (
    <div className="workflow-navigation">
      <div className="workflow-bar">

        {/* LEFT: WORKFLOW */}
        <div className="workflow-steps">
          {steps.map((step, index) => {
            const isCurrent =
              index === steps.length - 1;

            return (
              <div
                className="workflow-step-wrapper"
                key={`${step.key}-${index}`}
              >
                <div
                  className={
                    isCurrent
                      ? "workflow-step current"
                      : "workflow-step completed"
                  }
                >
                  {step.label}
                </div>

                {index < steps.length - 1 && (
                  <ChevronRight
                    size={15}
                    className="workflow-chevron"
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* RIGHT: BACK */}
        <button
          type="button"
          className="workflow-back"
          onClick={handleBack}
        >
          ← {backLabel}
        </button>

      </div>
    </div>
  );
}