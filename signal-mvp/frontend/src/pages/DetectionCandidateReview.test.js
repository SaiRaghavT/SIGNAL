import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

test("renders one overall-confidence score with the qualifying lab as primary and all source evidence inside", async () => {
  const vite = await createServer({
    root: frontendRoot,
    configFile: path.join(frontendRoot, "vite.config.js"),
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });
  try {
    const { default: Review } = await vite.ssrLoadModule("/src/pages/DetectionCandidateReview.jsx");
    const candidate = {
      disease: "Measles",
      status: "POTENTIAL",
      detection_priority: "HIGHEST",
      evidence_strength: 100,
      evidence_strength_method: "weighted_rule_based_v2",
      evidence_strength_components: [
        { factor: "primary_qualifying_laboratory", points: 100, detail: "Configured positive lab qualifies." },
        { factor: "evidence_strength_score", points: 100, detail: "Final score." },
      ],
      primary_trigger: {
        type: "laboratory",
        test_name: "Measles virus RNA",
        result: "positive",
        source_id: "lab-1",
        reason: "Mapped final positive result.",
      },
      signals: [
        { trigger_type: "LAB_RESULT", detection_priority: "HIGHEST", evidence: { source_type: "DiagnosticReport", source_id: "lab-1", display: "Measles virus RNA", result_classification: "POSITIVE", raw_result: "positive", positive_detection_eligible: true, disease_specific_test_mapping: true, classification_reason: "Mapped final positive result." } },
        { trigger_type: "DOCUMENT_DIAGNOSIS", evidence: { source_type: "ClinicalDocument", source_id: "doc-1", concept: "Measles", evidence_text: "Measles confirmed." } },
      ],
    };
    const patientContext = {
      lab_results: [{ lab_result_id: "lab-1", test: { display: "Measles virus RNA" }, conclusion: "Positive", report_status: "final", effective_time: "2026-10-15" }],
      clinical_documents: [{ document_id: "doc-1", title: "Clinical note", extracted_text: "Measles confirmed." }],
    };
    const markup = renderToStaticMarkup(createElement(Review, {
      candidate,
      conditionName: "Measles",
      patientContext,
      onContinue: () => {},
      onRunAgain: () => {},
    }));

    assert.equal((markup.match(/detection-evidence-strength-card/g) || []).length, 1);
    assert.equal((markup.match(/aria-label="Overall confidence score"/g) || []).length, 1);
    assert.match(markup, /OVERALL CONFIDENCE SCORE/);
    assert.doesNotMatch(markup, /Score breakdown|points/);
    assert.equal((markup.match(/<progress/g) || []).length, 1);
    assert.equal((markup.match(/class="detection-strength-meter"><strong>100/g) || []).length, 1);
    assert.match(markup, /PRIMARY TRIGGER · QUALIFYING POSITIVE LABORATORY RESULT/);
    const laboratoryCardStart = markup.indexOf('<details class="detection-category-card detection-category-laboratory">');
    const laboratoryCardEnd = markup.indexOf("</details>", laboratoryCardStart);
    const primaryTriggerPosition = markup.indexOf("PRIMARY TRIGGER", laboratoryCardStart);
    assert.ok(laboratoryCardStart >= 0 && primaryTriggerPosition > laboratoryCardStart && primaryTriggerPosition < laboratoryCardEnd);
    assert.doesNotMatch(markup, /detection-expanded-primary-trigger/);
    assert.doesNotMatch(markup, /Interpreted result:/);
    assert.match(markup, /Measles virus RNA/);
    assert.match(markup, /Measles confirmed\./);
    assert.match(markup, /Clinical note/);
  } finally {
    await vite.close();
  }
});
