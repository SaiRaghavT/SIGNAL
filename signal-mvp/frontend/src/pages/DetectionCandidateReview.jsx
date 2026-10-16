import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, FileSearch, FileText, Stethoscope, TestTube } from "lucide-react";
import {
  getLabRecordFacts,
  getSourceRecordText,
  groupSignalsByVerifiedSource,
} from "./detectionEvidence.js";

function evidenceCategory(signal) {
  const type = String(signal?.trigger_type || "").toUpperCase();
  const sourceType = String(signal?.evidence?.source_type || signal?.source_type || "").toLowerCase();
  if (type.startsWith("DOCUMENT_") || type === "DOCUMENT_EVIDENCE" || sourceType.includes("document") || signal?.evidence?.evidence_role === "supporting_clinical_evidence") return "document";
  if (type.includes("LAB") || sourceType.includes("diagnosticreport") || sourceType.includes("laboratory")) return "laboratory";
  return "clinical";
}

function safeDisplay(value) {
  if (value == null || value === "") return "";
  if (Array.isArray(value)) return value.map(safeDisplay).filter(Boolean).join(", ");
  if (typeof value === "object") return value.display || value.text || value.code || value.name || "";
  return String(value);
}

function sourceMatch(sourceId, context) {
  if (!sourceId || !context) return null;
  const records = [
    ...(context.conditions || []).map((record) => ({ record, kind: "Diagnosis", ids: [record.condition_id, record.source_condition_id, record.id] })),
    ...(context.lab_results || context.labs || []).map((record) => ({ record, kind: "Laboratory", ids: [record.lab_result_id, record.source_lab_result_id, record.diagnostic_report_id, record.id] })),
    ...(context.clinical_documents || context.documents || []).map((record) => ({ record, kind: "Clinical document", ids: [record.document_id, record.source_document_id, record.id] })),
    ...(context.observations || []).map((record) => ({ record, kind: "Observation", ids: [record.observation_id, record.source_observation_id, record.id] })),
  ];
  const matches = records.filter(({ ids }) => ids.some((id) => id != null && String(id) === String(sourceId)));
  return matches.length === 1 ? matches[0] : null;
}

function sourceTitle(record, signals, category) {
  const evidence = signals[0]?.evidence || {};
  return record?.title || record?.test?.display || record?.code?.display || record?.display ||
    evidence.source_title || evidence.display || evidence.concept ||
    (category === "clinical" ? "Clinical record" : category === "laboratory" ? "Laboratory record" : "Clinical document");
}

function categoryIcon(category) {
  if (category === "clinical") return <Stethoscope aria-hidden="true" />;
  if (category === "laboratory") return <TestTube aria-hidden="true" />;
  return <FileText aria-hidden="true" />;
}

function documentFindingLabels(signals) {
  return [...new Set((signals || []).flatMap((signal) => {
    const evidence = signal?.evidence || {};
    return [evidence.concept, evidence.display]
      .filter((value) => typeof value === "string" && value.trim())
      .map((value) => value.trim());
  }))];
}

function isPrimarySourceGroup(group, primaryTrigger, patientContext) {
  if (!primaryTrigger) return false;
  const triggerRefs = new Set([primaryTrigger.source_id, primaryTrigger.source_reference]
    .filter((value) => value != null && value !== "")
    .map(String));
  if (!triggerRefs.size) return false;
  const signalMatches = group.signals.some((signal) => {
    const evidence = signal?.evidence || {};
    return [evidence.source_id, evidence.source_reference, evidence.observation_id]
      .some((value) => value != null && triggerRefs.has(String(value)));
  });
  if (signalMatches) return true;
  const record = sourceMatch(group.sourceId, patientContext)?.record;
  return [group.sourceId, record?.lab_result_id, record?.source_lab_result_id, record?.diagnostic_report_id]
    .some((value) => value != null && triggerRefs.has(String(value)));
}

