from fastapi import FastAPI

from backend.app.agents.cluster_signal.api import router as cluster_router
from backend.app.agents.status_api import router as agent_status_router
from backend.app.analytics.api import router as analytics_router
from backend.app.canonical.api import router as canonical_router
from backend.app.candidate.router import router as candidates_router
from backend.app.case.api import router as cases_router
from backend.app.case.workflow_api import router as case_workflow_router
from backend.app.followup.api import router as followups_router
from backend.app.submission.api import router as submissions_router
from backend.app.submission.admin_api import router as admin_reporting_router
from backend.app.dashboard.router import router as dashboard_router
from backend.app.detection.api import router as detection_router
from backend.app.ingestion.api.fhir import router as fhir_router
from backend.app.ingestion.documents.api import router as document_router
from backend.app.ingestion.hl7.api import router as hl7_router
from backend.app.agents.audit_ledger.router import api_router as audit_api_router
from backend.app.agents.audit_ledger.router import router as audit_ledger_router
from backend.app.agents.document_intelligence.router import (
    router as document_intelligence_router,
)
from backend.app.agents.nlp_evidence.router import router as nlp_evidence_router
from backend.app.agents.candidate_disposition.router import (
    router as candidate_disposition_router,
)
from backend.app.agents.deadline_calculation.router import (
    router as deadline_calculation_router,
)

from backend.app.agents.deadline_escalation.router import (
    router as deadline_escalation_router,
)

from backend.app.agents.case_assembly.router import (
    router as case_assembly_router,
)

from backend.app.agents.attestation_control.router import (
    router as attestation_control_router,
)
from backend.app.agents.reportability_workflow.router import (
    router as reportability_workflow_router,

)

from backend.app.agents.manual_reporting.router import (
    router as manual_reporting_router,
)

from backend.app.agents.form_rendering.router import (
    public_router as reporting_router,
    router as form_rendering_router,
)


from backend.app.agents.ecr_submission.router import (
    router as ecr_submission_router,
)


from backend.app.agents.submission_tracking.router import (
    router as submission_tracking_router,
)

from backend.app.agents.acknowledgement.router import (
    router as acknowledgement_router,
)


from backend.app.agents.retry_resubmission.router import (
    router as retry_resubmission_router,
)

from backend.app.agents.public_health_followup.router import (
    router as public_health_followup_router,
)
from backend.app.workflow.router import router as workflow_router

app = FastAPI(
    title="SIGNAL MVP",
    description="Public Health Reporting Intelligence Layer",
    version="0.1.0",
)


# ---------------------------------------------------------
# Ingestion APIs
# ---------------------------------------------------------

# FHIR ingestion
app.include_router(fhir_router)

# HL7 v2 ingestion
app.include_router(hl7_router)

# Unstructured document ingestion
app.include_router(document_router)

# Audit ledger
app.include_router(audit_ledger_router)
app.include_router(audit_api_router)

app.include_router(deadline_calculation_router)

app.include_router(deadline_escalation_router)

app.include_router(case_assembly_router)



app.include_router(form_rendering_router)
app.include_router(reporting_router)

# ---------------------------------------------------------
# Canonical Data APIs
# ---------------------------------------------------------

# Read-only access to the standardized SIGNAL patient context
app.include_router(canonical_router)
app.include_router(candidates_router)

# Persisted case summary list for the manager-facing Cases screen.
app.include_router(cases_router)
app.include_router(case_workflow_router)
app.include_router(submissions_router)
app.include_router(admin_reporting_router)
app.include_router(followups_router)
app.include_router(dashboard_router)

# Candidate detection
app.include_router(detection_router)

# Population-level cluster analysis
app.include_router(cluster_router)


app.include_router(attestation_control_router)
app.include_router(candidate_disposition_router)
app.include_router(document_intelligence_router)
app.include_router(nlp_evidence_router)

app.include_router(reportability_workflow_router)


app.include_router(manual_reporting_router)


app.include_router(
    ecr_submission_router
)

app.include_router(
    submission_tracking_router
)

app.include_router(
    acknowledgement_router
)

app.include_router(
    retry_resubmission_router
)

app.include_router(
    public_health_followup_router
)

app.include_router(workflow_router)
app.include_router(agent_status_router)
app.include_router(analytics_router)
# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "signal-mvp",
    }
