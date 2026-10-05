TEXAS_MEASLES_FORM = {
    "form_id": "TX_MEASLES_OUTBREAK_CRF_2025",
    "form_version": "2025-05-07",
    "disease": "measles",
    "jurisdiction": "TX",
    "fields": [
        # Page 1 — Case / Patient
        {
            "field": "patient.case_name",
            "source": "patient.name",
            "required": True,
        },
        {
            "field": "patient.parent_guardian_name",
            "source": "patient.parent_guardian_name",
            "required": False,
        },
        {
            "field": "patient.current_address",
            "source": "patient.address",
            "required": True,
        },
        {
            "field": "patient.city",
            "source": "patient.city",
            "required": True,
        },
        {
            "field": "patient.county",
            "source": "patient.county",
            "required": True,
        },
        {
            "field": "patient.zip",
            "source": "patient.zip",
            "required": True,
        },
        {
            "field": "patient.phone",
            "source": "patient.phone",
            "required": False,
        },
        {
            "field": "patient.date_of_birth",
            "source": "patient.date_of_birth",
            "required": True,
        },
        {
            "field": "patient.age",
            "source": "patient.age",
            "required": False,
        },
        {
            "field": "patient.sex",
            "source": "patient.sex",
            "required": True,
        },
        {
            "field": "patient.country_of_residence",
            "source": "patient.country_of_residence",
            "required": True,
        },
        {
            "field": "patient.hispanic",
            "source": "patient.hispanic",
            "required": True,
        },
        {
            "field": "patient.race",
            "source": "patient.race",
            "required": True,
        },

        # Page 1 — Reporting / Investigation
        {
            "field": "reporting.reported_by",
            "source": "reporting.reported_by",
            "required": True,
        },
        {
            "field": "reporting.email",
            "source": "reporting.email",
            "required": True,
        },
        {
            "field": "reporting.phone",
            "source": "reporting.phone",
            "required": True,
        },
        {
            "field": "reporting.agency",
            "source": "reporting.agency",
            "required": False,
        },
        {
            "field": "reporting.earliest_date_reported",
            "source": "reporting.earliest_date_reported",
            "required": True,
        },

        # Page 1 — Clinical / Hospitalization
        {
            "field": "clinical.hospitalized",
            "source": "clinical.hospitalized",
            "required": True,
        },
        {
            "field": "clinical.icu_admission",
            "source": "clinical.icu_admission",
            "required": False,
        },
        {
            "field": "clinical.admission_date",
            "source": "clinical.admission_date",
            "required": True,
        },
        {
            "field": "clinical.discharge_date",
            "source": "clinical.discharge_date",
            "required": True,
        },
        {
            "field": "clinical.hospital",
            "source": "facility.name",
            "required": True,
        },
        {
            "field": "clinical.illness_onset_date",
            "source": "clinical.onset_date",
            "required": True,
        },
        {
            "field": "clinical.confirmation_method",
            "source": "clinical.confirmation_method",
            "required": False,
        },
        {
            "field": "clinical.diagnosis",
            "source": "disease",
            "required": False,
        },
        {
            "field": "clinical.diagnosis_date",
            "source": "clinical.diagnosis_date",
            "required": True,
        },

        # Page 2 — Rash / Fever
        {
            "field": "rash_fever.rash",
            "source": "clinical.rash",
            "required": True,
        },
        {
            "field": "rash_fever.rash_onset_date",
            "source": "clinical.rash_onset_date",
            "required": False,
        },
        {
            "field": "rash_fever.rash_duration",
            "source": "clinical.rash_duration",
            "required": False,
        },
        {
            "field": "rash_fever.rash_location",
            "source": "clinical.rash_location",
            "required": True,
        },
        {
            "field": "rash_fever.fever",
            "source": "clinical.fever",
            "required": True,
        },
        {
            "field": "rash_fever.fever_onset_date",
            "source": "clinical.fever_onset_date",
            "required": False,
        },
        {
            "field": "rash_fever.highest_temperature",
            "source": "clinical.highest_temperature",
            "required": False,
        },
        {
            "field": "rash_fever.cough",
            "source": "clinical.cough",
            "required": True,
        },
        {
            "field": "rash_fever.coryza",
            "source": "clinical.coryza",
            "required": True,
        },
        {
            "field": "rash_fever.conjunctivitis",
            "source": "clinical.conjunctivitis",
            "required": True,
        },
        {
            "field": "rash_fever.koplik_spots",
            "source": "clinical.koplik_spots",
            "required": False,
        },

        # Page 2 — Laboratory
        {
            "field": "laboratory.pcr",
            "source": "laboratory.pcr",
            "required": False,
        },
        {
            "field": "laboratory.culture",
            "source": "laboratory.culture",
            "required": False,
        },
        {
            "field": "laboratory.igm",
            "source": "laboratory.igm",
            "required": True,
        },
        {
            "field": "laboratory.igg",
            "source": "laboratory.igg",
            "required": True,
        },
    ],
}