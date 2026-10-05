/**
 * Demo adapter for the SIGNAL governance API. Replace these collections with
 * API calls without changing the governance screens. Optional fields are
 * intentionally supported so newly registered agents can be rendered safely.
 * @typedef {{agent_id:string,name:string,purpose?:string,description?:string,version?:string,model?:string,status?:string,owner?:string,monitoring_status?:string,evaluation_status?:string,governance_status?:string,[key:string]:unknown}} Agent
 * @typedef {{execution_id:string,agent_id:string,agent_version?:string,candidate_id?:string,started_at:string,completed_at?:string,status:string,latency_ms?:number,model?:string,input_source?:string,output_type?:string,error?:string|null,[key:string]:unknown}} AgentExecution
 * @typedef {{evaluation_run_id:string,agent_id:string,model?:string,version?:string,dataset?:string,timestamp?:string,metrics?:Record<string,number>,synthetic?:boolean,[key:string]:unknown}} EvaluationRun
 */
const agents = [
  { agent_id:'document-intelligence', name:'Document Intelligence Agent', description:'Extracts structured information from clinical documents.', purpose:'Document extraction', version:'1.2', model:'SIGNAL Document Model', status:'ACTIVE', owner:'SIGNAL AI Team', monitoring_status:'HEALTHY', evaluation_status:'AVAILABLE', governance_status:'COMPLIANT' },
  { agent_id:'nlp-evidence', name:'NLP Evidence Agent', description:'Identifies and structures clinical evidence from text.', purpose:'Clinical evidence extraction', version:'1.4', model:'SIGNAL Clinical NLP', status:'ACTIVE', owner:'SIGNAL AI Team', monitoring_status:'HEALTHY', evaluation_status:'AVAILABLE', governance_status:'COMPLIANT' },
  { agent_id:'candidate-fusion', name:'Candidate Fusion Agent', description:'Combines signals from multiple sources into a reporting candidate.', purpose:'Candidate fusion', version:'1.1', model:'SIGNAL Fusion Model', status:'ACTIVE', owner:'Reporting Intelligence', monitoring_status:'DEGRADED', evaluation_status:'REVIEW_REQUIRED', governance_status:'REVIEW_REQUIRED' },
  { agent_id:'cluster-signal', name:'Cluster Signal Agent', description:'Identifies potential related signals or clusters.', purpose:'Signal clustering', version:'0.9', model:'SIGNAL Cluster Model', status:'ACTIVE', owner:'Public Health Analytics', monitoring_status:'HEALTHY', evaluation_status:'NOT_AVAILABLE', governance_status:'IN_REVIEW' },
  { agent_id:'reportability', name:'Reportability Agent', purpose:'Assists with jurisdiction-specific reportability assessment.', version:'1.0', model:'SIGNAL Rules + ML', status:'ACTIVE', owner:'SIGNAL AI Team', monitoring_status:'HEALTHY', evaluation_status:'NOT_AVAILABLE', governance_status:'IN_REVIEW' },
  { agent_id:'smart-field-population', name:'Smart Field Population Agent', purpose:'Maps source-backed information to reporting fields.', version:'1.0', model:'SIGNAL Field Mapper', status:'ACTIVE', owner:'SIGNAL AI Team', monitoring_status:'HEALTHY', evaluation_status:'NOT_AVAILABLE', governance_status:'IN_REVIEW' },
]

const executions = [
  { execution_id:'EXE-10231',agent_id:'nlp-evidence',agent_version:'1.4',candidate_id:'CAND-001',started_at:'2026-09-29T09:31:00+05:30',completed_at:'2026-09-29T09:31:02+05:30',status:'SUCCESS',latency_ms:2100,model:'SIGNAL Clinical NLP 1.4',input_source:'clinical_note',output_type:'clinical_evidence',error:null },
  { execution_id:'EXE-10232',agent_id:'candidate-fusion',agent_version:'1.1',candidate_id:'CAND-002',started_at:'2026-09-29T09:34:00+05:30',completed_at:'2026-09-29T09:34:02+05:30',status:'FAILURE',latency_ms:1800,model:'SIGNAL Fusion Model 1.1',input_source:'ehr_and_elr',output_type:'candidate_match',error:'Conflicting patient identifiers; review required.' },
  { execution_id:'EXE-10233',agent_id:'document-intelligence',agent_version:'1.2',candidate_id:'CAND-003',started_at:'2026-09-29T09:38:00+05:30',completed_at:'2026-09-29T09:38:02+05:30',status:'SUCCESS',latency_ms:2400,model:'SIGNAL Document Model 1.2',input_source:'clinical_document',output_type:'structured_document_fields',error:null },
  { execution_id:'EXE-10234',agent_id:'reportability',agent_version:'1.0',candidate_id:'CAND-001',started_at:'2026-09-29T09:40:00+05:30',completed_at:'2026-09-29T09:40:01+05:30',status:'SUCCESS',latency_ms:950,model:'SIGNAL Rules + ML 1.0',input_source:'candidate_record',output_type:'reportability_assessment',error:null },
  { execution_id:'EXE-10235',agent_id:'smart-field-population',agent_version:'1.0',candidate_id:'CAND-004',started_at:'2026-09-29T09:42:00+05:30',completed_at:'2026-09-29T09:42:02+05:30',status:'SUCCESS',latency_ms:1600,model:'SIGNAL Field Mapper 1.0',input_source:'verified_evidence',output_type:'reporting_field_mapping',error:null },
]

