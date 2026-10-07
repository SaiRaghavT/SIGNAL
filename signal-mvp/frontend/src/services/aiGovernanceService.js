import { request } from '../api/client.js'
import { buildEvaluationReadiness, buildEvidencePatterns, findGovernanceIssues } from './governanceAnalysis.js'

const allPages = async (path, pageSize = 100) => {
  const first = await request(`${path}?page=1&page_size=${pageSize}`)
  const items = [...(first.items || [])]
  const pages = first.pages ?? Math.ceil((first.total || 0) / pageSize)
  for (let page = 2; page <= pages; page += 1) {
    const next = await request(`${path}?page=${page}&page_size=${pageSize}`)
    items.push(...(next.items || []))
  }
  return items
}

const getSourceData = async () => {
  const [candidateRows, caseRows, submissions, audit, auditSummary, status] = await Promise.all([
    allPages('/api/candidates'),
    allPages('/api/cases'),
    allPages('/api/submissions'),
    request('/api/audit/events'),
    request('/api/audit/events/summary'),
    request('/api/agents/status'),
  ])
  return { candidates: candidateRows, cases: caseRows, submissions, audit, auditSummary, agents: status.agents || [] }
}
const getAgentStatus = async () => (await request('/api/agents/status')).agents || []
const getAuditLedger = async () => request('/api/audit/events')
const getAuditSummary = async () => request('/api/audit/events/summary')

const label = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
const findCandidate = (data, id) => data.candidates.find(item => item.candidate_id === id)
const relevantDisease = value => String(value || '').toLowerCase().includes('measles')
const isTexas = value => /texas|\btx\b/i.test(String(value || ''))
const reviewDecision = review => review?.payload?.decision || review?.status || 'not_available'
const auditDetail = event => event.description || JSON.stringify(event.new_value || {})

async function getCaseContext(caseId) {
  if (!caseId) return null
  const [caseRecord, review, validation] = await Promise.all([
    request(`/api/cases/${encodeURIComponent(caseId)}`).catch(() => null),
    request(`/api/cases/${encodeURIComponent(caseId)}/review`).catch(() => null),
    request(`/api/cases/${encodeURIComponent(caseId)}/validation`).catch(() => null),
  ])
  return { caseRecord, review, validation }
}

async function getAcknowledgement(submissionId) {
  if (!submissionId) return null
  return request(`/api/submissions/${encodeURIComponent(submissionId)}/acknowledgement`).catch(() => null)
}

async function buildOutcomeData() {
  const data = await getSourceData()
  const cases = data.cases.filter(item => relevantDisease(item.disease) && isTexas(item.jurisdiction))
  const submissionsByCase = new Map()
  data.submissions.forEach(item => {
    const previous = submissionsByCase.get(item.case_id)
    if (!previous || Date.parse(item.created_at) > Date.parse(previous.created_at)) submissionsByCase.set(item.case_id, item)
  })
  const contexts = await Promise.all(cases.map(async item => [item.case_id, await getCaseContext(item.case_id)]))
    const caseContexts = new Map(contexts)
  const acknowledgements = new Map(await Promise.all([...submissionsByCase.entries()].map(async ([caseId, submission]) => [caseId, await getAcknowledgement(submission.submission_id)])))
  const rows = cases.map(item => {
    const context = caseContexts.get(item.case_id)
    const review = context?.review
    const validation = context?.validation
    const candidate = findCandidate(data, item.candidate_id)
    const candidateEvent = data.audit.find(event => event.entity_type === 'CANDIDATE' && event.entity_id === item.candidate_id)
    const submission = submissionsByCase.get(item.case_id)
    const acknowledgement = acknowledgements.get(item.case_id)
    const decision = reviewDecision(review)
    return {
      id: item.case_id,
      candidate_id: item.candidate_id,
      agent_id: candidateEvent?.source_agent || 'not_available',
      ai_output: candidate?.status || 'not_available',
      clinical_staff_decision: review?.payload?.reviewer_role === 'Clinical Staff' ? decision : 'not_available',
      reporting_admin_decision: review?.payload?.reviewer_role === 'Reporting Administrator' ? decision : 'not_available',
      reviewer_decision: decision,
      review_reason: review?.payload?.comments || 'not_available',
      reportability_decision: item.final_decision || item.reportability_decision || 'not_available',
      pha_outcome: acknowledgement?.status || submission?.status || 'not_available',
      correction_reason: [...(submission?.errors || []), ...(validation?.errors || [])].filter(Boolean).join('; ') || review?.payload?.comments || 'not_available',
      validation_status: validation?.status || (validation?.valid === true ? 'VALID' : validation?.valid === false ? 'INVALID' : 'not_available'),
      validation_errors: validation?.errors || [],
      submission_errors: submission?.errors || [],
      acknowledgement_id: acknowledgement?.acknowledgement_id || submission?.acknowledgement_id || null,
      disease: item.disease,
      jurisdiction: item.jurisdiction,
      evidence: candidate?.evidence || [],
      confidence: candidate?.confidence ?? null,
      status: review ? decision : submission?.status || item.status || 'not_available',
      timestamp: review?.created_at || submission?.created_at || item.updated_at,
      submission_simulated: submission?.destination === 'MOCK_PHA',
    }
  })
  const reviewed = rows.filter(item => item.reviewer_decision !== 'not_available')
  const insights = buildEvidencePatterns(rows)
  return {
    rows,
    insights,
    overview: {
      analyzed: cases.length,
      feedback: reviewed.length,
      pha: rows.filter(item => item.pha_outcome === 'ACKNOWLEDGED').length,
      analysis: insights.length,
      status: reviewed.length ? 'observed_outcomes_available' : 'insufficient_data',
    },
  }
}

