import pytest

from backend.app.ingestion.hl7.parser import (
    HL7ParseError,
    get_field,
    get_first_segment,
    get_segments,
    parse_hl7_message,
)


SAMPLE_HL7 = (
    "MSH|^~\\&|SENDER|HOSPITAL|RECEIVER|PHA|"
    "202609281200||ORU^R01|MSG00001|P|2.5.1\r"
    "PID|1||TEST-PATIENT-001^^^HOSPITAL||PATIENT^SAMPLE||"
    "19850505|M\r"
    "PV1|1|I|ER^01^01||||12345^SMITH^JANE\r"
    "ORC|RE|ORDER001\r"
    "OBR|1|ORDER001|LAB001|"
    "13950-1^Measles IgM^LN\r"
    "OBX|1|NM|TEST001^Measles IgM^LN|"
    "1|1.25|INDEX||||F"
)


def test_parse_hl7_message():

    parsed = parse_hl7_message(SAMPLE_HL7)

    assert parsed["message_type"] == "ORU^R01"

    assert len(parsed["segments"]) == 6


def test_get_segments():

    parsed = parse_hl7_message(SAMPLE_HL7)

    obx_segments = get_segments(
        parsed,
        "OBX",
    )

    assert len(obx_segments) == 1
    assert obx_segments[0]["type"] == "OBX"


def test_get_first_segment():

    parsed = parse_hl7_message(SAMPLE_HL7)

    pid = get_first_segment(
        parsed,
        "PID",
    )

    assert pid is not None
    assert pid["type"] == "PID"


def test_get_field():

    parsed = parse_hl7_message(SAMPLE_HL7)

    pid = get_first_segment(
        parsed,
        "PID",
    )

    assert pid is not None

    assert get_field(pid, 3) == "PAT001^^^HOSPITAL"
    assert get_field(pid, 8) == "M"


def test_invalid_empty_message():

    with pytest.raises(HL7ParseError):
        parse_hl7_message("")


def test_invalid_message_without_msh():

    with pytest.raises(HL7ParseError):
        parse_hl7_message(
            "PID|1||PAT001\r"
            "PV1|1|I"
        )


def test_lf_delimited_message():

    message = SAMPLE_HL7.replace("\r", "\n")

    parsed = parse_hl7_message(message)

    assert parsed["message_type"] == "ORU^R01"
    assert len(parsed["segments"]) == 6
