areimport pytest

from backend.app.ingestion.hl7.parser import (
    parse_hl7_message,
)
from backend.app.ingestion.hl7.validator import (
    validate_hl7_data_quality,
)


VALID_HL7 = (
    "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
    "202609281200||ORU^R01|MSG00001|P|2.5.1\r"
    "PID|1||PAT-QUALITY-001^^^HOSPITAL||"
    "DOE^JOHN||19900101|M\r"
    "PV1|1|I|ER^01^01||||"
    "12345^SMITH^JANE\r"
    "ORC|RE|ORDER-QUALITY-001\r"
    "OBR|1|ORDER-QUALITY-001|LAB-QUALITY-001|"
    "13950-1^Measles IgM^LN\r"
    "OBX|1|NM|TEST001^Measles IgM^LN|"
    "1|1.25|INDEX||||F"
)


def test_valid_hl7_passes_quality_gate():

    parsed = parse_hl7_message(
        VALID_HL7
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "passed"
    assert result["error_count"] == 0


def test_missing_pid_fails():

    message = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG00002|P|2.5.1\r"
        "PV1|1|I|ER^01^01"
    )

    parsed = parse_hl7_message(
        message
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "failed"
    assert result["error_count"] >= 1

    assert any(
        issue["code"] == "HL7_MISSING_PID"
        for issue in result["issues"]
    )


def test_missing_patient_id_fails():

    message = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG00003|P|2.5.1\r"
        "PID|1||||DOE^JOHN||19900101|M"
    )

    parsed = parse_hl7_message(
        message
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "failed"

    assert any(
        issue["code"] == "HL7_MISSING_PATIENT_ID"
        for issue in result["issues"]
    )


def test_invalid_patient_dob_fails():

    message = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG00004|P|2.5.1\r"
        "PID|1||PAT-QUALITY-004^^^HOSPITAL||"
        "DOE^JOHN||20261399|M"
    )

    parsed = parse_hl7_message(
        message
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "failed"

    assert any(
        issue["code"] == "HL7_INVALID_PATIENT_DOB"
        for issue in result["issues"]
    )


def test_missing_obx_identifier_fails():

    message = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG00005|P|2.5.1\r"
        "PID|1||PAT-QUALITY-005^^^HOSPITAL||"
        "DOE^JOHN||19900101|M\r"
        "OBX|1|NM||1|1.25|INDEX||||F"
    )

    parsed = parse_hl7_message(
        message
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "failed"

    assert any(
        issue["code"] == "HL7_MISSING_OBX_IDENTIFIER"
        for issue in result["issues"]
    )


def test_missing_obx_value_is_warning():

    message = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG00006|P|2.5.1\r"
        "PID|1||PAT-QUALITY-006^^^HOSPITAL||"
        "DOE^JOHN||19900101|M\r"
        "OBX|1|NM|TEST001^Measles IgM^LN||||||||F"
    )

    parsed = parse_hl7_message(
        message
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "passed"
    assert result["error_count"] == 0
    assert result["warning_count"] >= 1

    assert any(
        issue["code"] == "HL7_MISSING_OBX_VALUE"
        for issue in result["issues"]
    )


def test_missing_obr_test_fails():

    message = (
        "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
        "202609281200||ORU^R01|MSG00007|P|2.5.1\r"
        "PID|1||PAT-QUALITY-007^^^HOSPITAL||"
        "DOE^JOHN||19900101|M\r"
        "OBR|1|ORDER-QUALITY-007|LAB-QUALITY-007|"
    )

    parsed = parse_hl7_message(
        message
    )

    result = validate_hl7_data_quality(
        parsed
    )

    assert result["status"] == "failed"

    assert any(
        issue["code"] == "HL7_MISSING_OBR_TEST"
        for issue in result["issues"]
    )