const evaluations = [
  { evaluation_run_id:'EVAL-2026-0925-01',agent_id:'nlp-evidence',model:'SIGNAL Clinical NLP',version:'1.4',dataset:'Synthetic Public Health Evaluation Set',timestamp:'2026-09-25T14:00:00+05:30',metrics:{precision:0.94,recall:0.91,f1:0.92,accuracy:0.93},synthetic:true },
  { evaluation_run_id:'EVAL-2026-0924-02',agent_id:'document-intelligence',model:'SIGNAL Document Model',version:'1.2',dataset:'Synthetic Document Extraction Set',timestamp:'2026-09-24T11:30:00+05:30',metrics:{precision:0.92,recall:0.9,f1:0.91},synthetic:true },
]

const evidenceTraces = [
  { candidate_id:'CAND-001',execution_id:'EXE-10231',source:{name:'Clinical Note',type:'EHR',timestamp:'2026-09-16T10:12:00+05:30',reference:'DOC-CLN-001'},evidence:[{text:'Fever for 3 days',reference:'DOC-CLN-001#p1',timestamp:'2026-09-16T10:12:00+05:30'},{text:'Maculopapular rash',reference:'DOC-CLN-001#p2',timestamp:'2026-09-16T10:12:00+05:30'}],agent_id:'nlp-evidence',agent_version:'1.4',output:{type:'Potential reportable measles candidate',reference:'OUT-001'},human_decision:{status:'PENDING',reviewer:'',timestamp:''},outcome:{status:'PENDING',reference:''} },
  { candidate_id:'CAND-003',execution_id:'EXE-10233',source:{name:'Uploaded Clinical Summary',type:'Document',timestamp:'2026-09-17T09:15:00+05:30',reference:'DOC-UP-003'},evidence:[{text:'Positive laboratory result documented',reference:'DOC-UP-003#p1',timestamp:'2026-09-17T09:15:00+05:30'}],agent_id:'document-intelligence',agent_version:'1.2',output:{type:'Structured evidence available',reference:'OUT-003'},human_decision:{status:'CONFIRMED',reviewer:'Sarah Mitchell',timestamp:'2026-09-17T10:02:00+05:30'},outcome:{status:'UNDER_REVIEW',reference:'PHA-CASE-003'} },
]

const auditEvents = [
  { timestamp:'2026-09-29T09:31:02+05:30',agent_id:'nlp-evidence',agent_version:'1.4',execution_id:'EXE-10231',candidate_id:'CAND-001',actor:'System',action:'Execution completed',detail:'Clinical evidence emitted from source DOC-CLN-001.' },
  { timestamp:'2026-09-29T09:34:02+05:30',agent_id:'candidate-fusion',agent_version:'1.1',execution_id:'EXE-10232',candidate_id:'CAND-002',actor:'System',action:'Execution failed',detail:'Conflicting patient identifiers.' },
  { timestamp:'2026-09-17T10:02:00+05:30',agent_id:'document-intelligence',agent_version:'1.2',execution_id:'EXE-10233',candidate_id:'CAND-003',actor:'Sarah Mitchell',action:'Evidence confirmed',detail:'Human verification recorded.' },
]

