"""Mappings from SIGNAL report-data paths to the Texas PDF widget names."""

PDF_FIELD_MAP = {
    "patient.last_name": "Last Name",
    "patient.first_name": "First Name",
    "patient.current_address": "Patient Current Street Address",
    "patient.address": "Patient Current Street Address",
    "patient.city": "Patient Current City",
    "patient.county": "Patient Current County",
    "patient.zip": "Patient Current Zip Code",
    "patient.phone": "Patient Home Phone",
    "patient.parent_guardian_name": "Parent or Guardian",
    "patient.date_of_birth": "Patient DOB_af_date",
    "patient.age": "Patient Age",
    "patient.cell_phone": "Patient Cell Phone",
    "patient.permanent_address": "Patient Permanent Street Address",
    "patient.permanent_city": "Patient Permanent City",
    "patient.permanent_county": "Patient Permanent County",
    "patient.permanent_zip": "Patient Permanent Zip Code",
    "patient.occupation": "Occupation",
    "patient.place_of_birth": "Other place of birth",
    "patient.other_country_of_residence": "Other country of residence",
    "patient.other_race": "Other race",
    "patient.race_other": "Other race",
    "patient.estimated_case_due_date": "ESTIMATED_CASE_DUE_DATE",
    "case.nbs_patient_id": "NBS Patient ID",
    "case.nbs_investigation_id": "NBS Investigation ID",
    "provider.name": "Physician",
    "provider.phone": "Physician Phone",
    "provider.address": "Physician Address",
    "facility.name": "Hospital",
    "facility.delivery_hospital": "Case delivery hospital",
    "facility.unit": "Hospital unit",
    "patient.region": "Region",
    "reporting.reported_by": "Reported by",
    "reporting.email": "Reporting Agency email",
    "reporting.phone": "Reporting Agency Phone",
    "reporting.agency": "Reporting Agency",
    "reporting.earliest_date_reported": "Earliest date reported to county_af_date",
    "reporting.investigated_by": "Investigated by",
    "reporting.investigating_agency": "Investigating Agency",
    "reporting.investigating_agency_phone": "Investigating Agency Phone",
    "reporting.investigating_agency_email": "Investigating agency email",
    "reporting.investigation_start_date": "Investigation start date_af_date",
    "reporting.investigation_completed_date": "Investigation completed date_af_date",
    "clinical.hospital": "Hospital",
    "clinical.death_cause": "DEATH_CAUSE",
    "clinical.death_date": "DEATH_DATE",
    "clinical.duration_of_stay": "Duration of stay",
    "clinical.illness_onset_date": "Illness onset date_af_date",
    "clinical.onset_date": "Illness onset date_af_date",
    "clinical.diagnosis": "Diagnosis",
    "clinical.diagnosis_date": "Diagnosis date_af_date",
    "clinical.admission_date": "Hospital admit date_af_date",
    "clinical.discharge_date": "Hospital discharge date_af_date",
    "rash_fever.rash_onset_date": "RASH_ONSET_DATE",
    "rash_fever.rash_duration": "Rash duration",
    "rash_fever.rash_location": "Other rash location describe",
    "rash_fever.fever_onset_date": "FEVER_ONSET_DATE",
    "rash_fever.highest_temperature": "Highest temp",
    "laboratory.pcr": "PCR result",
    "laboratory.culture": "Culture result",
    "laboratory.igm": "IgM result",
    "laboratory.igg": "IgG result",
}

