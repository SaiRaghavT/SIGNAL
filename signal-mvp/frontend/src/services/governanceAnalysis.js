export function buildEvidencePatterns(reviewedRows) {
  const patterns = new Map()
  reviewedRows
    .filter(row => row.reviewer_decision && row.reviewer_decision !== 'not_available')
    .forEach(row => {
      const evidenceTypes = [...new Set((row.evidence || []).map(item => item.source_type || item.display).filter(Boolean))]
      evidenceTypes.forEach(type => {
        const pattern = patterns.get(type) || { pattern: type, cases: 0, decisions: {} }
        pattern.cases += 1
        pattern.decisions[row.reviewer_decision] = (pattern.decisions[row.reviewer_decision] || 0) + 1
        patterns.set(type, pattern)
      })
    })
  return [...patterns.values()].map(pattern => ({
    ...pattern,
    status: 'requires_human_review',
    suggestion: 'Review this evidence pattern and associated workflow outcomes. No automatic rule or model update is made.',
  }))
}

export function buildEvaluationReadiness(candidates, reviewedCases) {
  const confidence = candidates
    .filter(item => item.confidence !== null && item.confidence !== undefined && item.confidence !== '')
    .map(item => Number(item.confidence))
    .filter(value => Number.isFinite(value) && value >= 0 && value <= 1)
  return {
    candidate_count: candidates.length,
    confidence_count: confidence.length,
    mean_confidence: confidence.length ? confidence.reduce((sum, value) => sum + value, 0) / confidence.length : null,
    reviewed_cases: reviewedCases,
    classification_metrics: 'insufficient_data',
  }
}

export function findGovernanceIssues(candidates) {
  return candidates.flatMap(candidate => {
    const issues = []
    if (!Array.isArray(candidate.evidence) || candidate.evidence.length === 0) issues.push('Source evidence is missing.')
    if (candidate.confidence === null || candidate.confidence === undefined) issues.push('Confidence is not available.')
    else if (!Number.isFinite(Number(candidate.confidence)) || Number(candidate.confidence) < 0 || Number(candidate.confidence) > 1) issues.push('Confidence is outside the supported 0 to 1 range.')
    return issues.map(reason => ({ candidate_id: candidate.candidate_id, disease: candidate.disease, reason, status: 'requires_human_review' }))
  })
}
