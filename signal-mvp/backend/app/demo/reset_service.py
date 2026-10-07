"""Transactional reset of SIGNAL's controlled demo workflow only."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.config.demo import DEMO_FACILITY_ID, is_demo_case
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.demo_case_baseline import DemoCaseBaseline
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import (
    Acknowledgement,
    CaseWorkflowRecord,
    Report,
    SubmissionAttempt,
)
from backend.app.smart_field_population.mapper import populate_report_fields


_RENDER_ID = re.compile(r"^[0-9a-f]{32}$")


def _datetime_value(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _case_snapshot(case: Case) -> dict[str, Any]:
    return {
        "status": case.status,
        "final_decision": case.final_decision,
        "report_fields": case.report_fields or {},
        "provider": case.provider or {},
        "facility": case.facility or {},
        "deadline": case.deadline.isoformat() if case.deadline else None,
        "severity": case.severity,
        "warnings": case.warnings or [],
    }


def _candidate_snapshot(candidate: Candidate | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    return {
        "status": candidate.status,
        "jurisdiction": candidate.jurisdiction,
        "deadline": candidate.deadline.isoformat() if candidate.deadline else None,
        "severity": candidate.severity,
    }


def store_demo_baseline(db: Session, case: Case, candidate: Candidate | None) -> DemoCaseBaseline | None:
    """Capture the original assembly values once; never overwrite an existing baseline."""
    if not is_demo_case(case):
        return None
    baseline = db.query(DemoCaseBaseline).filter(DemoCaseBaseline.case_id == str(case.case_id)).first()
    if baseline is None:
        baseline = DemoCaseBaseline(
            case_id=str(case.case_id),
            case_state=_case_snapshot(case),
            candidate_state=_candidate_snapshot(candidate),
        )
        db.add(baseline)
        db.flush()
    return baseline


def _reconstruct_prebaseline_state(case: Case, candidate: Candidate | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rebuild legacy baseline using the same deterministic assembly mapper and intact evidence.

    The case workspace only edits report_fields/provider/facility. Patient, clinical,
    lab, and AI evidence stay unchanged, so the original generated form fields can
    be recreated from those source values. The original facility mapper emitted
    only canonical provenance keys; provider contact details are not source data.
    """
    current_facility = case.facility if isinstance(case.facility, dict) else {}
    facility = {
        "facility_id": current_facility.get("facility_id") or DEMO_FACILITY_ID,
        "source": current_facility.get("source"),
        "source_resource": current_facility.get("source_resource"),
    }
    current_provider = case.provider if isinstance(case.provider, dict) else {}
    references = current_provider.get("references") or ([current_provider["reference"]] if current_provider.get("reference") else [])
    provider = (
        {
            "status": "REFERENCE_ONLY",
            "reference": references[0],
            "references": references,
            "reference_source": "canonical lab/document performer or author reference",
            "missing_fields": ["name", "phone", "address"],
        }
        if references
        else {"status": "MISSING", "missing_fields": ["name", "phone", "address"]}
    )
    patient = case.patient if isinstance(case.patient, dict) else {}
    laboratory = case.laboratory_evidence if isinstance(case.laboratory_evidence, list) else []
    clinical = case.clinical_evidence if isinstance(case.clinical_evidence, dict) else {}
    ai_evidence = case.ai_evidence if isinstance(case.ai_evidence, dict) else {}
    candidate_data = {
        "candidate_id": case.candidate_id,
        "disease": case.disease,
        "patient": patient,
        "provider": provider,
        "facility": facility,
        "encounter": {},
        "clinical_evidence": clinical,
        "laboratory_evidence": laboratory,
        "ai_evidence": ai_evidence,
        "jurisdiction": case.jurisdiction,
        "jurisdiction_status": case.jurisdiction_status,
        "reportability_decision": case.reportability_decision,
        "reportability_evidence_status": case.reportability_evidence_status,
        "reconciliation_decision": case.final_decision,
    }
    smart_fields = populate_report_fields(candidate_data)
    final_decision = case.final_decision or case.reportability_decision
    missing_provider = [key for key in ("name", "phone", "address") if not provider.get(key)]
    status = final_decision
    warnings: list[str] = []
    if case.jurisdiction_status != "RESOLVED":
        warnings.append("Jurisdiction requires review.")
    if not patient:
        warnings.append("Patient information is missing.")
    if not case.disease:
        warnings.append("Disease information is missing.")
    if status != "HOLD" and case.jurisdiction_status != "RESOLVED":
        status = "NEEDS_REVIEW"
        warnings.append("Jurisdiction requires review.")
    if status != "HOLD" and (smart_fields.required_missing_fields or missing_provider or not facility.get("name")):
        status = "NEEDS_REVIEW"
        if smart_fields.required_missing_fields:
            warnings.append(f"{len(smart_fields.required_missing_fields)} required reporting fields need human completion.")
        if missing_provider:
            warnings.append("Provider information needs human completion.")
        if not facility.get("name"):
            warnings.append("Facility name needs human completion.")
    case_state = {
        "status": status,
        "final_decision": final_decision,
        "report_fields": smart_fields.fields,
        "provider": provider,
        "facility": facility,
        "deadline": None,
        "severity": None,
        "warnings": warnings,
    }
    # A candidate is made reprocessable while remaining linked to this stable case.
    candidate_state = {"status": "POTENTIAL", "jurisdiction": None, "deadline": None, "severity": None}
    return case_state, candidate_state


