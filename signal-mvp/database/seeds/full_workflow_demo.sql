-- Synthetic end-to-end SIGNAL measles workflow demo.
-- Paste into pgAdmin Query Tool and execute. Safe to rerun (fixed demo IDs).
-- This is fictional data. PHA submission and acknowledgement are simulated.
BEGIN;

INSERT INTO patients (
  patient_id, source_patient_id, first_name, last_name, date_of_birth, sex,
  address_line, city, county, state, postal_code, source, source_resource,
  created_at, updated_at
) VALUES (
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', 'SIGNAL-DEMO-MEASLES-001',
  'Jordan', 'Rivera', '2018-04-12', 'Female', '100 Demo Avenue', 'Austin',
  'Travis', 'TX', '78701', 'SIGNAL_DEMO', 'FHIR Patient',
  CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours', CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours'
) ON CONFLICT (patient_id) DO NOTHING;

INSERT INTO encounters (
  encounter_id, source_encounter_id, patient_id, facility_id, encounter_type,
  status, start_time, end_time, source, source_resource, created_at, updated_at
) VALUES (
  '70099710-f39f-5436-93ce-5c8a07e3716b', 'SIGNAL-DEMO-MEASLES-001-encounter',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', 'SIGNAL-DEMO-CLINIC', 'ambulatory',
  'finished', CURRENT_TIMESTAMP - INTERVAL '8 days', CURRENT_TIMESTAMP - INTERVAL '8 days',
  'SIGNAL_DEMO', 'FHIR Encounter',
  CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours', CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours'
) ON CONFLICT (encounter_id) DO UPDATE SET
  start_time = EXCLUDED.start_time,
  end_time = EXCLUDED.end_time,
  updated_at = EXCLUDED.updated_at;

-- Follow-up encounters: rash evaluation, then laboratory confirmation.
INSERT INTO encounters (
  encounter_id, source_encounter_id, patient_id, facility_id, encounter_type,
  status, start_time, end_time, source, source_resource, created_at, updated_at
) VALUES
(
  '4bcb7f35-ec26-5124-8eab-e9c084b8cf94', 'SIGNAL-DEMO-MEASLES-001-encounter-rash',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', 'SIGNAL-DEMO-URGENT-CARE', 'ambulatory',
  'finished', CURRENT_TIMESTAMP - INTERVAL '6 days', CURRENT_TIMESTAMP - INTERVAL '6 days',
  'SIGNAL_DEMO', 'FHIR Encounter', CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours', CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours'
),
(
  '2f0861e7-8a36-588c-b0a3-804deca9d95a', 'SIGNAL-DEMO-MEASLES-001-encounter-confirmation',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', 'SIGNAL-DEMO-CLINIC', 'ambulatory',
  'finished', CURRENT_TIMESTAMP - INTERVAL '5 days', CURRENT_TIMESTAMP - INTERVAL '5 days',
  'SIGNAL_DEMO', 'FHIR Encounter', CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours', CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours'
)
ON CONFLICT (encounter_id) DO NOTHING;

INSERT INTO conditions (
  condition_id, source_condition_id, patient_id, encounter_id, condition_code,
  condition_system, condition_display, clinical_status, verification_status,
  onset_time, recorded_time, source, source_resource
) VALUES (
  'c0a3a854-032c-5baa-96e4-26bb98fec10f', 'SIGNAL-DEMO-MEASLES-001-condition',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '2f0861e7-8a36-588c-b0a3-804deca9d95a',
  '14189004', 'http://snomed.info/sct', 'Measles', 'active', 'confirmed',
  CURRENT_TIMESTAMP - INTERVAL '8 days', CURRENT_TIMESTAMP - INTERVAL '5 days',
  'SIGNAL_DEMO', 'FHIR Condition'
) ON CONFLICT (condition_id) DO NOTHING;