const governanceService = {
  async getAgents() {
    const agents = await getAgentStatus()
    return agents.map(agent => ({
      agent_id: agent.agent_name,
      name: label(agent.agent_name),
      purpose: agent.description,
      description: agent.description,
      version: 'not_available',
      model: 'not_available',
      status: agent.available ? 'AVAILABLE' : 'UNAVAILABLE',
      owner: 'not_available',
      monitoring_status: agent.configured ? 'CONFIGURED' : 'NOT_CONFIGURED',
      evaluation_status: 'NOT_EVALUATED',
      governance_status: agent.simulated ? 'SIMULATED' : 'NOT_EVALUATED',
      configured: agent.configured,
      simulated: agent.simulated,
      error: agent.error,
      last_execution: agent.last_execution,
    }))
  },
  async getAgent(agentId) { return (await this.getAgents()).find(item => item.agent_id === agentId) || null },
  async getAuditEvents(filters = {}) {
    const [audit, cases, submissions] = await Promise.all([getAuditLedger(), allPages('/api/cases'), allPages('/api/submissions')])
    const caseToCandidate = new Map(cases.map(item => [item.case_id, item.candidate_id]))
    const submissionToCandidate = new Map(submissions.map(item => [item.submission_id, caseToCandidate.get(item.case_id)]))
    return audit.filter(event => {
      const agent = event.source_agent || ''
      const candidateId = event.entity_type === 'CANDIDATE'
        ? event.entity_id
        : event.entity_type === 'CASE'
          ? caseToCandidate.get(event.entity_id) || ''
          : event.entity_type === 'SUBMISSION'
            ? submissionToCandidate.get(event.entity_id) || ''
            : ''
      return (!filters.agent_id || agent === filters.agent_id) &&
        (!filters.candidate_id || candidateId.toLowerCase().includes(filters.candidate_id.toLowerCase())) &&
        (!filters.status || event.status === filters.status) &&
        (!filters.agent_version || false) &&
        (!filters.started_after || Date.parse(event.event_timestamp) >= Date.parse(filters.started_after)) &&
        (!filters.started_before || Date.parse(event.event_timestamp) <= Date.parse(filters.started_before))
    }).map(event => ({
      execution_id: event.audit_id,
      audit_id: event.audit_id,
      agent_id: event.source_agent,
      candidate_id: event.entity_type === 'CANDIDATE' ? event.entity_id : event.entity_type === 'CASE' ? caseToCandidate.get(event.entity_id) || null : event.entity_type === 'SUBMISSION' ? submissionToCandidate.get(event.entity_id) || null : null,
      entity_type: event.entity_type,
      entity_id: event.entity_id,
      started_at: event.event_timestamp,
      status: event.status,
      latency_ms: null,
      model: null,
      agent_version: null,
      input_source: event.metadata?.source_reference || null,
      output_type: event.event_type,
      error: event.status === 'FAILURE' ? event.description : null,
      action: event.event_type,
      actor: event.actor_id,
      timestamp: event.event_timestamp,
      detail: auditDetail(event),
    }))
  },
  async getAuditSummary() { return getAuditSummary() },
  async getExecutions(filters = {}) { return this.getAuditEvents(filters) },
  async getExecution(id) { return (await this.getAuditEvents()).find(item => item.audit_id === id) || null },
  async getEvaluations() { return [] },
  async getEvaluation() { return null },
  async getEvaluationReadiness() {
    const [candidates, outcome] = await Promise.all([allPages('/api/candidates'), buildOutcomeData()])
    const relevant = candidates.filter(item => relevantDisease(item.disease))
    const outcomeByCandidate = new Map(outcome.rows.map(row => [row.candidate_id, row]))
    return {
      ...buildEvaluationReadiness(relevant, outcome.overview.feedback),
      records: relevant.map(candidate => {
        const caseOutcome = outcomeByCandidate.get(candidate.candidate_id)
        return {
          candidate_id: candidate.candidate_id,
          confidence: candidate.confidence,
          candidate_status: candidate.status,
          reviewer_decision: caseOutcome?.reviewer_decision || 'not_available',
          reportability_decision: caseOutcome?.reportability_decision || 'not_available',
          pha_outcome: caseOutcome?.pha_outcome || 'not_available',
        }
      }),
    }
  },
  async getEvidenceTraces() {
    const data = await getSourceData()
    const audits = data.audit.filter(item => item.entity_type === 'CANDIDATE')
    const submissionsByCase = new Map()
    data.submissions.forEach(item => {
      const previous = submissionsByCase.get(item.case_id)
      if (!previous || Date.parse(item.created_at) > Date.parse(previous.created_at)) submissionsByCase.set(item.case_id, item)
    })
    return Promise.all(data.candidates.filter(item => relevantDisease(item.disease)).map(async candidate => {
      const events = audits.filter(item => item.entity_id === candidate.candidate_id)
      const sourceEvidence = candidate.evidence || []
      const context = await getCaseContext(candidate.case_id)
      const caseRecord = context?.caseRecord
      const review = context?.review
      const submission = candidate.case_id ? submissionsByCase.get(candidate.case_id) : null
      const acknowledgement = await getAcknowledgement(submission?.submission_id)
      const caseAudit = candidate.case_id ? data.audit.filter(item => item.entity_type === 'CASE' && item.entity_id === candidate.case_id) : []
      return {
        candidate_id: candidate.candidate_id,
        execution_id: events[0]?.audit_id || null,
        agent_id: events[0]?.source_agent || null,
        agent_version: null,
        source: {
          name: sourceEvidence.map(item => item.display).filter(Boolean).join(', ') || 'not_available',
          type: [...new Set(sourceEvidence.map(item => item.source_type).filter(Boolean))].join(', ') || 'not_available',
          timestamp: candidate.created_at,
          reference: sourceEvidence.map(item => item.source_id).filter(Boolean).join(', ') || null,
        },
        evidence: sourceEvidence.map(item => ({ text: item.display || item.code || item.source_type || 'Evidence', reference: item.source_id || null, timestamp: candidate.created_at })),
        candidate: { status: candidate.status, patient_id: candidate.patient_id, disease: candidate.disease, jurisdiction: candidate.jurisdiction, case_id: candidate.case_id },
        output: { type: candidate.status, reference: candidate.candidate_id, confidence: candidate.confidence },
        confidence: candidate.confidence,
        case: caseRecord ? {
          case_id: caseRecord.case_id,
          status: caseRecord.status,
          reportability_decision: caseRecord.final_decision || caseRecord.reportability_decision,
          jurisdiction: caseRecord.jurisdiction,
          evidence: { clinical: caseRecord.clinical_evidence, laboratory: caseRecord.laboratory_evidence, ai: caseRecord.ai_evidence },
          validation: context?.validation || null,
        } : null,
        human_decision: review ? { status: reviewDecision(review), reviewer: review.payload?.reviewer_id || review.actor_id || null, role: review.payload?.reviewer_role || null, comments: review.payload?.comments || null, timestamp: review.created_at } : { status: 'not_available', reviewer: null, timestamp: null },
        outcome: submission ? { status: acknowledgement?.status || submission.status, reference: submission.submission_id, acknowledgement_id: acknowledgement?.acknowledgement_id || submission.acknowledgement_id || null, errors: submission.errors || [], destination: submission.destination } : caseRecord ? { status: caseRecord.status, reference: caseRecord.case_id, timestamp: caseRecord.updated_at } : { status: 'not_available', reference: null },
        last_case_activity: caseAudit[0]?.event_timestamp || null,
      }
    }))
  },
  async getGovernanceFindings() {
    const candidates = await allPages('/api/candidates')
    return findGovernanceIssues(candidates.filter(item => relevantDisease(item.disease)))
  },
  async getEvidenceTrace(candidateId) { return (await this.getEvidenceTraces()).find(item => item.candidate_id === candidateId) || null },
  async getGovernanceOverview() {
    const data = await getSourceData()
    const relevant = data.candidates.filter(item => relevantDisease(item.disease))
    const audit = data.auditSummary || {}
    const configured = data.agents.filter(item => item.configured).length
    return {
      registered_agents: data.agents.length,
      active_agents: data.agents.filter(item => item.available).length,
      recent_executions: audit.total ?? data.audit.length,
      execution_failures: audit.failure ?? data.audit.filter(item => item.status === 'FAILURE').length,
      successful_executions: audit.success ?? data.audit.filter(item => item.status === 'SUCCESS').length,
      evaluation_runs: null,
      agents_requiring_review: data.agents.filter(item => !item.configured || item.simulated).length,
      explainability_coverage: relevant.filter(item => (item.evidence || []).length > 0).length,
      outcome_learning_signals: data.cases.filter(item => relevantDisease(item.disease) && isTexas(item.jurisdiction)).length,
      configured_agents: configured,
      data_label: 'Live backend component status, persisted patient/case records, and workflow audit events',
    }
  },
}

const outcomeLearningService = {
  async getDashboard() { return buildOutcomeData() },
  async getOverview() { return (await buildOutcomeData()).overview },
  async getLearningSignals() { return (await buildOutcomeData()).rows },
  async getInsights() { return (await buildOutcomeData()).insights },
  async getLearningSignal(id) { return (await buildOutcomeData()).rows.find(item => item.id === id) || null },
}

export { governanceService, outcomeLearningService }
export const aiGovernanceService = governanceService
