import test from "node:test";
import assert from "node:assert/strict";

import {
  formatBackendScore,
  getLabRecordFacts,
  getSourceRecordText,
  groupSignalsByVerifiedSource,
} from "./detectionEvidence.js";

test("groups interpretations only when their stable source IDs match", () => {
  const first = { trigger_type: "DIAGNOSIS_PROBLEM", evidence: { source_id: "condition-1" } };
  const second = { trigger_type: "DOCUMENT_DIAGNOSIS", evidence: { source_id: "condition-1" } };
  const unrelated = { trigger_type: "DIAGNOSIS_PROBLEM", evidence: { source_id: "condition-2" } };

  const groups = groupSignalsByVerifiedSource([first, second, unrelated]);

  assert.equal(groups.length, 2);
  assert.deepEqual(groups[0].signals, [first, second]);
  assert.deepEqual(groups[1].signals, [unrelated]);
  assert.equal(groups[0].signals.length, 2, "two interpretations remain attached to one source group");
});

test("does not merge same-worded signals from different source records", () => {
  const first = { evidence: { source_id: "doc-a", concept: "Rash" } };
  const second = { evidence: { source_id: "doc-b", concept: "Rash" } };

  const groups = groupSignalsByVerifiedSource([first, second]);

  assert.equal(groups.length, 2);
  assert.notEqual(groups[0].key, groups[1].key);
});

test("groups a linked lab observation under its diagnostic report source", () => {
  const observationSignal = { trigger_type: "LAB_RESULT", evidence: { source_type: "Observation", source_id: "obs-source-1" } };
  const reportSignal = { trigger_type: "LAB_RESULT", evidence: { source_type: "DiagnosticReport", source_id: "report-source-1", result_classification: "POSITIVE" } };
  const context = {
    lab_results: [{
      lab_result_id: "lab-internal-1",
      source_lab_result_id: "report-source-1",
      observations: [{ observation_id: "obs-internal-1", source_observation_id: "obs-source-1" }],
    }],
  };

  const groups = groupSignalsByVerifiedSource([observationSignal, reportSignal], context);

  assert.equal(groups.length, 1);
  assert.equal(groups[0].sourceId, "lab-internal-1");
  assert.deepEqual(groups[0].signals, [reportSignal, observationSignal]);
});

test("keeps signals with unknown source relationships separate", () => {
  const first = { evidence: { display: "Measles" } };
  const second = { evidence: { display: "Measles" } };
  const groups = groupSignalsByVerifiedSource([first, second]);

  assert.equal(groups.length, 2);
  assert.equal(groups[0].sourceId, "");
  assert.notEqual(groups[0].key, groups[1].key);
});

test("does not infer a positive lab result from a test name or order status", () => {
  const facts = getLabRecordFacts({
    test: { display: "Measles virus RNA" },
    report_status: "registered",
    observations: [],
  });

  assert.equal(facts.status, "registered");
  assert.equal(facts.hasResult, false);
  assert.deepEqual(facts.values, []);
});

test("omits empty laboratory status and value labels", () => {
  const facts = getLabRecordFacts({ report_status: "", conclusion: " ", observations: [{ value: null }] });

  assert.equal(facts.status, "");
  assert.equal(facts.hasResult, false);
  assert.deepEqual(facts.values, []);
});

test("exposes only an explicit backend score and hides missing values", () => {
  assert.equal(formatBackendScore(undefined), null);
  assert.equal(formatBackendScore(null), null);
  assert.equal(formatBackendScore(1), "1.00");
  assert.equal(formatBackendScore(0.75), "0.75");
});

test("source modal content can preserve original wording without fabricating missing text", () => {
  const original = "Rash on face. No fever.";
  assert.equal(getSourceRecordText({ extracted_text: original }), original);
  assert.equal(getSourceRecordText({ title: "No text available" }), "");
});
