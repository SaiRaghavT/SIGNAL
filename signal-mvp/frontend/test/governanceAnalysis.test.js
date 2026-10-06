import test from 'node:test'
import assert from 'node:assert/strict'
import { buildEvaluationReadiness, buildEvidencePatterns, findGovernanceIssues } from '../src/services/governanceAnalysis.js'

test('reviewed outcomes produce evidence patterns with transparent decision counts', () => {
  const patterns = buildEvidencePatterns([
    { reviewer_decision: 'APPROVE', evidence: [{ source_type: 'Condition' }, { source_type: 'Laboratory' }] },
    { reviewer_decision: 'REJECT', evidence: [{ source_type: 'Condition' }] },
    { reviewer_decision: 'not_available', evidence: [{ source_type: 'Condition' }] },
  ])
  assert.deepEqual(patterns.find(item => item.pattern === 'Condition').decisions, { APPROVE: 1, REJECT: 1 })
  assert.equal(patterns.find(item => item.pattern === 'Condition').cases, 2)
  assert.equal(patterns[0].status, 'requires_human_review')
})

test('no reviewer outcomes produce no fabricated learning patterns', () => {
  assert.deepEqual(buildEvidencePatterns([{ reviewer_decision: 'not_available', evidence: [{ source_type: 'Condition' }] }]), [])
})

test('evaluation readiness reports confidence descriptively and leaves classification metrics unavailable', () => {
  const result = buildEvaluationReadiness([{ confidence: 0.8 }, { confidence: 1 }, { confidence: null }, { confidence: 2 }], 0)
  assert.equal(result.candidate_count, 4)
  assert.equal(result.confidence_count, 2)
  assert.equal(result.mean_confidence, 0.9)
  assert.equal(result.classification_metrics, 'insufficient_data')
  assert.equal(result.reviewed_cases, 0)
})

test('governance checks flag missing evidence and invalid confidence without changing candidate state', () => {
  const candidates = [
    { candidate_id: 'candidate-1', disease: 'measles', evidence: [], confidence: null, status: 'POTENTIAL' },
    { candidate_id: 'candidate-2', disease: 'measles', evidence: [{ source_type: 'Condition' }], confidence: 1.2, status: 'POTENTIAL' },
  ]
  const findings = findGovernanceIssues(candidates)
  assert.equal(findings.length, 3)
  assert.equal(findings[0].candidate_id, 'candidate-1')
  assert.equal(findings[1].reason, 'Confidence is not available.')
  assert.equal(findings[2].status, 'requires_human_review')
  assert.equal(candidates[0].status, 'POTENTIAL')
})
