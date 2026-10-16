-- Synthetic end-to-end SIGNAL demo data.
-- Uses canonical tables, Texas 2026 rule-catalog disease labels, and
-- SNOMED/LOINC codes found in the eRSD v3.2 RCTC expansions.
-- Safe to run repeatedly: all records use stable IDs and source keys.
BEGIN;

INSERT INTO patients (
    patient_id, source_patient_id, first_name, last_name, date_of_birth, sex,
    address_line, city, county, state, postal_code, source, source_resource
) VALUES
('e2000000-0000-4000-8000-000000000001', 'SIGNAL-E2E-2026-001', 'Ava', 'Martinez', '2018-07-21', 'Female', '1201 Red River St', 'Austin', 'Travis', 'TX', '78701', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000002', 'SIGNAL-E2E-2026-002', 'Noah', 'Williams', '2026-05-10', 'Male', '4500 Main St', 'Houston', 'Harris', 'TX', '77002', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000003', 'SIGNAL-E2E-2026-003', 'Priya', 'Shah', '2004-03-11', 'Female', '800 Commerce St', 'Dallas', 'Dallas', 'TX', '75201', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000004', 'SIGNAL-E2E-2026-004', 'Mateo', 'Garcia', '2021-10-28', 'Male', '310 W Houston St', 'San Antonio', 'Bexar', 'TX', '78205', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000005', 'SIGNAL-E2E-2026-005', 'Linh', 'Nguyen', '1982-04-14', 'Female', '900 N Stanton St', 'El Paso', 'El Paso', 'TX', '79902', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000006', 'SIGNAL-E2E-2026-006', 'Carlos', 'Davis', '1995-08-03', 'Male', '700 Shoreline Blvd', 'Corpus Christi', 'Nueces', 'TX', '78401', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000007', 'SIGNAL-E2E-2026-007', 'Elijah', 'Brown', '2010-11-02', 'Male', '1500 S Main St', 'Fort Worth', 'Tarrant', 'TX', '76104', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000008', 'SIGNAL-E2E-2026-008', 'Grace', 'Thompson', '1959-06-19', 'Female', '1000 Herring Ave', 'Waco', 'McLennan', 'TX', '76708', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000009', 'SIGNAL-E2E-2026-009', 'Amina', 'Patel', '1997-02-20', 'Female', '2601 19th St', 'Lubbock', 'Lubbock', 'TX', '79410', 'signal_e2e_demo_2026', 'Patient'),
('e2000000-0000-4000-8000-000000000010', 'SIGNAL-E2E-2026-010', 'Robert', 'King', '1974-05-30', 'Male', '110 W Ferguson St', 'Tyler', 'Smith', 'TX', '75702', 'signal_e2e_demo_2026', 'Patient')
ON CONFLICT (source, source_patient_id) DO NOTHING;

INSERT INTO encounters (
    encounter_id, source_encounter_id, patient_id, facility_id, encounter_type,
    status, start_time, end_time, source, source_resource
) VALUES
('e2100000-0000-4000-8000-000000000001', 'SIGNAL-E2E-ENC-001', 'e2000000-0000-4000-8000-000000000001', 'DEMO-AUSTIN-CHILDRENS', 'Emergency', 'finished', '2026-10-06 09:15:00-05', '2026-10-06 12:40:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000002', 'SIGNAL-E2E-ENC-002', 'e2000000-0000-4000-8000-000000000002', 'DEMO-HOUSTON-PEDIATRICS', 'Pediatric urgent care', 'finished', '2026-10-07 08:20:00-05', '2026-10-07 10:05:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000003', 'SIGNAL-E2E-ENC-003', 'e2000000-0000-4000-8000-000000000003', 'DEMO-DALLAS-STUDENT-HEALTH', 'Outpatient', 'finished', '2026-10-05 13:10:00-05', '2026-10-05 14:00:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000004', 'SIGNAL-E2E-ENC-004', 'e2000000-0000-4000-8000-000000000004', 'DEMO-SANANTONIO-PEDIATRICS', 'Outpatient', 'finished', '2026-10-04 11:00:00-05', '2026-10-04 11:50:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000005', 'SIGNAL-E2E-ENC-005', 'e2000000-0000-4000-8000-000000000005', 'DEMO-ELPASO-RESPIRATORY', 'Pulmonary clinic', 'finished', '2026-10-01 08:00:00-06', '2026-10-01 09:30:00-06', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000006', 'SIGNAL-E2E-ENC-006', 'e2000000-0000-4000-8000-000000000006', 'DEMO-CORPUS-URGENT-CARE', 'Emergency', 'finished', '2026-10-02 17:25:00-05', '2026-10-02 20:15:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000007', 'SIGNAL-E2E-ENC-007', 'e2000000-0000-4000-8000-000000000007', 'DEMO-FORTWORTH-CHILDRENS', 'Emergency', 'finished', '2026-10-08 06:40:00-05', '2026-10-08 09:30:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000008', 'SIGNAL-E2E-ENC-008', 'e2000000-0000-4000-8000-000000000008', 'DEMO-WACO-MEDICAL', 'Inpatient', 'in-progress', '2026-10-03 19:05:00-05', NULL, 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000009', 'SIGNAL-E2E-ENC-009', 'e2000000-0000-4000-8000-000000000009', 'DEMO-LUBBOCK-GI', 'Outpatient', 'finished', '2026-10-06 15:45:00-05', '2026-10-06 16:30:00-05', 'signal_e2e_demo_2026', 'Encounter'),
('e2100000-0000-4000-8000-000000000010', 'SIGNAL-E2E-ENC-010', 'e2000000-0000-4000-8000-000000000010', 'DEMO-TYLER-PRIMARY-CARE', 'Outpatient', 'finished', '2026-10-07 10:30:00-05', '2026-10-07 11:20:00-05', 'signal_e2e_demo_2026', 'Encounter')
ON CONFLICT (source, source_encounter_id) DO NOTHING;