INSERT INTO observations (
  observation_id, source_observation_id, patient_id, encounter_id, observation_code,
  observation_system, observation_display, status, value_text, effective_time,
  source, source_resource
) VALUES (
  '413fabbe-5c7b-5e0d-a7ab-469e12ef55a7', 'SIGNAL-DEMO-MEASLES-001-observation',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '2f0861e7-8a36-588c-b0a3-804deca9d95a',
  '48508-6', 'http://loinc.org',
  'Measles virus RNA [Presence] in Specimen by NAA with probe detection', 'final', 'Positive',
  CURRENT_TIMESTAMP - INTERVAL '6 days', 'SIGNAL_DEMO', 'FHIR Observation'
) ON CONFLICT (observation_id) DO NOTHING;

-- Synthetic vital signs from the initial and rash visits (temperature in Celsius).
INSERT INTO observations (
  observation_id, source_observation_id, patient_id, encounter_id, observation_code,
  observation_system, observation_display, status, value_text, effective_time,
  source, source_resource
) VALUES
('87e98054-a851-5025-8f00-701e7d5bf845','SIGNAL-DEMO-MEASLES-001-temp-initial','bb06202b-79bc-58c9-a8d6-be96e0775fdb','70099710-f39f-5436-93ce-5c8a07e3716b','8310-5','http://loinc.org','Body temperature','final','39.1 Cel',CURRENT_TIMESTAMP - INTERVAL '8 days','SIGNAL_DEMO','FHIR Observation'),
('1f42e261-f94b-50dc-a133-c691317a65f5','SIGNAL-DEMO-MEASLES-001-spo2-initial','bb06202b-79bc-58c9-a8d6-be96e0775fdb','70099710-f39f-5436-93ce-5c8a07e3716b','59408-5','http://loinc.org','Oxygen saturation in Arterial blood by Pulse oximetry','final','97 %',CURRENT_TIMESTAMP - INTERVAL '8 days','SIGNAL_DEMO','FHIR Observation'),
('cdf534cb-4a37-5f58-ae3d-97509b48a1e6','SIGNAL-DEMO-MEASLES-001-temp-rash','bb06202b-79bc-58c9-a8d6-be96e0775fdb','4bcb7f35-ec26-5124-8eab-e9c084b8cf94','8310-5','http://loinc.org','Body temperature','final','39.4 Cel',CURRENT_TIMESTAMP - INTERVAL '6 days','SIGNAL_DEMO','FHIR Observation'),
('9038c60c-d4d1-5844-90e7-b86c2c598a45','SIGNAL-DEMO-MEASLES-001-spo2-rash','bb06202b-79bc-58c9-a8d6-be96e0775fdb','4bcb7f35-ec26-5124-8eab-e9c084b8cf94','59408-5','http://loinc.org','Oxygen saturation in Arterial blood by Pulse oximetry','final','96 %',CURRENT_TIMESTAMP - INTERVAL '6 days','SIGNAL_DEMO','FHIR Observation')
ON CONFLICT (observation_id) DO NOTHING;

INSERT INTO lab_results (
  lab_result_id, source_lab_result_id, patient_id, encounter_id, test_code,
  test_system, test_display, report_status, category, effective_time, issued_time,
  conclusion, source, source_resource
) VALUES (
  'ccfc399b-4a06-56ca-882b-8c1e9cf81f12', 'SIGNAL-DEMO-MEASLES-001-lab',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '2f0861e7-8a36-588c-b0a3-804deca9d95a',
  '48508-6', 'http://loinc.org',
  'Measles virus RNA [Presence] in Specimen by NAA with probe detection', 'final', 'virology',
  CURRENT_TIMESTAMP - INTERVAL '6 days', CURRENT_TIMESTAMP - INTERVAL '5 days',
  'Positive', 'SIGNAL_DEMO', 'FHIR DiagnosticReport'
) ON CONFLICT (lab_result_id) DO NOTHING;

