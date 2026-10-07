-- Correct the already-loaded synthetic measles case in place.
-- Run in pgAdmin Query Tool. This does not submit or transmit anything.
BEGIN;

UPDATE cases
SET clinical_evidence = clinical_evidence || jsonb_build_object(
      'onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'illness_onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'rash_onset_date', to_char(CURRENT_DATE - 6, 'YYYY-MM-DD'),
      'diagnosis_date', to_char(CURRENT_DATE - 5, 'YYYY-MM-DD'),
      'rash_duration', 'Approximately 1 day at last documentation',
      'highest_temperature', '39.4 C'
    ),
    laboratory_evidence = jsonb_build_array(
      jsonb_build_object(
        'test', 'Measles virus RNA [Presence] in Specimen by NAA with probe detection',
        'code', '48508-6',
        'code_system', 'http://loinc.org',
        'result', 'POSITIVE'
      )
    ),
    report_fields = report_fields || jsonb_build_object(
      'clinical.illness_onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'clinical.diagnosis_date', to_char(CURRENT_DATE - 5, 'YYYY-MM-DD'),
      'reporting.earliest_date_reported', to_char(CURRENT_DATE - 5, 'YYYY-MM-DD'),
      'rash_fever.fever_onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'rash_fever.rash_onset_date', to_char(CURRENT_DATE - 6, 'YYYY-MM-DD'),
      'rash_fever.highest_temperature', '39.4 C',
      'rash_fever.rash_duration', 'Approximately 1 day at last documentation',
      'laboratory.igm', 'Not documented',
      'laboratory.igg', 'Not documented'
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE case_id = '47c36049-c05c-5cd0-9636-e870a6457597'
  AND patient->>'patient_id' = 'bb06202b-79bc-58c9-a8d6-be96e0775fdb';

COMMIT;

SELECT case_id, clinical_evidence, laboratory_evidence, report_fields
FROM cases
WHERE case_id = '47c36049-c05c-5cd0-9636-e870a6457597';
