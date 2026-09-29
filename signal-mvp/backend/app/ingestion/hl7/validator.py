from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.app.ingestion.hl7.parser import (
    get_field,
    get_first_segment,
    get_segments,
)


@dataclass
class HL7QualityIssue:
    severity: str
    code: str
    message: str
    segment: str | None = None
    field: str | None = None


def _is_valid_hl7_datetime(
    value: str | None,
) -> bool:
    """
    Validate common HL7 date/time formats.

    Supported:
        YYYYMMDD
        YYYYMMDDHHMM
        YYYYMMDDHHMMSS
    """

    if not value:
        return True

    value = value.strip()

    formats = (
        ("%Y%m%d%H%M%S", 14),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    )

    for fmt, length in formats:
        if len(value) < length:
            continue

        try:
            datetime.strptime(
                value[:length],
                fmt,
            )
            return True
        except ValueError:
            continue

    return False


def _add_error(
    issues: list[HL7QualityIssue],
    code: str,
    message: str,
    segment: str | None = None,
    field: str | None = None,
) -> None:
    issues.append(
        HL7QualityIssue(
            severity="error",
            code=code,
            message=message,
            segment=segment,
            field=field,
        )
    )


def _add_warning(
    issues: list[HL7QualityIssue],
    code: str,
    message: str,
    segment: str | None = None,
    field: str | None = None,
) -> None:
    issues.append(
        HL7QualityIssue(
            severity="warning",
            code=code,
            message=message,
            segment=segment,
            field=field,
        )
    )


