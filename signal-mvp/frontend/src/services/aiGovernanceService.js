const agents = [
  { id:'document-intelligence', name:'Document Intelligence', purpose:'Extract relevant information from clinical documents.', version:'Model v2.1', status:'Healthy', lastRun:'09:44', executions:'386', success:'98.8%', latency:'1.8s', monitoring:'Monitored', governance:'Governed', owner:'Clinical AI team', evaluation:'Sep 25, 2026' },
  { id:'nlp-evidence', name:'NLP Evidence', purpose:'Identify and structure clinical evidence from text.', version:'Model v1.4', status:'Healthy', lastRun:'09:42', executions:'312', success:'98.4%', latency:'0.9s', monitoring:'Monitored', governance:'Governed', owner:'Clinical AI team', evaluation:'Sep 25, 2026' },
  { id:'candidate-fusion', name:'Candidate Fusion', purpose:'Combine signals from multiple sources into a reporting candidate.', version:'Model v1.1', status:'Warning', lastRun:'09:40', executions:'284', success:'96.1%', latency:'1.2s', monitoring:'Monitored', governance:'Evaluation Pending', owner:'Reporting intelligence team', evaluation:'Pending' },
  { id:'cluster-signal', name:'Cluster Signal', purpose:'Identify potential related signals or clusters.', version:'Model v0.9', status:'Healthy', lastRun:'09:37', executions:'266', success:'97.3%', latency:'2.1s', monitoring:'Monitored', governance:'Governed', owner:'Public health analytics team', evaluation:'Sep 24, 2026' },
]
const outcomes = [
  { id:'LS-001', case:'CAND-001', ai:'Reportable', reviewer:'Reportable', pha:'Accepted', difference:'No significant difference', signal:'Correct reporting recommendation', status:'Validated' },
  { id:'LS-002', case:'CAND-002', ai:'Reportable', reviewer:'Not Reportable', pha:'Not Submitted', difference:'Potential false positive', signal:'Potential false positive pattern', status:'Under Review' },
  { id:'LS-003', case:'CAND-003', ai:'Not Reportable', reviewer:'Reportable', pha:'Accepted', difference:'Potential missed signal', signal:'Potential missed signal', status:'Under Review' },
]
export const aiGovernanceService = {
  getOverview: async()=>({ active:6, executions:1248, successful:1217, attention:8, humanReview:'34%', evaluation:'Current', agents }),
  getAgents: async()=>agents,
  getAgent: async(id)=>agents.find(a=>a.id===id)||agents[0],
  getMonitoringData: async()=>agents,
  getEvaluationData: async()=>agents,
  getAuditHistory: async()=>[['09:31','NLP Evidence','Executed','Model v1.4','Evidence extracted','System'],['09:32','Candidate Fusion','Executed','Model v1.1','Candidate generated','System'],['09:35','Reviewer','Reviewed AI evidence','Human reviewer','Verified','Sarah Mitchell']],
}
export const outcomeLearningService = {
  getOverview: async()=>({ analyzed:'4,280', feedback:'3,912', pha:'2,846', agreement:'91%', analysis:'126' }),
  getLearningSignals: async()=>outcomes,
  getLearningSignal: async(id)=>outcomes.find(o=>o.id===id)||outcomes[0],
}