INSERT INTO lab_result_observations (lab_result_id, observation_id) VALUES (
  'ccfc399b-4a06-56ca-882b-8c1e9cf81f12', '413fabbe-5c7b-5e0d-a7ab-469e12ef55a7'
) ON CONFLICT DO NOTHING;

INSERT INTO clinical_documents (
  document_id, source_document_id, patient_id, encounter_id, document_type,
  document_status, title, document_date, content_type, extracted_text,
  source, source_resource
) VALUES (
  '13ca358c-139b-54c9-8dc7-41cce51af724', 'SIGNAL-DEMO-MEASLES-001-document',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '2f0861e7-8a36-588c-b0a3-804deca9d95a',
  'clinical-note', 'final', 'Synthetic measles confirmation note', CURRENT_TIMESTAMP - INTERVAL '5 days',
  'text/plain', 'Synthetic demo confirmation visit: respiratory specimen collected during rash evaluation returned positive for measles virus RNA by nucleic acid amplification. Result reviewed with caregiver by phone; public health notification workflow initiated. Caregiver advised to continue home isolation and follow local public health instructions. No hospitalization documented.',
  'SIGNAL_DEMO', 'FHIR DocumentReference'
) ON CONFLICT (document_id) DO UPDATE SET
  encounter_id = EXCLUDED.encounter_id,
  title = EXCLUDED.title,
  document_date = EXCLUDED.document_date,
  extracted_text = EXCLUDED.extracted_text;

-- Clinical notes at each encounter give the case a readable progression.
INSERT INTO clinical_documents (
  document_id, source_document_id, patient_id, encounter_id, document_type,
  document_status, title, document_date, content_type, extracted_text,
  source, source_resource
) VALUES
(
  '4e25bbe8-e0fd-5d22-896f-865415eee1c1', 'SIGNAL-DEMO-MEASLES-001-document-initial',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '70099710-f39f-5436-93ce-5c8a07e3716b',
  'clinical-note', 'final', 'Synthetic initial illness note', CURRENT_TIMESTAMP - INTERVAL '8 days',
  'text/plain', 'Synthetic demo initial visit (day 1 of illness): caregiver reports fever beginning this morning with cough, nasal congestion, and reduced appetite. No rash reported. No known measles contact reported; exposure history and immunization record are not available in this synthetic fixture. Temperature 39.1 C, pulse oximetry 97% on room air. Child alert, drinking fluids, and without documented respiratory distress. Measles considered in the differential because of the symptom pattern. Supportive care discussed, return precautions reviewed, and follow-up advised if rash develops or symptoms worsen.',
  'SIGNAL_DEMO', 'FHIR DocumentReference'
),
(
  '6aad9562-003a-528c-9536-94ec616058a9', 'SIGNAL-DEMO-MEASLES-001-document-rash',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '4bcb7f35-ec26-5124-8eab-e9c084b8cf94',
  'clinical-note', 'final', 'Synthetic rash evaluation note', CURRENT_TIMESTAMP - INTERVAL '6 days',
  'text/plain', 'Synthetic demo rash evaluation (approximately day 3 of illness): fever persists at 39.4 C with cough, coryza, and bilateral conjunctival injection. Blanching maculopapular rash began near the hairline and face yesterday and is now visible on the upper trunk. Pulse oximetry 96% on room air; no respiratory distress documented. Caregiver reports no known exposure; immunization history remains unknown. Suspected measles discussed. Clinic used source control and separated the patient from the general waiting area; staff followed facility airborne-precaution procedure. Respiratory specimen collected for measles rRT-PCR and public health consultation/notification initiated. Caregiver given instructions to call ahead before seeking in-person care, minimize contact with others, and follow public health guidance. Emergency return precautions reviewed.',
  'SIGNAL_DEMO', 'FHIR DocumentReference'
)
ON CONFLICT (document_id) DO NOTHING;