function SignalCategoryCard({ category, title, description, groups, patientContext, onOpenSource, primaryTrigger }) {
  const findingCount = groups.reduce((total, group) => total + (
    category === "document"
      ? documentFindingLabels(group.signals).length
      : 1
  ), 0);
  const primaryGroup = groups.find((group) => isPrimarySourceGroup(group, primaryTrigger, patientContext)) || groups[0];
  const primaryLink = sourceMatch(primaryGroup?.sourceId, patientContext);
  const primaryTitle = primaryGroup ? sourceTitle(primaryLink?.record, primaryGroup.signals, category) : "";
  const primaryLab = category === "laboratory" && primaryLink?.kind === "Laboratory" ? getLabRecordFacts(primaryLink.record) : null;
  const resultText = primaryLab?.values.find((item) => /positive|negative|detected|not detected/i.test(item.value))?.value || "";
  return <details className={`detection-category-card detection-category-${category}`}>
    <summary className="detection-category-heading">
      <span className="detection-category-icon">{categoryIcon(category)}</span>
      <div className="detection-category-title"><span>{title}</span><h4>{primaryTitle}</h4><small>{description}</small></div>
      <div className="detection-category-badges">{resultText && <span className="detection-result-badge">{resultText}</span>}{primaryLab?.status && <span className="detection-status-badge">{primaryLab.status}</span>}<span className="detection-category-count">{findingCount} finding{findingCount === 1 ? "" : "s"}</span></div>
      <ChevronDown className="detection-category-toggle" aria-hidden="true" />
    </summary>
    <div className="detection-category-sources">
      {groups.map((group) => <EvidenceSourceCard key={group.key} group={group} showSourceTitle={groups.length > 1} context={patientContext} onOpenSource={onOpenSource} isPrimaryTrigger={isPrimarySourceGroup(group, primaryTrigger, patientContext)} />)}
    </div>
  </details>;
}

