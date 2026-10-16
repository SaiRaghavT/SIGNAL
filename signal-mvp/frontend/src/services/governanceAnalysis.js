export function buildEvidencePatterns(reviewedRows) {
  const patterns = new Map()
  const record = (type, row, decision = row.reviewer_decision) => {
    const pattern = patterns.get(type) || { pattern: type, cases: 0, decisions: {} }
    pattern.cases += 1
    pattern.decisions[decision] = (pattern.decisions[decision] || 0) + 1
    patterns.set(type, pattern)
  }
  reviewedRows
    .filter(row => row.reviewer_decision && row.reviewer_decision !== 'not_available')
    .forEach(row => {
      const evidenceTypes = [...new Set((row.evidence || []).map(item => item.source_type || item.display).filter(Boolean))]
      evidenceTypes.forEach(type => record(`Evidence: ${type}`, row))
    })
  reviewedRows.forEach(row => {
    if (row.validation_status === 'INVALID' || row.validation_errors?.length) record('Case validation failure', row, row.validation_status || 'INVALID')
    if (['REJECT', 'REQUEST_INFORMATION'].includes(row.reviewer_decision)) record('Case returned or rejected by reviewer', row)
    if (row.submission_errors?.length) record('Submission reported errors', row, row.pha_outcome)
    if (row.pha_outcome === 'ACKNOWLEDGED') record('PHA acknowledgement', row, row.pha_outcome)
    else if (row.pha_outcome !== 'not_available' && row.pha_outcome) record(`ACKNOWLEDGEMENT STATUS: ${row.pha_outcome}`, row, row.pha_outcome)
    if (row.correction_reason && row.correction_reason !== 'not_available' && !row.submission_errors?.length && !row.validation_errors?.length) record('Correction or reviewer note recorded', row)
  })
  return [...patterns.values()].map(pattern => ({
    ...pattern,
    status: 'requires_human_review',
    suggestion: 'Review this evidence pattern and associated workflow outcomes. No automatic rule or model update is made.',
  }))
}

export function buildEvaluationReadiness(candidates, reviewedCases) {
  const confidence = candidates
    .filter(item => item.evidence_strength !== null && item.evidence_strength !== undefined && item.evidence_strength !== '')
    .map(item => Number(item.evidence_strength))
    .filter(value => Number.isFinite(value) && value >= 0 && value <= 100)
  return {
    candidate_count: candidates.length,
    evidence_strength_count: confidence.length,
    mean_evidence_strength: confidence.length ? confidence.reduce((sum, value) => sum + value, 0) / confidence.length : null,
    reviewed_cases: reviewedCases,
    classification_metrics: 'insufficient_data',
  }
}

export function findGovernanceIssues(candidates) {
  return candidates.flatMap(candidate => {
    const issues = []
    if (!Array.isArray(candidate.evidence) || candidate.evidence.length === 0) issues.push('Source evidence is missing.')
    if (candidate.evidence_strength === null || candidate.evidence_strength === undefined) issues.push('Evidence strength is not available.')
    else if (!Number.isFinite(Number(candidate.evidence_strength)) || Number(candidate.evidence_strength) < 0 || Number(candidate.evidence_strength) > 100) issues.push('Evidence strength is outside the supported 0 to 100 range.')
    return issues.map(reason => ({ candidate_id: candidate.candidate_id, disease: candidate.disease, reason, status: 'requires_human_review' }))
  })
}