# Values map to the exact non-Off appearance state in the source PDF. Checkbox
# groups that represent multiple independent selections are mapped separately.
PDF_CHECKBOX_MAP = {
    "clinical.case_status": {"pdf_field": "CASE_STATUS", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N",
        "true": "Y", "false": "N", "confirmed": "Y",
        "ruled out": "N", "ruled out/not a case": "N",
    }},
    "clinical.outcome": {"pdf_field": "OUTCOME", "values": {
        "survived": "Survived", "alive": "Survived", "unknown": "Unknown",
        "died": "Died", "deceased": "Died",
    }},
    "case.update_to_existing": {"pdf_field": "UPDATE_TO_EXISTING", "values": {
        "yes": "Y", "y": "Y", "true": "Y", "no": "N", "n": "N",
        "false": "N", "unknown": "U", "u": "U",
    }},
    "patient.is_minor": {"pdf_field": "MINOR", "values": {
        "yes": "1", "true": "1", "1": "1",
    }},
    "patient.permanent_address_is_current": {"pdf_field": "IS_PERMANENT_ADDRESS", "values": {
        "yes": "1", "true": "1", "1": "1",
    }},
    "patient.homeless": {"pdf_field": "HOMELESSNESS", "values": {
        "yes": "Y", "true": "Y", "1": "Y",
    }},
    "patient.infant_age_group": {"pdf_field": "INFANT", "values": {
        "0-6 months": "0-6 months", "0 to 6 months": "0-6 months",
        "7-11 months": "7-11 months", "7 to 11 months": "7-11 months",
        "no": "N", "false": "N",
    }},
    "patient.sex": {"pdf_field": "SEX", "values": {
        "male": "M", "m": "M", "female": "F", "f": "F",
        "unknown": "U", "u": "U", "unspecified": "U",
    }},
    "patient.country_of_residence": {"pdf_field": "COUNTRY_OF_RESIDENCE", "values": {
        "usa": "USA", "us": "USA", "united states": "USA",
        "other": "Other", "unknown": "U", "u": "U",
    }},
    "patient.birthplace": {"pdf_field": "BIRTHPLACE", "values": {
        "usa": "USA", "us": "USA", "united states": "USA",
        "other": "Other", "unknown": "U", "u": "U",
    }},
    "patient.pregnant": {"pdf_field": "PREGNANT", "values": {
        "yes": "Y", "y": "Y", "true": "Y", "no": "N", "n": "N",
        "false": "N", "unknown": "U", "u": "U", "not applicable": "N/A",
        "n/a": "N/A",
    }},
    "patient.hispanic": {"pdf_field": "HISPANIC", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N", "unknown": "U", "u": "U",
    }},
    "clinical.hospitalized": {"pdf_field": "INPT_ADMIT", "values": {
        "yes": "Yes", "y": "Yes", "true": "Yes", "inpatient": "Yes",
        "no": "No", "n": "No", "false": "No", "outpatient": "No",
        "unknown": "Unknown", "er only": "ER Only", "er": "ER Only",
        "urgent care": "Urgent Care",
    }},
    "clinical.icu_admission": {"pdf_field": "ICU_ADMIT", "values": {
        "yes": "Yes", "y": "Yes", "true": "Yes", "no": "No", "n": "No",
        "false": "No", "unknown": "Unknown", "u": "Unknown",
    }},
    "clinical.confirmation_method": {"pdf_field": "CONFIRMATION", "values": {
        "lab confirmed": "Lab Confirmed", "laboratory confirmed": "Lab Confirmed",
        "epi-linked": "Epi-Linked", "epidemiologically linked": "Epi-Linked",
    }},
    "rash_fever.rash": {"pdf_field": "RASH", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N", "unknown": "U", "u": "U",
    }},
    "rash_fever.fever": {"pdf_field": "FEVER", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N", "unknown": "3", "u": "3",
    }},
    "rash_fever.cough": {"pdf_field": "COUGH", "values": {
        "yes": "1", "y": "1", "no": "2", "n": "2", "unknown": "U", "u": "U",
    }},
    "rash_fever.coryza": {"pdf_field": "CORYZA", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N", "unknown": "U", "u": "U",
    }},
    "rash_fever.conjunctivitis": {"pdf_field": "CONJUNCTIVITIS", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N", "unknown": "U", "u": "U",
    }},
    "rash_fever.koplik_spots": {"pdf_field": "KOPLIKS", "values": {
        "yes": "Y", "y": "Y", "no": "N", "n": "N", "unknown": "U", "u": "U",
    }},
    "clinical.still_inpatient": {"pdf_field": "STILL_INPT", "values": {
        "yes": "Yes", "true": "Yes", "1": "Yes",
    }},
}

# The source form presents races as independent checkboxes. This lookup maps
# actual reported race labels to those PDF fields without selecting defaults.
PDF_MULTI_CHECKBOX_MAP = {
    "patient.race": {
        "white": "RACE_WHITE", "black or african american": "RACE_BLACK",
        "black": "RACE_BLACK", "asian": "RACE_ASIAN",
        "american indian or alaska native": "RACE_AI_AN",
        "native hawaiian or other pacific islander": "RACE_HAWAIIAN_PAC_ISLAND",
        "unknown": "RACE_UNKNOWN", "other": "RACE_OTHER",
    },
}
