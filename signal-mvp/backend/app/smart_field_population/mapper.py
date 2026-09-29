from backend.app.smart_field_population.models import SmartFieldResult


def populate_report_fields(candidate: dict) -> SmartFieldResult:

    fields = {}
    populated_fields = []
    missing_fields = []
    warnings = []

    patient = candidate.get("patient") or {}
    provider = candidate.get("provider") or {}
    facility = candidate.get("facility") or {}
    clinical = candidate.get("clinical_evidence") or {}
    labs = candidate.get("laboratory_evidence") or []

    # Patient fields
    patient_mapping = {
        "patient.first_name": patient.get("first_name"),
        "patient.last_name": patient.get("last_name"),
        "patient.date_of_birth": patient.get("dob") or patient.get("date_of_birth"),
        "patient.address": patient.get("address"),
        "patient.city": patient.get("city"),
        "patient.state": patient.get("state"),
        "patient.zip": patient.get("zip"),
    }

    # Provider fields
    provider_mapping = {
        "provider.name": provider.get("name"),
        "provider.phone": provider.get("phone"),
    }

    # Facility fields
    facility_mapping = {
        "facility.name": facility.get("name"),
        "facility.state": facility.get("state"),
        "facility.city": facility.get("city"),
    }

    # Clinical fields
    clinical_mapping = {
        "clinical.symptoms": clinical.get("symptoms"),
        "clinical.onset_date": clinical.get("onset_date"),
    }

    all_mappings = {
        **patient_mapping,
        **provider_mapping,
        **facility_mapping,
        **clinical_mapping,
    }

    for field_name, value in all_mappings.items():

        if value is not None and value != "":
            fields[field_name] = value
            populated_fields.append(field_name)
        else:
            missing_fields.append(field_name)

    # Laboratory fields
    if labs:
        fields["laboratory"] = labs
        populated_fields.append("laboratory")
    else:
        missing_fields.append("laboratory")

    if missing_fields:
        warnings.append(
            f"{len(missing_fields)} report fields could not be populated."
        )

    return SmartFieldResult(
        fields=fields,
        populated_fields=populated_fields,
        missing_fields=missing_fields,
        warnings=warnings,
    )