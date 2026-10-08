from backend.app.ingestion.hl7.mapper import map_hl7_message
from backend.app.ingestion.hl7.parser import parse_hl7_message


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


def test_map_hl7_message():

    parsed = parse_hl7_message(SAMPLE_HL7)

    result = map_hl7_message(parsed)

    assert result["message_type"] == "ORU^R01"

    patient = result["patient"]

    assert patient["source_patient_id"] == "PAT001"
    assert patient["name"] == {"family": "PATIENT", "given": "SAMPLE"}
    assert patient["date_of_birth"].isoformat() == "1985-05-05"
    assert patient["sex"] == "M"
    assert patient["source"] == "hl7"
    assert patient["source_resource"] == "PID"


def test_map_encounter():

    parsed = parse_hl7_message(SAMPLE_HL7)

    result = map_hl7_message(parsed)

    encounter = result["encounter"]

    assert encounter is not None
    assert encounter["source_encounter_id"] == "hl7-encounter-PAT001"
    assert encounter["patient_id"] == "PAT001"
    assert encounter["encounter_type"] == "I"
    assert encounter["source"] == "hl7"


def test_map_observations():

    parsed = parse_hl7_message(SAMPLE_HL7)

    result = map_hl7_message(parsed)

    observations = result["observations"]

    assert len(observations) == 1

    observation = observations[0]

    assert observation["source_observation_id"] == "1"
    assert observation["observation_code"] == "TEST001"
    assert observation["observation_display"] == "Measles IgM"
    assert observation["observation_system"] == "LN"
    assert observation["value_numeric"] == 1.25
    assert observation["unit"] == "INDEX"
    assert observation["source"] == "hl7"


def test_map_lab_result():

    parsed = parse_hl7_message(SAMPLE_HL7)

    result = map_hl7_message(parsed)

    lab_result = result["lab_result"]

    assert lab_result is not None
    assert lab_result["source_lab_result_id"] == "ORDER001"
    assert lab_result["test_code"] == "13950-1"
    assert lab_result["test_display"] == "Measles IgM"
    assert lab_result["test_system"] == "LN"
    assert lab_result["source"] == "hl7"
    assert lab_result["source_resource"] == "OBR"