INSERT INTO candidates (
  candidate_id, detection_key, patient_id, encounter_id, disease_id, jurisdiction,
  case_id, detection_source, confidence, evidence, signals, status, deadline, severity,
  created_at, updated_at
) VALUES (
  'demo-measles-candidate-001', 'signal-demo-measles-001-detection',
  'bb06202b-79bc-58c9-a8d6-be96e0775fdb', '2f0861e7-8a36-588c-b0a3-804deca9d95a',
  'measles', 'TX', '47c36049-c05c-5cd0-9636-e870a6457597', 'SIGNAL_DEMO', 0.98,
  '[{"source":"FHIR Condition","code":"14189004"},{"source":"FHIR DiagnosticReport","result":"Positive"}]'::jsonb,
  '["MEASLES_CONDITION","POSITIVE_MEASLES_PCR"]'::jsonb, 'CASE_CREATED',
  CURRENT_TIMESTAMP + INTERVAL '24 hours', 'HIGH',
  CURRENT_TIMESTAMP - INTERVAL '3 days 1 hour 45 minutes', CURRENT_TIMESTAMP - INTERVAL '3 days 1 hour 45 minutes'
) ON CONFLICT (candidate_id) DO NOTHING;

INSERT INTO cases (
  case_id, candidate_id, patient, facility, provider, disease, clinical_evidence,
  laboratory_evidence, ai_evidence, report_fields, jurisdiction, jurisdiction_status,
  reportability_decision, reportability_evidence_status, status, final_decision,
  rule_id, deadline, severity, warnings, created_at, updated_at
) VALUES (
  '47c36049-c05c-5cd0-9636-e870a6457597', 'demo-measles-candidate-001',
  $$ {"patient_id":"bb06202b-79bc-58c9-a8d6-be96e0775fdb","first_name":"Jordan","last_name":"Rivera","name":"Jordan Rivera","date_of_birth":"2018-04-12","sex":"Female","address":{"line":"100 Demo Avenue"},"city":"Austin","county":"Travis","state":"TX","postal_code":"78701","country_of_residence":"United States","hispanic":"Unknown","race":"Unknown","phone":"512-555-0100"} $$::jsonb,
  $$ {"name":"SIGNAL Demonstration Clinic","address":"200 Sample Street, Austin, TX 78701"} $$::jsonb,
  $$ {"name":"Taylor Morgan, MD","phone":"512-555-0199","address":"200 Sample Street, Austin, TX 78701"} $$::jsonb,
  'measles',
  $$ {"onset_date":"2026-09-28","diagnosis_date":"2026-10-01","illness_onset_date":"2026-09-28","diagnosis":"Measles","confirmation_method":"Laboratory confirmed","hospitalized":"No","icu_admission":"No","admission_date":"Not applicable","discharge_date":"Not applicable","rash":"Yes","rash_onset_date":"2026-09-30","rash_duration":"2 days","rash_location":"Face and trunk","fever":"Yes","fever_onset_date":"2026-09-28","highest_temperature":"39.1 C","cough":"Yes","coryza":"Yes","conjunctivitis":"Yes","koplik_spots":"Unknown"} $$::jsonb,
  $$ [{"test":"Measles virus RNA [Presence] in Specimen by NAA with probe detection","code":"48508-6","code_system":"http://loinc.org","result":"POSITIVE"}] $$::jsonb,
  $$ {"assessment":"Clinical and laboratory evidence are consistent with measles.","confidence":0.98,"human_review_required":true} $$::jsonb,
  $$ {"patient.case_name":"Jordan Rivera","patient.parent_guardian_name":"Alex Rivera (synthetic)","patient.current_address":"100 Demo Avenue","patient.city":"Austin","patient.county":"Travis","patient.zip":"78701","patient.phone":"512-555-0100","patient.date_of_birth":"2018-04-12","patient.sex":"Female","patient.country_of_residence":"United States","patient.hispanic":"Unknown","patient.race":"Unknown","reporting.reported_by":"Taylor Morgan, MD","reporting.email":"demo@signal.local","reporting.phone":"512-555-0199","reporting.agency":"SIGNAL Demonstration Clinic","reporting.earliest_date_reported":"2026-10-01","clinical.hospitalized":"No","clinical.icu_admission":"No","clinical.admission_date":"Not applicable","clinical.discharge_date":"Not applicable","clinical.hospital":"SIGNAL Demonstration Clinic","clinical.illness_onset_date":"2026-09-28","clinical.confirmation_method":"Laboratory confirmed","clinical.diagnosis":"Measles","clinical.diagnosis_date":"2026-10-01","rash_fever.rash":"Yes","rash_fever.rash_onset_date":"2026-09-30","rash_fever.rash_duration":"2 days","rash_fever.rash_location":"Face and trunk","rash_fever.fever":"Yes","rash_fever.fever_onset_date":"2026-09-28","rash_fever.highest_temperature":"39.1 C","rash_fever.cough":"Yes","rash_fever.coryza":"Yes","rash_fever.conjunctivitis":"Yes","rash_fever.koplik_spots":"Unknown","laboratory.pcr":"Positive","laboratory.culture":"Not performed","laboratory.igm":"Positive","laboratory.igg":"Pending"} $$::jsonb,
  'TX', 'RESOLVED', 'REPORT', 'LAB_CONFIRMED', 'REPORT', 'REPORT',
  'TX-MEASLES-IMMEDIATE', CURRENT_TIMESTAMP + INTERVAL '24 hours', 'HIGH',
  '["Synthetic demonstration record; not a real patient or public-health submission."]'::jsonb,
  CURRENT_TIMESTAMP - INTERVAL '3 days 1 hour 30 minutes', CURRENT_TIMESTAMP - INTERVAL '10 minutes'
) ON CONFLICT (case_id) DO NOTHING;