def validate_hl7_data_quality(
    parsed_message: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate a parsed HL7 message before canonical mapping
    and PostgreSQL persistence.

    Returns:

        {
            "status": "passed" | "failed",
            "error_count": int,
            "warning_count": int,
            "issue_count": int,
            "issues": [...]
        }
    """

    issues: list[HL7QualityIssue] = []

    segments = parsed_message.get(
        "segments",
        [],
    )

    # --------------------------------------------------
    # 1. Basic parsed-message structure
    # --------------------------------------------------

    if not segments:
        _add_error(
            issues,
            code="HL7_EMPTY_MESSAGE",
            message="HL7 message contains no segments.",
        )

    # --------------------------------------------------
    # 2. MSH validation
    # --------------------------------------------------

    msh = get_first_segment(
        parsed_message,
        "MSH",
    )

    if msh is None:
        _add_error(
            issues,
            code="HL7_MISSING_MSH",
            message="HL7 message is missing the MSH segment.",
            segment="MSH",
        )
    else:
        message_type = get_field(
            msh,
            9,
        )

        if not message_type:
            _add_error(
                issues,
                code="HL7_MISSING_MESSAGE_TYPE",
                message="MSH-9 message type is missing.",
                segment="MSH",
                field="MSH-9",
            )

    # --------------------------------------------------
    # 3. PID validation
    # --------------------------------------------------

    pid = get_first_segment(
        parsed_message,
        "PID",
    )

    if pid is None:
        _add_error(
            issues,
            code="HL7_MISSING_PID",
            message="HL7 message is missing the PID segment.",
            segment="PID",
        )
    else:

        patient_identifier = get_field(
            pid,
            3,
        )

        if not patient_identifier:
            _add_error(
                issues,
                code="HL7_MISSING_PATIENT_ID",
                message="PID-3 patient identifier is missing.",
                segment="PID",
                field="PID-3",
            )

        date_of_birth = get_field(
            pid,
            7,
        )

        if date_of_birth and not _is_valid_hl7_datetime(
            date_of_birth
        ):
            _add_error(
                issues,
                code="HL7_INVALID_PATIENT_DOB",
                message=(
                    "PID-7 contains an invalid HL7 "
                    "date/time value."
                ),
                segment="PID",
                field="PID-7",
            )

        sex = get_field(
            pid,
            8,
        )

        if not sex:
            _add_warning(
                issues,
                code="HL7_MISSING_PATIENT_SEX",
                message="PID-8 administrative sex is missing.",
                segment="PID",
                field="PID-8",
            )

    # --------------------------------------------------
    # 4. PV1 validation
    # --------------------------------------------------

    pv1 = get_first_segment(
        parsed_message,
        "PV1",
    )

    if pv1 is not None:

        patient_class = get_field(
            pv1,
            2,
        )

        if not patient_class:
            _add_warning(
                issues,
                code="HL7_MISSING_PATIENT_CLASS",
                message="PV1-2 patient class is missing.",
                segment="PV1",
                field="PV1-2",
            )

    # --------------------------------------------------
    # 5. OBR validation
    # --------------------------------------------------

    obr_segments = get_segments(
        parsed_message,
        "OBR",
    )

    for index, obr in enumerate(
        obr_segments,
        start=1,
    ):

        test_identifier = get_field(
            obr,
            4,
        )

        if not test_identifier:
            _add_error(
                issues,
                code="HL7_MISSING_OBR_TEST",
                message=(
                    f"OBR segment {index} is missing "
                    "OBR-4 universal service identifier."
                ),
                segment="OBR",
                field="OBR-4",
            )

        observation_date = get_field(
            obr,
            7,
        )

        if observation_date and not _is_valid_hl7_datetime(
            observation_date
        ):
            _add_error(
                issues,
                code="HL7_INVALID_OBR_DATE",
                message=(
                    f"OBR segment {index} contains "
                    "an invalid OBR-7 observation date/time."
                ),
                segment="OBR",
                field="OBR-7",
            )

    # --------------------------------------------------
    # 6. OBX validation
    # --------------------------------------------------

    obx_segments = get_segments(
        parsed_message,
        "OBX",
    )

    for index, obx in enumerate(
        obx_segments,
        start=1,
    ):

        observation_identifier = get_field(
            obx,
            3,
        )

        if not observation_identifier:
            _add_error(
                issues,
                code="HL7_MISSING_OBX_IDENTIFIER",
                message=(
                    f"OBX segment {index} is missing "
                    "OBX-3 observation identifier."
                ),
                segment="OBX",
                field="OBX-3",
            )

        value_type = get_field(
            obx,
            2,
        )

        if not value_type:
            _add_error(
                issues,
                code="HL7_MISSING_OBX_VALUE_TYPE",
                message=(
                    f"OBX segment {index} is missing "
                    "OBX-2 value type."
                ),
                segment="OBX",
                field="OBX-2",
            )

        value = get_field(
            obx,
            5,
        )

        if not value:
            _add_warning(
                issues,
                code="HL7_MISSING_OBX_VALUE",
                message=(
                    f"OBX segment {index} does not contain "
                    "an observation value."
                ),
                segment="OBX",
                field="OBX-5",
            )

        effective_time = get_field(
            obx,
            14,
        )

        if effective_time and not _is_valid_hl7_datetime(
            effective_time
        ):
            _add_error(
                issues,
                code="HL7_INVALID_OBX_DATE",
                message=(
                    f"OBX segment {index} contains "
                    "an invalid OBX-14 observation date/time."
                ),
                segment="OBX",
                field="OBX-14",
            )

    # --------------------------------------------------
    # 7. General segment validation
    # --------------------------------------------------

    for index, segment in enumerate(
        segments
    ):

        segment_type = segment.get(
            "type"
        )

        raw = segment.get(
            "raw"
        )

        if not segment_type:
            _add_error(
                issues,
                code="HL7_INVALID_SEGMENT_TYPE",
                message=(
                    f"Segment at index {index} "
                    "does not contain a segment type."
                ),
            )

        if not raw or "|" not in raw:
            _add_error(
                issues,
                code="HL7_INVALID_SEGMENT_FORMAT",
                message=(
                    f"Segment at index {index} "
                    "does not contain the HL7 field separator."
                ),
                segment=segment_type,
            )

    # --------------------------------------------------
    # 8. Result
    # --------------------------------------------------

    error_count = sum(
        1
        for issue in issues
        if issue.severity == "error"
    )

    warning_count = sum(
        1
        for issue in issues
        if issue.severity == "warning"
    )

    serialized_issues = [
        {
            "severity": issue.severity,
            "code": issue.code,
            "message": issue.message,
            "segment": issue.segment,
            "field": issue.field,
        }
        for issue in issues
    ]

    return {
        "status": (
            "failed"
            if error_count > 0
            else "passed"
        ),
        "error_count": error_count,
        "warning_count": warning_count,
        "issue_count": len(issues),
        "issues": serialized_issues,
    }