def _stage_generated_pdfs(render_ids: list[str]) -> list[tuple[Path, Path]]:
    from backend.app.agents.form_rendering.service import get_rendered_pdf_path

    staged: list[tuple[Path, Path]] = []
    try:
        for render_id in set(render_ids):
            if not isinstance(render_id, str) or not _RENDER_ID.fullmatch(render_id):
                continue
            source = get_rendered_pdf_path(render_id)
            if source is None:
                continue
            target = source.with_name(".demo-reset-" + uuid4().hex + source.suffix)
            os.replace(source, target)
            staged.append((source, target))
    except Exception:
        _restore_staged_files(staged)
        raise
    return staged


def _restore_staged_files(staged: list[tuple[Path, Path]]) -> None:
    for source, target in reversed(staged):
        if target.exists():
            os.replace(target, source)


def _demo_cases(db: Session) -> list[Case]:
    return [case for case in db.query(Case).all() if is_demo_case(case)]


def reset_demo(db: Session, requested_case_id: UUID | None = None) -> dict[str, Any]:
    """Reset exactly one stable-marker demo case and its workflow-generated records."""
    staged_files: list[tuple[Path, Path]] = []
    try:
        cases = _demo_cases(db)
        if requested_case_id is not None:
            cases = [case for case in cases if case.case_id == requested_case_id]
        if not cases:
            raise HTTPException(status_code=404, detail="SIGNAL Texas demo case was not found.")
        if len(cases) != 1:
            raise HTTPException(status_code=409, detail="More than one SIGNAL Texas demo case matched; reset was not applied.")
        case = cases[0]
        case_id = str(case.case_id)
        candidate = db.query(Candidate).filter(Candidate.candidate_id == case.candidate_id).first()
        baseline = db.query(DemoCaseBaseline).filter(DemoCaseBaseline.case_id == case_id).first()
        if baseline is None:
            case_state, candidate_state = _reconstruct_prebaseline_state(case, candidate)
            baseline = DemoCaseBaseline(case_id=case_id, case_state=case_state, candidate_state=candidate_state)
            db.add(baseline)
            db.flush()
        case_state = baseline.case_state
        if not isinstance(case_state, dict) or not {"report_fields", "provider", "facility", "status"}.issubset(case_state):
            raise HTTPException(status_code=409, detail="The demo baseline is incomplete; no workflow state was reset.")

        submission_ids = [row[0] for row in db.query(Submission.submission_id).filter(Submission.case_id == case_id).all()]
        reports = db.query(Report).filter(Report.case_id == case_id).all()
        render_ids = [report.render_id for report in reports if report.render_id]

        if submission_ids:
            db.query(Acknowledgement).filter(Acknowledgement.submission_id.in_(submission_ids)).delete(synchronize_session=False)
            db.query(SubmissionAttempt).filter(
                SubmissionAttempt.original_submission_id.in_(submission_ids)
                | SubmissionAttempt.new_submission_id.in_(submission_ids)
            ).delete(synchronize_session=False)

        db.query(CaseWorkflowRecord).filter(CaseWorkflowRecord.case_id == case_id).delete(synchronize_session=False)
        db.query(Report).filter(Report.case_id == case_id).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.case_id == case_id).delete(synchronize_session=False)
        db.query(DeadlineEscalation).filter(DeadlineEscalation.case_id == case_id).delete(synchronize_session=False)

        case.status = case_state["status"]
        case.final_decision = case_state.get("final_decision")
        case.report_fields = case_state["report_fields"]
        case.provider = case_state["provider"]
        case.facility = case_state["facility"]
        case.deadline = _datetime_value(case_state.get("deadline"))
        case.severity = case_state.get("severity")
        case.warnings = case_state.get("warnings", [])
        if candidate is not None:
            candidate_state = baseline.candidate_state if isinstance(baseline.candidate_state, dict) else {}
            candidate.status = candidate_state.get("status") or "POTENTIAL"
            candidate.jurisdiction = candidate_state.get("jurisdiction")
            candidate.deadline = _datetime_value(candidate_state.get("deadline"))
            candidate.severity = candidate_state.get("severity")
            candidate.case_id = case_id

        # Move only report-linked render artifacts aside before commit. A DB failure
        # restores them; unrelated generated forms and the official template remain.
        staged_files = _stage_generated_pdfs(render_ids)
        db.commit()
    except HTTPException:
        db.rollback()
        _restore_staged_files(staged_files)
        raise
    except Exception as exc:
        db.rollback()
        _restore_staged_files(staged_files)
        raise HTTPException(status_code=500, detail="SIGNAL demo reset failed; all database changes were rolled back.") from exc

    cleanup_warning = False
    for _, staged_path in staged_files:
        try:
            staged_path.unlink(missing_ok=True)
        except OSError:
            cleanup_warning = True

    return {
        "success": True,
        "message": "SIGNAL demo reset successfully",
        "case_id": case_id,
        "patient_id": (case.patient or {}).get("patient_id"),
        "reset": {
            "case": True,
            "report_fields": True,
            "provider": True,
            "facility": True,
            "review": True,
            "attestation": True,
            "deadline": True,
            "notification": True,
            "submission": True,
            "candidate": candidate is not None,
            "generated_forms": True,
        },
        "generated_files_removed": len(staged_files) if not cleanup_warning else None,
        "generated_file_cleanup_warning": cleanup_warning,
        "current_workflow_state": {
            "validation": "PENDING",
            "review": "PENDING",
            "attestation": "PENDING",
            "reporting": "LOCKED",
        },
        "audit_history_preserved": True,
        "canonical_data_preserved": True,
    }