-- Each condition code is the eRSD SNOMED focus concept and is included in
-- the eRSD dxtc-3.2.0 (diagnosis/problem) trigger group.
INSERT INTO conditions (
    condition_id, source_condition_id, patient_id, encounter_id,
    condition_code, condition_system, condition_display, clinical_status,
    verification_status, onset_time, recorded_time, source, source_resource
) VALUES
('e2200000-0000-4000-8000-000000000001', 'SIGNAL-E2E-COND-001', 'e2000000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000001', '14189004', 'http://snomed.info/sct', 'Measles (rubeola)', 'active', 'confirmed', '2026-10-05 00:00:00-05', '2026-10-06 09:30:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000002', 'SIGNAL-E2E-COND-002', 'e2000000-0000-4000-8000-000000000002', 'e2100000-0000-4000-8000-000000000002', '27836007', 'http://snomed.info/sct', 'Pertussis', 'active', 'confirmed', '2026-10-03 00:00:00-05', '2026-10-07 08:40:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000003', 'SIGNAL-E2E-COND-003', 'e2000000-0000-4000-8000-000000000003', 'e2100000-0000-4000-8000-000000000003', '36989005', 'http://snomed.info/sct', 'Mumps', 'active', 'confirmed', '2026-10-03 00:00:00-05', '2026-10-05 13:20:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000004', 'SIGNAL-E2E-COND-004', 'e2000000-0000-4000-8000-000000000004', 'e2100000-0000-4000-8000-000000000004', '38907003', 'http://snomed.info/sct', 'Chickenpox (varicella)', 'active', 'confirmed', '2026-10-02 00:00:00-05', '2026-10-04 11:10:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000005', 'SIGNAL-E2E-COND-005', 'e2000000-0000-4000-8000-000000000005', 'e2100000-0000-4000-8000-000000000005', '56717001', 'http://snomed.info/sct', 'Tuberculosis (Mycobacterium tuberculosis complex)', 'active', 'confirmed', '2026-09-28 00:00:00-06', '2026-10-01 08:15:00-06', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000006', 'SIGNAL-E2E-COND-006', 'e2000000-0000-4000-8000-000000000006', 'e2100000-0000-4000-8000-000000000006', '302231008', 'http://snomed.info/sct', 'Salmonellosis, including typhoid fever', 'active', 'confirmed', '2026-09-30 00:00:00-05', '2026-10-02 17:40:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000007', 'SIGNAL-E2E-COND-007', 'e2000000-0000-4000-8000-000000000007', 'e2100000-0000-4000-8000-000000000007', '23511006', 'http://snomed.info/sct', 'Meningococcal infection, invasive (Neisseria meningitidis)', 'active', 'confirmed', '2026-10-08 04:00:00-05', '2026-10-08 07:00:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000008', 'SIGNAL-E2E-COND-008', 'e2000000-0000-4000-8000-000000000008', 'e2100000-0000-4000-8000-000000000008', '26726000', 'http://snomed.info/sct', 'Legionellosis', 'active', 'confirmed', '2026-10-01 00:00:00-05', '2026-10-03 20:00:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000009', 'SIGNAL-E2E-COND-009', 'e2000000-0000-4000-8000-000000000009', 'e2100000-0000-4000-8000-000000000009', '36188001', 'http://snomed.info/sct', 'Shigellosis', 'active', 'confirmed', '2026-10-04 00:00:00-05', '2026-10-06 15:55:00-05', 'signal_e2e_demo_2026', 'Condition'),
('e2200000-0000-4000-8000-000000000010', 'SIGNAL-E2E-COND-010', 'e2000000-0000-4000-8000-000000000010', 'e2100000-0000-4000-8000-000000000010', '23502006', 'http://snomed.info/sct', 'Lyme disease', 'active', 'confirmed', '2026-10-02 00:00:00-05', '2026-10-07 10:40:00-05', 'signal_e2e_demo_2026', 'Condition')
ON CONFLICT (source, source_condition_id) DO NOTHING;

-- Positive synthetic laboratory results. Every LOINC code below is in an
-- eRSD lrtc-3.2.0 lab-result trigger ValueSet for the corresponding focus.
INSERT INTO lab_results (
    lab_result_id, source_lab_result_id, patient_id, encounter_id,
    test_code, test_system, test_display, report_status, category,
    effective_time, issued_time, performer_reference, conclusion,
    source, source_resource
) VALUES
('e2300000-0000-4000-8000-000000000001', 'SIGNAL-E2E-LAB-001', 'e2000000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000001', '48508-6', 'http://loinc.org', 'Measles virus RNA [Presence] in Specimen by NAA with probe detection', 'final', 'LAB', '2026-10-06 11:40:00-05', '2026-10-06 12:05:00-05', 'Organization/DEMO-AUSTIN-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000002', 'SIGNAL-E2E-LAB-002', 'e2000000-0000-4000-8000-000000000002', 'e2100000-0000-4000-8000-000000000002', '23826-1', 'http://loinc.org', 'Bordetella pertussis DNA [Presence] in Specimen by NAA with probe detection', 'final', 'LAB', '2026-10-07 09:10:00-05', '2026-10-07 09:35:00-05', 'Organization/DEMO-HOUSTON-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000003', 'SIGNAL-E2E-LAB-003', 'e2000000-0000-4000-8000-000000000003', 'e2100000-0000-4000-8000-000000000003', '47532-7', 'http://loinc.org', 'Mumps virus RNA [Presence] in Specimen by NAA with probe detection', 'final', 'LAB', '2026-10-05 13:35:00-05', '2026-10-05 14:10:00-05', 'Organization/DEMO-DALLAS-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000004', 'SIGNAL-E2E-LAB-004', 'e2000000-0000-4000-8000-000000000004', 'e2100000-0000-4000-8000-000000000004', '11483-5', 'http://loinc.org', 'Varicella zoster virus DNA [Presence] in Specimen by NAA with probe detection', 'final', 'LAB', '2026-10-04 11:25:00-05', '2026-10-04 12:00:00-05', 'Organization/DEMO-SANANTONIO-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000005', 'SIGNAL-E2E-LAB-005', 'e2000000-0000-4000-8000-000000000005', 'e2100000-0000-4000-8000-000000000005', '13956-8', 'http://loinc.org', 'Mycobacterium tuberculosis DNA [Presence] in Specimen by NAA with probe detection', 'final', 'LAB', '2026-10-01 08:50:00-06', '2026-10-01 10:30:00-06', 'Organization/DEMO-ELPASO-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000006', 'SIGNAL-E2E-LAB-006', 'e2000000-0000-4000-8000-000000000006', 'e2100000-0000-4000-8000-000000000006', '105913-8', 'http://loinc.org', 'Salmonella enterica+bongori DNA [Presence] in Specimen', 'final', 'LAB', '2026-10-02 18:30:00-05', '2026-10-02 19:05:00-05', 'Organization/DEMO-CORPUS-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000007', 'SIGNAL-E2E-LAB-007', 'e2000000-0000-4000-8000-000000000007', 'e2100000-0000-4000-8000-000000000007', '86581-6', 'http://loinc.org', 'Neisseria meningitidis [Presence] in Cerebral spinal fluid by Organism specific culture', 'final', 'LAB', '2026-10-08 08:15:00-05', '2026-10-08 09:05:00-05', 'Organization/DEMO-FORTWORTH-LAB', 'Isolated. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000008', 'SIGNAL-E2E-LAB-008', 'e2000000-0000-4000-8000-000000000008', 'e2100000-0000-4000-8000-000000000008', '17058-9', 'http://loinc.org', 'Legionella pneumophila Ag [Presence] in Urine by Latex agglutination', 'final', 'LAB', '2026-10-03 21:15:00-05', '2026-10-03 21:40:00-05', 'Organization/DEMO-WACO-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000009', 'SIGNAL-E2E-LAB-009', 'e2000000-0000-4000-8000-000000000009', 'e2100000-0000-4000-8000-000000000009', '70242-3', 'http://loinc.org', 'Shigella species+EIEC invasion plasmid antigen H ipaH gene [Presence] in Stool by NAA with probe detection', 'final', 'LAB', '2026-10-06 16:05:00-05', '2026-10-06 16:35:00-05', 'Organization/DEMO-LUBBOCK-LAB', 'Detected. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport'),
('e2300000-0000-4000-8000-000000000010', 'SIGNAL-E2E-LAB-010', 'e2000000-0000-4000-8000-000000000010', 'e2100000-0000-4000-8000-000000000010', '101357-2', 'http://loinc.org', 'Borrelia burgdorferi.VlsE+OspC IgG+IgM Ab [Presence] in Serum by Immunoassay', 'final', 'LAB', '2026-10-07 10:45:00-05', '2026-10-07 11:15:00-05', 'Organization/DEMO-TYLER-LAB', 'Positive. Synthetic demo result.', 'signal_e2e_demo_2026', 'DiagnosticReport')
ON CONFLICT (source, source_lab_result_id) DO NOTHING;

-- Note text is synthetic and gives document intelligence additional context.
INSERT INTO clinical_documents (
    document_id, source_document_id, patient_id, encounter_id, document_type,
    document_status, title, document_date, author_reference, content_type,
    extracted_text, source, source_resource
) VALUES
('e2400000-0000-4000-8000-000000000001', 'SIGNAL-E2E-NOTE-001', 'e2000000-0000-4000-8000-000000000001', 'e2100000-0000-4000-8000-000000000001', 'clinical-note', 'final', 'A. Martinez - febrile rash evaluation', '2026-10-06 12:15:00-05', 'Practitioner/DEMO-001', 'text/plain', 'SYNTHETIC DEMO NOTE. Eight-year-old with fever, cough, coryza, and a spreading maculopapular rash after a known school exposure. Exam documents conjunctival injection and Koplik spots. Measles (rubeola) is confirmed by a positive measles virus RNA PCR. Airborne precautions initiated; public health notification is indicated.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000002', 'SIGNAL-E2E-NOTE-002', 'e2000000-0000-4000-8000-000000000002', 'e2100000-0000-4000-8000-000000000002', 'clinical-note', 'final', 'N. Williams - infant cough evaluation', '2026-10-07 09:45:00-05', 'Practitioner/DEMO-002', 'text/plain', 'SYNTHETIC DEMO NOTE. Five-month-old with ten days of worsening paroxysmal cough, post-tussive emesis, and brief apnea. Household contact has a prolonged cough. Nasopharyngeal Bordetella pertussis PCR is positive. Pertussis is confirmed; supportive care and contact precautions discussed.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000003', 'SIGNAL-E2E-NOTE-003', 'e2000000-0000-4000-8000-000000000003', 'e2100000-0000-4000-8000-000000000003', 'clinical-note', 'final', 'P. Shah - parotitis evaluation', '2026-10-05 14:15:00-05', 'Practitioner/DEMO-003', 'text/plain', 'SYNTHETIC DEMO NOTE. Twenty-two-year-old college student with two days of fever, headache, and painful bilateral parotid swelling. No airway compromise. Buccal specimen mumps virus RNA PCR is positive. Mumps is confirmed; isolation guidance and campus exposure follow-up reviewed.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000004', 'SIGNAL-E2E-NOTE-004', 'e2000000-0000-4000-8000-000000000004', 'e2100000-0000-4000-8000-000000000004', 'clinical-note', 'final', 'M. Garcia - vesicular rash evaluation', '2026-10-04 12:10:00-05', 'Practitioner/DEMO-004', 'text/plain', 'SYNTHETIC DEMO NOTE. Four-year-old with low-grade fever and intensely pruritic vesicles in crops at different stages over the trunk and scalp. Lesion swab varicella zoster virus PCR is positive. Chickenpox (varicella) is confirmed; family given home isolation and return precautions.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000005', 'SIGNAL-E2E-NOTE-005', 'e2000000-0000-4000-8000-000000000005', 'e2100000-0000-4000-8000-000000000005', 'clinical-note', 'final', 'L. Nguyen - chronic cough and weight loss', '2026-10-01 10:45:00-06', 'Practitioner/DEMO-005', 'text/plain', 'SYNTHETIC DEMO NOTE. Forty-four-year-old with eight weeks of cough, night sweats, fatigue, and unintentional weight loss. Chest imaging shows a right upper-lobe cavitary opacity. Sputum Mycobacterium tuberculosis nucleic acid test is positive. Active tuberculosis is confirmed; airborne isolation and public health coordination initiated.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000006', 'SIGNAL-E2E-NOTE-006', 'e2000000-0000-4000-8000-000000000006', 'e2100000-0000-4000-8000-000000000006', 'clinical-note', 'final', 'C. Davis - acute gastroenteritis', '2026-10-02 19:15:00-05', 'Practitioner/DEMO-006', 'text/plain', 'SYNTHETIC DEMO NOTE. Thirty-one-year-old with fever, abdominal cramping, and frequent diarrhea beginning after a community barbecue. Stool multiplex testing detects Salmonella enterica. Salmonellosis is confirmed. Hydration plan reviewed and food exposure history documented.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000007', 'SIGNAL-E2E-NOTE-007', 'e2000000-0000-4000-8000-000000000007', 'e2100000-0000-4000-8000-000000000007', 'clinical-note', 'final', 'E. Brown - acute meningitis evaluation', '2026-10-08 09:15:00-05', 'Practitioner/DEMO-007', 'text/plain', 'SYNTHETIC DEMO NOTE. Fifteen-year-old with abrupt high fever, severe headache, neck stiffness, photophobia, and a non-blanching petechial rash. Cerebrospinal fluid culture isolates Neisseria meningitidis. Invasive meningococcal infection is confirmed; droplet precautions and immediate public health notification initiated.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000008', 'SIGNAL-E2E-NOTE-008', 'e2000000-0000-4000-8000-000000000008', 'e2100000-0000-4000-8000-000000000008', 'clinical-note', 'final', 'G. Thompson - severe community-acquired pneumonia', '2026-10-03 21:50:00-05', 'Practitioner/DEMO-008', 'text/plain', 'SYNTHETIC DEMO NOTE. Sixty-seven-year-old with fever, dry cough, dyspnea, and confusion after a recent hotel conference. Imaging shows multilobar pneumonia; sodium is low. Urine Legionella pneumophila antigen is positive. Legionellosis is confirmed; inpatient treatment and exposure interview planned.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000009', 'SIGNAL-E2E-NOTE-009', 'e2000000-0000-4000-8000-000000000009', 'e2100000-0000-4000-8000-000000000009', 'clinical-note', 'final', 'A. Patel - febrile bloody diarrhea', '2026-10-06 16:45:00-05', 'Practitioner/DEMO-009', 'text/plain', 'SYNTHETIC DEMO NOTE. Twenty-nine-year-old with fever, abdominal cramps, tenesmus, and bloody diarrhea after a catered gathering. Stool NAAT detects Shigella species. Shigellosis is confirmed; hydration, hygiene, and contact precautions reviewed.', 'signal_e2e_demo_2026', 'ClinicalDocument'),
('e2400000-0000-4000-8000-000000000010', 'SIGNAL-E2E-NOTE-010', 'e2000000-0000-4000-8000-000000000010', 'e2100000-0000-4000-8000-000000000010', 'clinical-note', 'final', 'R. King - expanding rash and joint pain', '2026-10-07 11:25:00-05', 'Practitioner/DEMO-010', 'text/plain', 'SYNTHETIC DEMO NOTE. Fifty-two-year-old with an expanding annular rash after hiking in a wooded area, followed by fatigue and migratory knee pain. Borrelia burgdorferi antibody testing is positive. Lyme disease is confirmed; treatment and tick-bite prevention discussed.', 'signal_e2e_demo_2026', 'ClinicalDocument')
ON CONFLICT (source, source_document_id) DO NOTHING;

COMMIT;

-- Confirm the ten patients and their linked structured evidence:
SELECT p.source_patient_id, p.first_name, p.last_name, c.condition_display,
       c.condition_code AS snomed_code, l.test_code AS loinc_code,
       l.test_display, e.start_time AS encounter_time
FROM patients p
JOIN conditions c ON c.patient_id = p.patient_id
JOIN lab_results l ON l.patient_id = p.patient_id
JOIN encounters e ON e.encounter_id = c.encounter_id
WHERE p.source = 'signal_e2e_demo_2026'
ORDER BY p.source_patient_id;