-- Keep flat demo report fields consistent with the relative encounter
-- timeline, even when this seed is rerun on a later date.
UPDATE cases
SET clinical_evidence = clinical_evidence || jsonb_build_object(
      'onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'illness_onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'rash_onset_date', to_char(CURRENT_DATE - 6, 'YYYY-MM-DD'),
      'diagnosis_date', to_char(CURRENT_DATE - 5, 'YYYY-MM-DD'),
      'rash_duration', 'Approximately 1 day at last documentation',
      'highest_temperature', '39.4 C'
    ),
    report_fields = report_fields || jsonb_build_object(
      'clinical.illness_onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'clinical.diagnosis_date', to_char(CURRENT_DATE - 5, 'YYYY-MM-DD'),
      'reporting.earliest_date_reported', to_char(CURRENT_DATE - 5, 'YYYY-MM-DD'),
      'rash_fever.fever_onset_date', to_char(CURRENT_DATE - 8, 'YYYY-MM-DD'),
      'rash_fever.rash_onset_date', to_char(CURRENT_DATE - 6, 'YYYY-MM-DD'),
      'rash_fever.rash_duration', 'Approximately 1 day at last documentation',
      'rash_fever.highest_temperature', '39.4 C',
      'laboratory.igm', 'Not documented',
      'laboratory.igg', 'Not documented'
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE case_id = '47c36049-c05c-5cd0-9636-e870a6457597';

INSERT INTO audit_events (
  audit_id, entity_type, entity_id, event_type, actor_type, actor_id, source_agent,
  status, description, new_value, metadata, event_timestamp
) VALUES
('SIGNAL-DEMO-MEASLES-001:DATA_INGESTION','CASE','47c36049-c05c-5cd0-9636-e870a6457597','DEMO_FHIR_DATA_LOADED','SYSTEM','SIGNAL_DEMO','synthetic FHIR fixture','SUCCESS','Synthetic demonstration: data ingestion stage.','{"source":"SIGNAL_DEMO","resources":["Patient","Encounter","Condition","Observation","DiagnosticReport","DocumentReference"],"synthetic":true}'::jsonb,'{"workflow_stage":"DATA_INGESTION","synthetic_demo":true}'::jsonb,CURRENT_TIMESTAMP - INTERVAL '3 days 2 hours'),
('SIGNAL-DEMO-MEASLES-001:DETECTION','CASE','47c36049-c05c-5cd0-9636-e870a6457597','DEMO_CANDIDATE_DETECTED','SYSTEM','SIGNAL_DEMO','Structured trigger detection','SUCCESS','Synthetic demonstration: detection stage.','{"candidate_id":"demo-measles-candidate-001","signals":["MEASLES_CONDITION","POSITIVE_MEASLES_PCR"],"confidence":0.98,"synthetic":true}'::jsonb,'{"workflow_stage":"DETECTION","synthetic_demo":true}'::jsonb,CURRENT_TIMESTAMP - INTERVAL '3 days 1 hour 50 minutes'),
('SIGNAL-DEMO-MEASLES-001:REPORTABILITY','CASE','47c36049-c05c-5cd0-9636-e870a6457597','DEMO_REPORTABILITY_DECIDED','SYSTEM','SIGNAL_DEMO','Reportability workflow','SUCCESS','Synthetic demonstration: reportability stage.','{"decision":"REPORT","rule_id":"TX-MEASLES-IMMEDIATE","jurisdiction":"TX","synthetic":true}'::jsonb,'{"workflow_stage":"REPORTABILITY","synthetic_demo":true}'::jsonb,CURRENT_TIMESTAMP - INTERVAL '3 days 1 hour 40 minutes'),
('SIGNAL-DEMO-MEASLES-001:REPORTING','CASE','47c36049-c05c-5cd0-9636-e870a6457597','CASE_MANUAL_REPORT_PREPARED','SYSTEM','SIGNAL_DEMO','SIGNAL report preparation','SUCCESS','Synthetic demonstration: reporting stage.','{"status":"READY_FOR_RENDERING","form_id":"TX_MEASLES_OUTBREAK_CRF_2025","synthetic":true}'::jsonb,'{"workflow_stage":"REPORTING","synthetic_demo":true}'::jsonb,CURRENT_TIMESTAMP - INTERVAL '30 minutes'),
('SIGNAL-DEMO-MEASLES-001:CASE_ATTESTED','CASE','47c36049-c05c-5cd0-9636-e870a6457597','CASE_ATTESTED','USER','demo-reviewer','attestation_control','SUCCESS','Synthetic demo attestation recorded.','{"reviewer_id":"demo-reviewer","reviewer_role":"Public Health Reviewer","attestation_status":"ATTESTED","comments":"Synthetic demo attestation; no real submission."}'::jsonb,'{"workflow_stage":"ATTESTATION","synthetic_demo":true}'::jsonb,CURRENT_TIMESTAMP - INTERVAL '15 minutes')
ON CONFLICT (audit_id) DO NOTHING;

INSERT INTO case_workflow_records (record_id, case_id, record_type, status, actor_id, payload) VALUES
('SIGNAL-DEMO-MEASLES-001:VALIDATION','47c36049-c05c-5cd0-9636-e870a6457597','VALIDATION','VALID','SIGNAL_DEMO','{"valid":true,"errors":[],"completion_required":[],"warnings":[],"synthetic_demo":true}'::jsonb),
('SIGNAL-DEMO-MEASLES-001:REVIEW','47c36049-c05c-5cd0-9636-e870a6457597','REVIEW','APPROVE','demo-reviewer','{"reviewer_id":"demo-reviewer","reviewer_role":"Public Health Reviewer","decision":"APPROVE","comments":"Synthetic demo case reviewed."}'::jsonb),
('SIGNAL-DEMO-MEASLES-001:ATTESTATION','47c36049-c05c-5cd0-9636-e870a6457597','ATTESTATION','ATTESTED','demo-reviewer','{"reviewer_id":"demo-reviewer","reviewer_role":"Public Health Reviewer","attestation_status":"ATTESTED","comments":"Synthetic demo attestation; no real submission."}'::jsonb)
ON CONFLICT (record_id) DO NOTHING;

INSERT INTO reports (
  report_id, case_id, form_id, form_version, render_id, report_type, disease,
  jurisdiction, validation, attestation, status
) VALUES (
  'SIGNAL-DEMO-MEASLES-001:report', '47c36049-c05c-5cd0-9636-e870a6457597',
  'TX_MEASLES_OUTBREAK_CRF_2025', '2025-05-07', 'DEMO-RENDER-001',
  'TEXAS_MEASLES', 'measles', 'TX',
  '{"valid":true,"errors":[],"completion_required":[],"warnings":[],"synthetic_demo":true}'::jsonb,
  '{"reviewer_id":"demo-reviewer","reviewer_role":"Public Health Reviewer","attestation_status":"ATTESTED","comments":"Synthetic demo attestation; no real submission."}'::jsonb,
  'GENERATED'
) ON CONFLICT (report_id) DO NOTHING;

INSERT INTO submissions (
  submission_id, case_id, report_id, channel, ecr_id, destination, status,
  errors, warnings, ecr_payload, acknowledgement_id, pha_case_id
) VALUES (
  'SUB-SIGNAL-DEMO-MEASLES-001', '47c36049-c05c-5cd0-9636-e870a6457597',
  'SIGNAL-DEMO-MEASLES-001:report', 'eCR',
  'ECR-47c36049-c05c-5cd0-9636-e870a6457597', 'MOCK_PHA', 'ACKNOWLEDGED', '[]'::jsonb,
  '["Synthetic demo acknowledgement; no real PHA transmission occurred."]'::jsonb,
  '{"demo":true,"case_id":"47c36049-c05c-5cd0-9636-e870a6457597","disease":"measles","jurisdiction":"TX"}'::jsonb,
  'ACK-SIGNAL-DEMO-MEASLES-001', 'PHA-SIGNAL-DEMO-MEASLES-001'
) ON CONFLICT (submission_id) DO NOTHING;

INSERT INTO acknowledgements (
  acknowledgement_id, submission_id, pha_id, status, response, errors
) VALUES (
  'ACK-SIGNAL-DEMO-MEASLES-001', 'SUB-SIGNAL-DEMO-MEASLES-001',
  'PHA-SIGNAL-DEMO-MEASLES-001', 'ACKNOWLEDGED',
  '{"simulated":true,"status":"ACKNOWLEDGED","synthetic_demo":true}'::jsonb, '[]'::jsonb
) ON CONFLICT (acknowledgement_id) DO NOTHING;

INSERT INTO follow_ups (
  followup_id, case_id, action, status, notes, submission_id, patient_id,
  disease, next_action, due_date
) VALUES (
  'FOLLOWUP-SIGNAL-DEMO-MEASLES-001', '47c36049-c05c-5cd0-9636-e870a6457597',
  'ACKNOWLEDGEMENT_REVIEW', 'CLOSED',
  'Synthetic demo: mock acknowledgement reviewed and follow-up closed.',
  'SUB-SIGNAL-DEMO-MEASLES-001', 'bb06202b-79bc-58c9-a8d6-be96e0775fdb',
  'measles', 'No further demo action.', CURRENT_TIMESTAMP - INTERVAL '5 minutes'
) ON CONFLICT (followup_id) DO NOTHING;

COMMIT;

-- Confirm the row was inserted. The case journey endpoint should show all stages:
-- /api/workflow/cases/47c36049-c05c-5cd0-9636-e870a6457597/journey
SELECT case_id, disease, jurisdiction, status, final_decision
FROM cases
WHERE case_id = '47c36049-c05c-5cd0-9636-e870a6457597';
