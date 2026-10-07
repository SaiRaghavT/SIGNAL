import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { Activity, ArrowRight } from 'lucide-react'
import { governanceService, outcomeLearningService } from '../services/aiGovernanceService.js'

function useLoad(loader, dependencies = []) {
  const [state, setState] = useState({ data: null, error: '' })
  useEffect(() => {
    let alive = true
    loader().then(data => { if (alive) setState({ data, error: '' }) }).catch(error => { if (alive) setState({ data: null, error: error.message || 'Unable to retrieve SIGNAL records.' }) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)
  return state
}

// Outcome Learning stays implemented and routable, but is hidden from the current navigation.
const links = [['Overview','/governance'],['AI Monitoring','/governance/monitoring'],['Model Evaluation','/governance/evaluation'],['Explainability','/governance/explainability'],['Agent Governance','/governance/agents']]
const field = value => value === undefined || value === null || value === '' || value === 'not_available' ? '—' : String(value)
const dateTime = value => value ? new Date(value).toLocaleString() : '—'

function GovLayout({ title, sub, children }) {
  const { pathname } = useLocation()
  return <div className="page"><div className="page-heading"><div><h1>{title}</h1><p>{sub}</p></div></div><div className="gov-tabs">{links.map(([name,path]) => <Link key={path} to={path} className={pathname === path ? 'selected' : ''}>{name}</Link>)}</div>{children}</div>
}
function ErrorNote({ error }) { return error ? <div className="alert-banner" role="alert">{error}</div> : null }
function Metric({ label, value, note }) { if (value == null || value === '' || value === 'not_available') return null; return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small><Activity className="metric-spark" size={18}/></div> }
function Status({ children }) { if (!children || children === 'not_available') return <span>—</span>; const key = String(children).toLowerCase().replaceAll(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,''); return <span className={`badge ${key}`}>{children}</span> }
function Table({ headers, rows, empty = 'No records available.' }) { return <section className="panel"><div className="table-wrapper"><table><thead><tr>{headers.map(header => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows}</tbody></table></div>{!rows.length && <div className="note">{empty}</div>}</section> }

export function GovernanceOverview() {
  const overview = useLoad(() => governanceService.getGovernanceOverview(), [])
  const agents = useLoad(() => governanceService.getAgents(), [])
  const findings = useLoad(() => governanceService.getGovernanceFindings(), [])
  const d = overview.data
  return <GovLayout title="AI Governance" sub="Status of SIGNAL workflow components and stored audit activity."><ErrorNote error={overview.error || agents.error || findings.error}/><div className="metrics-grid gov-metrics"><Metric label="WORKFLOW COMPONENTS" value={d?.registered_agents} note="Backend registered agents"/><Metric label="AVAILABLE" value={d?.active_agents} note="Currently available"/><Metric label="AUDIT EVENTS" value={d?.recent_executions} note="Persisted records"/><Metric label="CANDIDATES WITH EVIDENCE" value={d?.explainability_coverage} note="Stored candidate records"/></div><Table headers={['Component','Status','Configuration','Details']} rows={(agents.data || []).map(agent => <tr key={agent.agent_id}><td><b>{agent.name}</b><small>{agent.purpose || agent.description}</small></td><td><Status>{agent.status}</Status></td><td>{agent.configured ? 'Configured' : 'Not configured'}{agent.simulated ? ' · Simulated' : ''}</td><td><Link to={`/governance/agents/${agent.agent_id}`}>View <ArrowRight size={13}/></Link></td></tr>)} empty="No workflow component records are available."/>{findings.data?.length > 0 && <section className="panel"><div className="panel-header"><div><h3>Data checks</h3></div><small className="muted">{findings.data.length} findings</small></div>{findings.data.map((item,index) => <div className="source-row" key={`${item.candidate_id}-${item.reason}-${index}`}><b>{item.reason}</b><span>{item.disease} · {item.status}</span><Link to={`/candidates/${item.candidate_id}`}>Review candidate</Link></div>)}</section>}</GovLayout>
}

export function MonitoringPage() {
  const agents = useLoad(() => governanceService.getAgents(), [])
  const events = useLoad(() => governanceService.getExecutions(), [])
  const [filters, setFilters] = useState({ agent_id: '', status: '', candidate_id: '' })
  const allRows = events.data || []
  const rows = allRows.filter(row => (!filters.agent_id || row.agent_id === filters.agent_id) && (!filters.status || row.status === filters.status) && (!filters.candidate_id || (row.candidate_id || '').toLowerCase().includes(filters.candidate_id.toLowerCase())))
  const statuses = [...new Set(allRows.map(row => row.status).filter(Boolean))].sort()
  const update = (key, value) => setFilters(current => ({ ...current, [key]: value }))
  return <GovLayout title="AI Monitoring" sub="Recent audit activity from SIGNAL workflow components."><ErrorNote error={events.error || agents.error}/><div className="metrics-grid gov-metrics"><Metric label="AUDIT EVENTS" value={rows.length} note="Matching records"/><Metric label="SUCCESS" value={rows.filter(row => row.status === 'SUCCESS').length} note="Successful events"/><Metric label="FAILURES" value={rows.filter(row => row.status === 'FAILURE').length} note="Failed events"/></div><section className="panel pad gov-filters"><label>Component<select value={filters.agent_id} onChange={event => update('agent_id', event.target.value)}><option value="">All components</option>{(agents.data || []).map(agent => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}</select></label><label>Status<select value={filters.status} onChange={event => update('status', event.target.value)}><option value="">All statuses</option>{statuses.map(status => <option key={status}>{status}</option>)}</select></label><label>Candidate ID<input value={filters.candidate_id} onChange={event => update('candidate_id', event.target.value)} placeholder="Search candidate"/></label></section><Table headers={['Component','Candidate','Event','Status','Time']} rows={rows.map(row => <tr key={row.audit_id}><td>{row.agent_id || 'Unknown'}</td><td>{field(row.candidate_id)}</td><td>{row.output_type || row.action || '—'}</td><td><Status>{row.status}</Status></td><td>{dateTime(row.timestamp)}</td></tr>)} empty="No audit events match these filters."/></GovLayout>
}

export function EvaluationPage() {
  const state = useLoad(() => governanceService.getEvaluationReadiness(), [])
  const d = state.data
  const records = d?.records || []
  const reviewed = records.filter(row => row.reviewer_decision && row.reviewer_decision !== 'not_available')
  const confidence = d?.mean_confidence == null ? null : `${(d.mean_confidence * 100).toFixed(1)}%`
  return <GovLayout title="Model Evaluation" sub="Summary of persisted candidate and reviewer data."><ErrorNote error={state.error}/><div className="metrics-grid gov-metrics"><Metric label="CANDIDATES" value={d?.candidate_count} note="Persisted records"/><Metric label="WITH CONFIDENCE" value={d?.confidence_count} note="Stored confidence values"/><Metric label="MEAN CONFIDENCE" value={confidence} note="Descriptive only"/><Metric label="REVIEWED CASES" value={d?.reviewed_cases} note="Persisted reviews"/></div>{reviewed.length > 0 && <Table headers={['Candidate','Confidence','Reviewer outcome','Reportability','Submission']} rows={reviewed.map(row => <tr key={row.candidate_id}><td><Link to={`/candidates/${row.candidate_id}`}>{row.candidate_id}</Link></td><td>{row.confidence == null ? '—' : `${(Number(row.confidence) * 100).toFixed(1)}%`}</td><td>{row.reviewer_decision}</td><td>{field(row.reportability_decision)}</td><td>{field(row.pha_outcome)}</td></tr>)}/>}<p className="note">Model performance scores appear when labeled reviewer outcomes are available.</p></GovLayout>
}

export function ExplainabilityPage() {
  const state = useLoad(() => governanceService.getEvidenceTraces(), [])
  const traces = state.data || []
  const [selected, setSelected] = useState('')
  const trace = traces.find(item => item.candidate_id === selected) || traces[0]
  const detailRows = trace ? [
    ['Patient', trace.candidate?.patient_id], ['Condition', trace.candidate?.disease], ['Candidate status', trace.output?.type],
    ['Source', trace.source?.name], ['Source reference', trace.source?.reference], ['Detection component', trace.agent_id],
    ['Confidence', trace.confidence], ['Linked case', trace.case?.case_id || trace.candidate?.case_id],
    ['Human review', trace.human_decision?.status], ['Reportability', trace.case?.reportability_decision], ['Submission status', trace.outcome?.status],
  ].filter(([, value]) => value != null && value !== '' && value !== 'not_available') : []
  const evidence = trace?.evidence || []
  return <GovLayout title="Explainability" sub="View source evidence and decisions linked to a candidate.">
    <ErrorNote error={state.error}/>
    {traces.length > 0 && <section className="panel pad gov-filters"><label>Candidate<select value={trace?.candidate_id || ''} onChange={event => setSelected(event.target.value)}>{traces.map(item => <option key={item.candidate_id} value={item.candidate_id}>{item.candidate_id}</option>)}</select></label></section>}
    {trace ? <div>
      <Table headers={['Field','Persisted value']} rows={detailRows.map(([label,value]) => <tr key={label}><td>{label}</td><td>{field(value)}</td></tr>)} empty="No linked case or source detail is available."/>
      {evidence.length > 0 && <Table headers={['Evidence','Source']} rows={evidence.map((item,index) => <tr key={`${item.reference || item.text}-${index}`}><td>{item.text || item.display || 'Evidence record'}</td><td>{item.reference || item.source_type || '—'}</td></tr>)}/>}
    </div> : <div className="panel pad">No candidate evidence is available.</div>}
  </GovLayout>
}

export function AgentGovernancePage() {
  const agents = useLoad(() => governanceService.getAgents(), [])
  const audit = useLoad(() => governanceService.getAuditEvents(), [])
  const auditRows = audit.data || []
  return <GovLayout title="Agent Governance" sub="Backend component status and recent audit activity."><ErrorNote error={agents.error || audit.error}/><Table headers={['Component','Description','Status','Configured','Simulated','Last activity','Audit events']} rows={(agents.data || []).map(agent => {
    const events = auditRows.filter(event => event.agent_id === agent.agent_id)
    const latest = events[0]
    return <tr key={agent.agent_id}><td><Link to={`/governance/agents/${agent.agent_id}`}>{agent.name}</Link></td><td>{agent.purpose || agent.description || '—'}</td><td><Status>{agent.status}</Status></td><td>{agent.configured ? 'Yes' : 'No'}</td><td>{agent.simulated ? 'Yes' : 'No'}</td><td>{dateTime(latest?.timestamp || agent.last_execution)}</td><td>{events.length}</td></tr>
  })} empty="No component status records are available."/></GovLayout>
}

export function AgentDetailPage() {
  const { agentId } = useParams()
  const agent = useLoad(() => governanceService.getAgent(agentId), [agentId])
  const events = useLoad(() => governanceService.getExecutions({ agent_id: agentId }), [agentId])
  if (agent.error) return <GovLayout title="Component Details" sub={agentId}><ErrorNote error={agent.error}/></GovLayout>
  if (!agent.data) return <GovLayout title="Component Details" sub="Loading component status…"/>
  const item = agent.data
  const details = [['Component ID',item.agent_id],['Purpose',item.purpose],['Configured',item.configured ? 'Yes' : 'No'],['Simulated',item.simulated ? 'Yes' : 'No'],['Runtime error',item.error]].filter(([,value]) => value != null && value !== '')
  return <GovLayout title={item.name} sub="Component status and activity."><section className="panel pad agent-detail"><div className="panel-header"><div><h3>{item.name}</h3><p>{item.description}</p></div><Status>{item.status}</Status></div><div className="info-grid">{details.map(([name,value]) => <div className="info" key={name}><small>{name}</small><b>{field(value)}</b></div>)}</div></section><Table headers={['Event','Status','Time','Candidate','Details']} rows={(events.data || []).map(row => <tr key={row.audit_id}><td>{row.action}</td><td>{row.status}</td><td>{dateTime(row.timestamp)}</td><td>{field(row.candidate_id)}</td><td>{row.detail || '—'}</td></tr>)} empty="No audit records for this component."/></GovLayout>
}

export function OutcomeLearningPage() {
  const state = useLoad(() => outcomeLearningService.getDashboard(), [])
  const overview = state.data?.overview, rows = state.data?.rows || [], insights = state.data?.insights || []
  return <GovLayout title="Outcome Learning" sub="Review learning signals from persisted case outcomes."><ErrorNote error={state.error}/><div className="metrics-grid gov-metrics"><Metric label="CASES ANALYZED" value={overview?.analyzed} note="Persisted case rows"/><Metric label="REVIEW DECISIONS" value={overview?.feedback} note="Persisted decisions"/><Metric label="ACKNOWLEDGEMENTS" value={overview?.pha} note="Stored responses"/><Metric label="OUTCOME PATTERNS" value={overview?.analysis} note="Derived from outcomes"/></div><Table headers={['Case','Candidate','Review','Reportability','Submission']} rows={rows.map(row => <tr key={row.id}><td><Link to={`/governance/outcome-learning/${row.id}`}>{row.id}</Link></td><td>{row.candidate_id}</td><td>{field(row.reviewer_decision)}</td><td>{field(row.reportability_decision)}</td><td>{field(row.pha_outcome)}</td></tr>)} empty="No reviewed case outcomes are available."/>{insights.length > 0 && <Table headers={['Observed pattern','Cases','Suggestion']} rows={insights.map(item => <tr key={item.pattern}><td>{item.pattern}</td><td>{item.cases}</td><td>{item.suggestion}</td></tr>)}/>}</GovLayout>
}

export function LearningSignalDetail() {
  const { signalId } = useParams()
  const state = useLoad(() => outcomeLearningService.getLearningSignal(signalId), [signalId])
  const signal = state.data
  if (state.error) return <GovLayout title="Outcome Record" sub={signalId}><ErrorNote error={state.error}/></GovLayout>
  if (!signal) return <GovLayout title="Outcome Record" sub="Loading persisted outcome…"/>
  const details = [['Candidate',signal.candidate_id],['Candidate status',signal.ai_output],['Reviewer decision',signal.reviewer_decision],['Reportability',signal.reportability_decision],['Submission status',signal.pha_outcome],['Review reason',signal.review_reason],['Jurisdiction',signal.jurisdiction]].filter(([,value]) => value != null && value !== '' && value !== 'not_available')
  return <GovLayout title="Outcome Record" sub={`Case ${signal.id}`}><Table headers={['Field','Value']} rows={details.map(([label,value]) => <tr key={label}><td>{label}</td><td>{field(value)}</td></tr>)}/></GovLayout>
}
