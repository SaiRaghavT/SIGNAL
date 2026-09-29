from .models import SubmissionResult


def submit_ecr(ecr, validation) -> SubmissionResult:

    if not validation.valid:
        return SubmissionResult(
            submission_id=None,
            status="REJECTED",
            destination="MOCK_PHA",
            errors=validation.errors,
            warnings=validation.warnings,
        )

    if ecr.status == "HOLD":
        return SubmissionResult(
            submission_id=None,
            status="BLOCKED",
            destination="MOCK_PHA",
            errors=["ECR is on hold."],
            warnings=validation.warnings,
        )

    if ecr.status == "NEEDS_REVIEW":
        return SubmissionResult(
            submission_id=None,
            status="BLOCKED",
            destination="MOCK_PHA",
            errors=["ECR requires review before submission."],
            warnings=validation.warnings,
        )

    if ecr.status != "REPORT":
        return SubmissionResult(
            submission_id=None,
            status="BLOCKED",
            destination="MOCK_PHA",
            errors=["Only a REPORT ECR can be submitted."],
            warnings=validation.warnings,
        )

    return SubmissionResult(
        submission_id=f"SUB-{ecr.ecr_id}",
        status="SUBMITTED",
        destination="MOCK_PHA",
        errors=[],
        warnings=[
            "Submission is simulated; no real PHA transmission occurred."
        ],
    )
