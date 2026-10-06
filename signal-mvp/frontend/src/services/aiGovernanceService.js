import { request } from '../api/client.js'
import { buildEvaluationReadiness, buildEvidencePatterns, findGovernanceIssues } from './governanceAnalysis.js'

const allPages = async (path, pageSize = 100) => {
  const first = await request(`${path}?page=1&page_size=${pageSize}`)
  const items = [...(first.items || [])]
  const pages = first.pages || Math.ceil((first.total || 0) / pageSize)
  for (let page = 2; page <= pages; page += 1) {
    const next = await request(`${path}?page=${page}&page_size=${pageSize}`)
    items.push(...(next.items || []))
  }
  return items
}

const getSourceData = async () => {
  const [candidateRows, caseRows, submissions, audit, status] = await Promise.all([
    allPages('/api/candidates'),
    allPages('/api/cases'),
    allPages('/api/submissions'),
    request('/api/audit/events'),
    request('/api/agents/status'),
  ])
  return { candidates: candidateRows, cases: caseRows, submissions, audit, agents: status.agents || [] }
}
const getAgentStatus = async () => (await request('/api/agents/status')).agents || []
const getAuditLedger = async () => request('/api/audit/events')

const label = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
const findCandidate = (data, id) => data.candidates.find(item => item.candidate_id === id)
const relevantDisease = value => String(value || '').toLowerCase().includes('measles')
const isTexas = value => /texas|\btx\b/i.test(String(value || ''))