const outcomeSignals = [
  { id:'LS-001',candidate_id:'CAND-001',agent_id:'nlp-evidence',ai_output:'Potentially reportable',clinical_staff_decision:'Pending',reporting_admin_decision:'Pending',pha_outcome:'Pending',correction_reason:'',signal:'Outcome not yet available',status:'Observed',timestamp:'2026-09-29T09:31:02+05:30' },
  { id:'LS-002',candidate_id:'CAND-002',agent_id:'candidate-fusion',ai_output:'Candidate match',clinical_staff_decision:'Reviewed',reporting_admin_decision:'Returned for correction',pha_outcome:'Not submitted',correction_reason:'Conflicting identifiers require correction.',signal:'Potential identity-resolution issue',status:'Under Review',timestamp:'2026-09-28T16:20:00+05:30' },
  { id:'LS-003',candidate_id:'CAND-003',agent_id:'document-intelligence',ai_output:'Evidence extracted',clinical_staff_decision:'Confirmed',reporting_admin_decision:'Verified',pha_outcome:'Acknowledged',correction_reason:'',signal:'Outcome validated against review',status:'Applied to Evaluation',timestamp:'2026-09-27T12:10:00+05:30' },
]

const copy = value => structuredClone(value)
const agentById = id => agents.find(agent => agent.agent_id === id)
const matches = (item, filters = {}) => Object.entries(filters).every(([key,value]) => {
  if (!value) return true
  if (key === 'started_after') return Date.parse(item.started_at) >= Date.parse(value)
  if (key === 'started_before') return Date.parse(item.started_at) <= Date.parse(value)
  return String(item[key] ?? '').toLowerCase().includes(String(value).toLowerCase())
})

export const governanceService = {
  async getAgents(filters) { return copy(agents.filter(agent => matches(agent,filters))) },
  async getAgent(agentId) { return copy(agentById(agentId) || null) },
  async getExecutions(filters = {}) { return copy(executions.filter(item => matches(item,filters))) },
  async getExecution(executionId) { return copy(executions.find(item => item.execution_id === executionId) || null) },
  async getEvaluations(filters = {}) { return copy(evaluations.filter(item => matches(item,filters))) },
  async getEvaluation(evaluationRunId) { return copy(evaluations.find(item => item.evaluation_run_id === evaluationRunId) || null) },
  async getEvidenceTrace(candidateId, executionId) { return copy(evidenceTraces.find(item => (!candidateId || item.candidate_id === candidateId) && (!executionId || item.execution_id === executionId)) || null) },
  async getEvidenceTraces() { return copy(evidenceTraces) },
  async getOutcomeSignals(filters = {}) { return copy(outcomeSignals.filter(item => matches(item,filters))) },
  async getOutcomeSignal(id) { return copy(outcomeSignals.find(item => item.id === id) || null) },
  async getAuditEvents(filters = {}) { return copy(auditEvents.filter(item => matches(item,filters))) },
  async getGovernanceOverview() {
    const successful = executions.filter(item => item.status === 'SUCCESS').length
    const attentionAgents = agents.filter(agent => ['DEGRADED','REVIEW_REQUIRED','IN_REVIEW'].includes(agent.monitoring_status) || ['REVIEW_REQUIRED','IN_REVIEW'].includes(agent.governance_status)).length
    return { registered_agents:agents.length,active_agents:agents.filter(agent => agent.status === 'ACTIVE').length,recent_executions:executions.length,execution_failures:executions.filter(item => item.status === 'FAILURE').length,successful_executions:successful,evaluation_runs:evaluations.length,agents_requiring_review:attentionAgents,explainability_coverage:evidenceTraces.length,outcome_learning_signals:outcomeSignals.length,data_label:'Demo / Synthetic Data' }
  },
}

// Backwards-compatible named adapters used by the existing governance screens.
export const aiGovernanceService = {
  getOverview: () => governanceService.getGovernanceOverview(),
  getAgents: () => governanceService.getAgents(),
  getAgent: id => governanceService.getAgent(id),
  getMonitoringData: () => governanceService.getAgents(),
  getEvaluationData: () => governanceService.getAgents(),
  getAuditHistory: async () => (await governanceService.getAuditEvents()).map(event => [new Date(event.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),agentById(event.agent_id)?.name || event.agent_id,event.action,event.agent_version,event.detail,event.actor]),
}
export const outcomeLearningService = {
  getOverview: async () => { const rows=await governanceService.getOutcomeSignals();return { analyzed:String(rows.length),feedback:String(rows.filter(row=>row.clinical_staff_decision!=='Pending').length),pha:String(rows.filter(row=>row.pha_outcome==='Acknowledged').length),agreement:'Evaluation required',analysis:String(rows.filter(row=>['Observed','Under Review'].includes(row.status)).length) } },
  getLearningSignals: () => governanceService.getOutcomeSignals(),
  getLearningSignal: id => governanceService.getOutcomeSignal(id),
}