function metadataRows(record, kind, sourceId) {
  const code = record?.test || record?.code || {};
  const lab = kind === "Laboratory" ? getLabRecordFacts(record) : null;
  return [
    ["Source type", kind], ["Source record ID", sourceId], ["Encounter ID", record?.encounter_id],
    ["Recorded", record?.effective_time || record?.document_date || record?.recorded_time || record?.created_at],
    ["Record status", record?.document_status || record?.clinical_status || record?.status || lab?.status],
    ["Terminology code", code?.code], ["Terminology system", code?.system],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
}

function DetailRows({ rows }) {
  if (!rows.length) return null;
  return <dl className="detection-detail-rows">{rows.map(([label, value]) => {
    const className = String(label).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return <div className={`detection-detail-${className}`} key={label}><dt>{label}</dt><dd>{safeDisplay(value)}</dd></div>;
  })}</dl>;
}

function SourceDialog({ source, onClose }) {
  const dialogRef = useRef(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);
  const record = source?.record;
  const originalText = getSourceRecordText(record);
  const lab = source?.kind === "Laboratory" ? getLabRecordFacts(record) : null;
  return <dialog ref={dialogRef} className="detection-source-dialog" aria-labelledby="detection-source-dialog-title" onClose={onClose}>
    <header className="detection-source-dialog-header"><div><span className="detection-eyebrow">ORIGINAL RECORD · {source?.kind}</span><h2 id="detection-source-dialog-title">{source?.title}</h2></div><button type="button" onClick={() => dialogRef.current?.close()} aria-label="Close original record">×</button></header>
    <div className="detection-source-dialog-body">
      <DetailRows rows={metadataRows(record, source?.kind, source?.sourceId)} />
      {source?.kind === "Clinical document" && <section className="detection-original-text"><h3>Original clinical wording</h3>{originalText ? <pre>{originalText}</pre> : <p>Original document text is not available in the current patient context.</p>}</section>}
      {lab && <section className="detection-source-lab-results"><h3>Laboratory record</h3>{lab.status && <p><b>Record status:</b> {lab.status}</p>}{lab.values.length ? lab.values.map((item, index) => <p key={`${item.label}-${index}`}><b>{item.label}:</b> {item.value}</p>) : <p>No result value is present in this record.</p>}</section>}
      {source?.kind === "Clinical document" && originalText && <p className="detection-source-highlight-note">Evidence is not highlighted because the response does not include verified text offsets.</p>}
    </div>
    <footer className="detection-source-dialog-footer"><button type="button" onClick={() => dialogRef.current?.close()}>Close</button></footer>
  </dialog>;
}

function EvidenceSourceCard({ group, showSourceTitle, context, onOpenSource, isPrimaryTrigger }) {
  const linked = sourceMatch(group.sourceId, context);
  const record = linked?.record;
  const category = evidenceCategory(group.signals[0]);
  const kind = linked?.kind || (category === "laboratory" ? "Laboratory" : category === "clinical" ? "Clinical record" : "Clinical document");
  const displayKind = kind === "Observation" ? "clinical signal" : kind === "Clinical document" ? "document" : kind.toLowerCase();
  const title = sourceTitle(record, group.signals, category);
  const lab = kind === "Laboratory" && record ? getLabRecordFacts(record) : null;
  const documentEvidence = group.signals.map((signal) => signal?.evidence || {}).filter((evidence) => evidence.concept || evidence.evidence_text);
  const findings = documentFindingLabels(group.signals);
  const hasTriggerMatch = group.signals.some((signal) => signal?.trigger_id);
  const rationale = category === "clinical"
    ? hasTriggerMatch ? "This structured clinical record matched a configured clinical detection trigger." : "Structured clinical evidence is available for review."
    : category === "laboratory"
      ? (() => {
        const labEvidence = group.signals[0]?.evidence || {};
        const classification = labEvidence.result_classification;
        return classification
          ? `${isPrimaryTrigger && labEvidence.positive_detection_eligible ? "The mapped result qualifies as the highest-priority laboratory trigger." : `${labEvidence.classification_reason || `The result was classified as ${classification.toLowerCase()}.`} ${labEvidence.positive_detection_eligible ? "This mapped positive result qualified as the highest-priority laboratory trigger." : "This result did not qualify as a positive laboratory trigger."}`}`
          : hasTriggerMatch ? "This laboratory record matched a configured test trigger; the match alone does not establish the result." : "Laboratory evidence is available for review.";
      })()
      : documentEvidence.length ? "The document contains extracted clinical findings relevant to this detection review." : "Structured document evidence is available for review.";
  const sourceDescription = kind === "Diagnosis" ? "Diagnosis record" : kind === "Laboratory" ? "Laboratory record" : kind === "Observation" ? "Clinical observation" : "Clinical document";
  const clinicalRecordLabel = kind === "Diagnosis" ? "Diagnosis details" : "Clinical observation details";
  const clinicalFieldLabel = kind === "Diagnosis" ? "Condition" : "Finding";
  const clinicalStatus = record?.clinical_status || record?.status || "";
  const documentText = getSourceRecordText(record);
  const extractedTexts = [...new Set(documentEvidence.map((evidence) => evidence.evidence_text).filter(Boolean))];
  const labResult = lab?.values.find((item) => /positive|negative|detected|not detected/i.test(item.value))?.value || "";
  const originalTestName = record?.test?.display || record?.test?.text || title;

  return <article className={`detection-source-card detection-source-card-${category}`}>
    <div className="detection-source-card-main">
      {showSourceTitle && <header className="detection-expanded-source-heading"><span>{sourceDescription}</span><strong>{title}</strong></header>}
      {isPrimaryTrigger && <span className="detection-primary-trigger-badge">{category === "laboratory" ? "PRIMARY TRIGGER · QUALIFYING POSITIVE LABORATORY RESULT" : "PRIMARY TRIGGER"}</span>}
      {category === "clinical" && <>
        <section className="detection-clinical-explanation"><span className="detection-explanation-check"><Check aria-hidden="true" /></span><div><strong>Why SIGNAL detected this</strong><p>{rationale}</p></div></section>
        <section className="detection-clinical-record"><span className="detection-clinical-record-icon"><Stethoscope aria-hidden="true" /></span><div><strong>{clinicalRecordLabel}</strong><p>{clinicalFieldLabel}: <b>{title}</b></p>{clinicalStatus && <p>Status: <b>{clinicalStatus}</b></p>}</div>{clinicalStatus && <span className="detection-status-badge">{clinicalStatus}</span>}</section>
      </>}
      {category === "laboratory" && <>
        {!isPrimaryTrigger && (labResult || lab?.status) && <div className="detection-lab-badges">{labResult && <span className="detection-result-badge">{labResult}</span>}{lab?.status && <span className="detection-status-badge">{lab.status}</span>}</div>}
        <section className="detection-clinical-explanation"><span className="detection-explanation-check"><Check aria-hidden="true" /></span><div><strong>Why SIGNAL detected this</strong><p>{rationale}</p></div></section>
        <section className="detection-original-test"><strong>Test name</strong><p>{originalTestName}</p>{(group.signals[0]?.evidence?.code || record?.test?.code) && <p><span>Test code:</span> {safeDisplay(group.signals[0]?.evidence?.code || record?.test?.code)}{(group.signals[0]?.evidence?.code_system || record?.test?.system) ? ` · ${safeDisplay(group.signals[0]?.evidence?.code_system || record?.test?.system)}` : ""}</p>}{!isPrimaryTrigger && group.signals[0]?.evidence?.result_classification && <p><span>Interpreted result:</span> {group.signals[0].evidence.result_classification}</p>}{(record?.effective_time || group.signals[0]?.evidence?.effective_time) && <p><span>Collection date:</span> {safeDisplay(record?.effective_time || group.signals[0].evidence.effective_time)}</p>}{(group.sourceId || group.signals[0]?.evidence?.source_reference) && <p><span>Source reference:</span> {safeDisplay(group.signals[0]?.evidence?.source_reference || group.sourceId)}</p>}{lab?.values.filter((item) => item.value !== labResult).map((item, index) => <p key={`${item.label}-${index}`}><span>{item.label}:</span> {item.value}</p>)}</section>
      </>}
      {category === "document" && <>
        <section className="detection-document-findings"><strong>What SIGNAL extracted</strong>{findings.length ? <ul>{findings.map((finding) => <li key={finding}>{finding}</li>)}</ul> : <p>No individual finding text was returned for this source.</p>}</section>
        {(documentText || extractedTexts.length > 0) && <section className="detection-document-extracted"><FileText aria-hidden="true"/><div><strong>Extracted clinical text</strong>{documentText ? <p>{documentText}</p> : extractedTexts.map((text) => <p key={text}>{text}</p>)}</div></section>}
        <section className="detection-clinical-explanation detection-document-explanation"><span className="detection-explanation-check"><Check aria-hidden="true" /></span><div><strong>Why SIGNAL detected this</strong><p>{rationale}</p></div></section>
      </>}
      {!group.sourceId && <p className="detection-source-warning">This finding has no verified link to an original source record.</p>}
      {group.sourceId && !record && <p className="detection-source-warning">The linked source record is not available in the current patient context.</p>}
      <footer className="detection-source-card-actions"><div><strong>Source</strong><span>{sourceDescription}{record?.provenance?.source ? ` (${record.provenance.source})` : ""}</span></div>{record && <button type="button" className="detection-source-open" onClick={() => onOpenSource({ record, kind, sourceId: group.sourceId, title })}><FileSearch aria-hidden="true"/>View original {displayKind}</button>}</footer>
    </div>
  </article>;
}

export default function DetectionCandidateReview({ candidate, conditionName, patientContext, onContinue, onRunAgain }) {
  const signals = [candidate?.signals, candidate?.supporting_signals, candidate?.evidence].find((items) => Array.isArray(items) && items.length) || [];
  const signalCategories = [
    { key: "laboratory", title: "SIGNAL LABORATORY SIGNAL", description: "Laboratory evidence" },
    { key: "clinical", title: "SIGNAL CLINICAL SIGNAL", description: "Structured diagnosis evidence" },
    { key: "document", title: "SIGNAL DOCUMENT", description: "AI-extracted clinical evidence" },
  ].map((category) => ({
    ...category,
    groups: groupSignalsByVerifiedSource(
      signals.filter((signal) => evidenceCategory(signal) === category.key),
      patientContext,
    ),
  })).filter((category) => category.groups.length > 0);
  const [activeSource, setActiveSource] = useState(null);
  const name = conditionName || "Potential condition";
  const status = candidate?.status || "Review required";
  const legacyRatio = ["legacy_evidence_strength_ratio", "weighted_rule_based_v1"].includes(candidate?.confidence_method)
    && candidate?.confidence != null
    ? Number(candidate.confidence)
    : null;
  const rawCandidateScore = candidate?.evidence_strength ?? (legacyRatio == null ? null : legacyRatio * 100);
  const numericCandidateScore = rawCandidateScore == null ? null : Number(rawCandidateScore);
  const candidateScore = Number.isFinite(numericCandidateScore)
    ? Math.round(Math.max(0, Math.min(100, numericCandidateScore)))
    : null;
  const qualifyingLab = signals.find((signal) => {
    const evidence = signal?.evidence || {};
    return String(signal?.trigger_type || "").toUpperCase() === "LAB_RESULT"
      && evidence.positive_detection_eligible === true
      && evidence.disease_specific_test_mapping === true;
  });
  const primaryTrigger = candidate?.primary_trigger || (qualifyingLab ? {
    type: "laboratory",
    label: "Qualifying positive laboratory result",
    test_name: qualifyingLab.evidence?.display,
    result: qualifyingLab.evidence?.raw_result || qualifyingLab.evidence?.result,
    source_id: qualifyingLab.evidence?.source_id,
    source_reference: qualifyingLab.evidence?.source_reference || qualifyingLab.evidence?.source_id,
    collection_date: qualifyingLab.evidence?.collection_time || qualifyingLab.evidence?.effective_time,
    reason: qualifyingLab.evidence?.classification_reason,
  } : null);
  const primaryTriggerCategory = primaryTrigger?.type === "laboratory"
    ? "laboratory"
    : primaryTrigger?.type === "structured"
      ? "clinical"
      : primaryTrigger ? "document" : null;

  return <div className="enterprise-detection-result">
    <section className="detection-result-hero" aria-labelledby="detection-result-title">
      <div className="detection-result-hero-topline"><div className="detection-result-kicker">SIGNAL DETECTION</div><button type="button" className="detection-run-again" onClick={onRunAgain}>Run again</button></div>
      <div className="detection-result-hero-main"><div><span className="detection-result-overline">{candidate?.detection_priority === "HIGHEST" ? "Highest detection priority · qualifying laboratory evidence" : "Potential condition"}</span><h2 id="detection-result-title">{name}</h2><div className="detection-status-pill">{status}</div><p className="detection-result-explanation">SIGNAL matched available clinical records to configured detection triggers. This is a review finding; it does not confirm a diagnosis or determine reportability.</p></div></div>
    </section>

    <section className="detection-evidence-strength-card" aria-labelledby="detection-confidence-heading">
      <div className="detection-section-heading"><div><span className="detection-eyebrow">WHY THIS CASE WAS FLAGGED</span><h3 id="detection-confidence-heading">Overall confidence</h3><p>Each original source appears once. Expand a signal to review its clinical evidence.</p></div></div>
      <div className="detection-strength-summary">
        <div><span className="detection-eyebrow">OVERALL CONFIDENCE SCORE</span><p>Rule-based score from matched clinical evidence; not a calibrated disease probability.</p></div>
        {candidateScore !== null ? <div className="detection-strength-meter"><strong>{candidateScore}<small>/100</small></strong><progress max="100" value={candidateScore} aria-label="Overall confidence score" aria-valuenow={candidateScore} /> </div> : <strong className="detection-strength-unavailable">Not available</strong>}
      </div>
      {signalCategories.length ? <div className="detection-signal-categories">{signalCategories.map(({ key, ...categoryProps }) => <SignalCategoryCard key={key} category={key} {...categoryProps} primaryTrigger={key === primaryTriggerCategory ? primaryTrigger : null} patientContext={patientContext} onOpenSource={setActiveSource} />)}</div> : <p className="detection-no-evidence">No supporting signals were included with this candidate.</p>}
    </section>

    <div className="detection-action-bar"><div><span className="detection-eyebrow">NEXT STEP</span><strong>Review and next steps</strong><small>Overall confidence appears when the detection result supports it.</small></div><button type="button" className="detection-primary-action" onClick={() => onContinue(candidate)}>Continue to Reporting <span aria-hidden="true">→</span></button></div>
    {activeSource && <SourceDialog source={activeSource} onClose={() => setActiveSource(null)} />}
  </div>;
}