async function buildOutcomeData() {
  const data = await getSourceData()
  const cases = data.cases.filter(item => relevantDisease(item.disease) && isTexas(item.jurisdiction))
  const submissionsByCase = new Map()
  data.submissions.forEach(item => {
    const previous = submissionsByCase.get(item.case_id)
    if (!previous || Date.parse(item.created_at) > Date.parse(previous.created_at)) submissionsByCase.set(item.case_id, item)
  })
  const reviewResults = await Promise.all(cases.map(async item => {
    try { return [item.case_id, await request(`/api/cases/${encodeURIComponent(item.case_id)}/review`)] }
    catch { return [item.case_id, null] }
  }))
  const reviews = new Map(reviewResults)
  const rows = cases.map(item => {
    const review = reviews.get(item.case_id)
    const candidate = findCandidate(data, item.candidate_id)
    const submission = submissionsByCase.get(item.case_id)
    const decision = review?.payload?.decision || review?.status || 'not_available'
    return {
      id: item.case_id,
      candidate_id: item.candidate_id,
      agent_id: candidate?.detection_source || 'candidate_fusion',
      ai_output: candidate?.status || 'not_available',
      clinical_staff_decision: review?.payload?.reviewer_role === 'Clinical Staff' ? decision : 'not_available',
      reporting_admin_decision: review?.payload?.reviewer_role === 'Reporting Administrator' ? decision : 'not_available',
      reviewer_decision: decision,
      review_reason: review?.payload?.comments || 'not_available',
      reportability_decision: item.final_decision || item.reportability_decision || 'not_available',
      pha_outcome: submission?.status || 'not_available',
      correction_reason: submission?.errors?.join('; ') || review?.payload?.comments || 'not_available',
      disease: item.disease,
      jurisdiction: item.jurisdiction,
      evidence: candidate?.evidence || [],
      status: review ? decision : submission?.status || item.status || 'not_available',
      timestamp: review?.created_at || submission?.created_at || item.updated_at,
      submission_simulated: submission?.destination === 'MOCK_PHA',
    }
  })
  const reviewed = rows.filter(item => item.reviewer_decision !== 'not_available')
  const insights = buildEvidencePatterns(reviewed)
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
    const audit = await getAuditLedger()
    return audit.filter(event => {
      const agent = event.source_agent || ''
      const candidateId = event.entity_type === 'CANDIDATE' ? event.entity_id : ''
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
      candidate_id: event.entity_type === 'CANDIDATE' ? event.entity_id : null,
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
      detail: event.description || JSON.stringify(event.new_value || {}),
    }))
  },
  async getExecutions(filters = {}) { return this.getAuditEvents(filters) },
  async getExecution(id) { return (await this.getAuditEvents()).find(item => item.audit_id === id) || null },
  async getEvaluations() { return [] },
  async getEvaluation() { return null },
  async getEvaluationReadiness() {
    const [candidates, outcome] = await Promise.all([allPages('/api/candidates'), buildOutcomeData()])
    return buildEvaluationReadiness(candidates.filter(item => relevantDisease(item.disease)), outcome.overview.feedback)
  },
  async getEvidenceTraces() {
    const data = await getSourceData()
    const audits = data.audit.filter(item => item.entity_type === 'CANDIDATE')
    return data.candidates.filter(item => relevantDisease(item.disease)).map(candidate => {
      const events = audits.filter(item => item.entity_id === candidate.candidate_id)
      const sourceEvidence = candidate.evidence || []
      return {
        candidate_id: candidate.candidate_id,
        execution_id: events[0]?.audit_id || null,
        agent_id: events[0]?.source_agent || 'candidate_fusion',
        agent_version: null,
        source: {
          name: sourceEvidence.map(item => item.display).filter(Boolean).join(', ') || 'FHIR source record',
          type: [...new Set(sourceEvidence.map(item => item.source_type).filter(Boolean))].join(', ') || 'FHIR',
          timestamp: candidate.created_at,
          reference: sourceEvidence.map(item => item.source_id).filter(Boolean).join(', ') || candidate.patient_id,
        },
        evidence: sourceEvidence.map(item => ({ text: item.display || item.code || item.source_type || 'Evidence', reference: item.source_id || null, timestamp: candidate.created_at })),
        output: { type: candidate.status, reference: candidate.candidate_id },
        human_decision: { status: 'not_available', reviewer: 'not_available', timestamp: null },
        outcome: { status: candidate.case_id ? 'case_created' : 'not_available', reference: candidate.case_id || null },
      }
    })
  },
  async getGovernanceFindings() {
    const candidates = await allPages('/api/candidates')
    return findGovernanceIssues(candidates.filter(item => relevantDisease(item.disease)))
  },
  async getEvidenceTrace(candidateId) { return (await this.getEvidenceTraces()).find(item => item.candidate_id === candidateId) || null },
  async getGovernanceOverview() {
    const data = await getSourceData()
    const relevant = data.candidates.filter(item => relevantDisease(item.disease))
    const audit = data.audit.filter(item => ['candidate_fusion', 'document_intelligence', 'nlp_evidence', 'reportability_workflow', 'candidate_disposition'].includes(item.source_agent))
    const configured = data.agents.filter(item => item.configured).length
    return {
      registered_agents: data.agents.length,
      active_agents: data.agents.filter(item => item.available).length,
      recent_executions: audit.length,
      execution_failures: audit.filter(item => item.status === 'FAILURE').length,
      successful_executions: audit.filter(item => item.status === 'SUCCESS').length,
      evaluation_runs: null,
      agents_requiring_review: data.agents.filter(item => !item.configured || item.simulated).length,
      explainability_coverage: relevant.filter(item => (item.evidence || []).length > 0).length,
      outcome_learning_signals: data.cases.filter(item => relevantDisease(item.disease) && isTexas(item.jurisdiction)).length,
      configured_agents: configured,
      data_label: 'Live backend status, FHIR-derived candidate records, and persisted audit events',
    }
  },
}

const outcomeLearningService = {
  async getOverview() { return (await buildOutcomeData()).overview },
  async getLearningSignals() { return (await buildOutcomeData()).rows },
  async getInsights() { return (await buildOutcomeData()).insights },
  async getLearningSignal(id) { return (await buildOutcomeData()).rows.find(item => item.id === id) || null },
}

export { governanceService, outcomeLearningService }
export const aiGovernanceService = governanceService
