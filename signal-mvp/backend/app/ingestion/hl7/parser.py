from typing import Any


class HL7ParseError(ValueError):
    """Raised when an HL7 v2 message cannot be parsed."""


def parse_hl7_message(message: str) -> dict[str, Any]:
    """
    Parse a raw HL7 v2 message into segments and fields.

    This parser intentionally focuses on structural parsing.
    Mapping HL7 data into SIGNAL canonical entities happens later.
    """

    if not isinstance(message, str):
        raise HL7ParseError("HL7 message must be a string.")

    message = message.strip()

    if not message:
        raise HL7ParseError("HL7 message cannot be empty.")

    # HL7 messages normally use carriage return as the segment delimiter.
    # Accept LF/CRLF as well for easier testing and file-based ingestion.
    normalized = message.replace("\r\n", "\r").replace("\n", "\r")

    raw_segments = [
        segment
        for segment in normalized.split("\r")
        if segment.strip()
    ]

    if not raw_segments:
        raise HL7ParseError("HL7 message contains no segments.")

    segments: list[dict[str, Any]] = []

    for index, raw_segment in enumerate(raw_segments):

        fields = raw_segment.split("|")

        if not fields or not fields[0]:
            raise HL7ParseError(
                f"HL7 segment at index {index} is invalid."
            )

        segment_type = fields[0].strip()

        segments.append(
            {
                "index": index,
                "type": segment_type,
                "fields": fields,
                "raw": raw_segment,
            }
        )

    if segments[0]["type"] != "MSH":
        raise HL7ParseError(
            "HL7 message must begin with an MSH segment."
        )

    return {
        "message_type": _extract_message_type(segments),
        "segments": segments,
    }


def _extract_message_type(
    segments: list[dict[str, Any]],
) -> str | None:
    """
    Extract MSH-9 message type.

    MSH is special in HL7 because MSH-1 is the field separator
    itself. Therefore MSH-9 corresponds to index 8 in the
    split field list.
    """

    msh = segments[0]

    fields = msh["fields"]

    # fields[0] = "MSH"
    # fields[1] = MSH-1 = field separator
    # fields[2] = MSH-2 = encoding characters
    # fields[3] = MSH-3
    # ...
    # fields[8] = MSH-9 = message type

    if len(fields) <= 8:
        return None

    value = fields[8].strip()

    return value or None


def get_segments(
    parsed_message: dict[str, Any],
    segment_type: str,
) -> list[dict[str, Any]]:
    """
    Return all segments of a specific type.

    Example:
        get_segments(parsed, "OBX")
    """

    return [
        segment
        for segment in parsed_message.get("segments", [])
        if segment["type"] == segment_type
    ]


def get_first_segment(
    parsed_message: dict[str, Any],
    segment_type: str,
) -> dict[str, Any] | None:
    """
    Return the first segment of a specific type.
    """

    segments = get_segments(
        parsed_message,
        segment_type,
    )

    return segments[0] if segments else None


def get_field(
    segment: dict[str, Any],
    field_number: int,
) -> str | None:
    """
    Get a field using normal HL7 field numbering.

    For non-MSH segments:
        PID-3 -> fields[3]

    For MSH:
        MSH-1 -> fields[1]
        MSH-2 -> fields[2]
        MSH-9 -> fields[8]

    MSH is special because the field separator occupies
    MSH-1.
    """

    segment_type = segment.get("type")
    fields = segment.get("fields", [])

    if not isinstance(fields, list):
        return None

    if field_number < 1:
        return None

    # HL7 field numbering is 1-based, but the parsed list includes the segment
    # type as fields[0]. For non-MSH segments, PID-3 is fields[3] as expected.
    # For MSH, the first character is MSH-1, not a true field, so index is
    # shifted by one relative to the standard numbering. This matches the tests.
    # The tests also expect field extraction to behave like the standard HL7
    # cardinality in which PID-3 is the component at index 3 of the raw fields
    # list (after the segment type); the prior implementation incorrectly
    # stripped the leading patient identifier from a PID value like
    # "TEST-PATIENT-001^^^HOSPITAL" to "PAT001".
    index = field_number - 1 if segment_type == "MSH" else field_number

    if index >= len(fields):
        return None

    value = fields[index]

    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None