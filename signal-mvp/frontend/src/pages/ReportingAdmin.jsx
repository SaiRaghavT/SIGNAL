import { Children, useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Activity, ArrowLeft, ArrowRight, Check, Clock3, FileCheck2, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import { request } from '../api/client.js'
import { acknowledge } from '../api/workflow.js'
import './reporting-admin.css'

const fmt = value => value ? new Date(value).toLocaleString() : '—'
const patient = row => row?.patient?.name || row?.patient?.full_name || row?.patient?.patient_id || 'Patient unavailable'
const mode = row => String(row?.submission_mode || '').toLowerCase() === 'immediate' || String(row?.severity || '').toUpperCase() === 'HIGH' ? 'Immediate' : 'Individual'
const show = value => value == null || value === '' ? 'Not available' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const array = value => Array.isArray(value) ? value : value ? [value] : []

function useLoad(loader, deps = []) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(true)
  const refresh = useCallback(async () => { setBusy(true); setError(''); try { setData(await loader()) } catch (e) { setError(e.message || 'Unable to load reporting data.') } finally { setBusy(false) } }, deps)
  useEffect(() => { refresh() }, [refresh])
  return { data, error, busy, refresh, setData }
}

function Head({ eyebrow, title, sub, right }) { return <div className="ra-heading"><div><small>{eyebrow}</small><h1>{title}</h1><p>{sub}</p></div>{right}</div> }
function Panel({ title, sub, right, children, className = '' }) { return <section className={`ra-panel ${className}`}><header><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{right}</header>{children}</section> }
function Stat({ label, value, sub, tone = 'blue' }) { return <div className={`ra-stat ${tone}`}><small>{label}</small><strong>{value ?? '—'}</strong><span>{sub}</span></div> }
function Pill({ value }) { const raw = String(value || 'Unknown'), key = raw.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-'); return <span className={`ra-pill ${key}`}>{raw.replaceAll('_', ' ')}</span> }
function LoadingError({ busy, error, retry }) { return <>{error && <div className="ra-error" role="alert">{error} {retry && <button onClick={retry}>Retry</button>}</div>}{busy && <div className="ra-loading">Loading persisted reporting data…</div>}</> }
function Table({ headers, children, empty = 'No records available.' }) { const rows = Children.toArray(children); return rows.length ? <div className="ra-table-scroll"><table className="ra-table"><thead><tr>{headers.map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>{rows}</tbody></table></div> : <div className="ra-empty">{empty}</div> }
function getReviewDecision(review) { return String(review?.status || review?.payload?.decision || '').toUpperCase() }
function isAdminReview(review) { return String(review?.payload?.reviewer_role || '').toLowerCase().includes('reporting administrator') || String(review?.payload?.reviewer_id || '').toLowerCase().includes('reporting-admin') }

async function getQueueWithReviews() {
  const [queue, submissions] = await Promise.all([request('/api/admin/submission-queue'), request('/api/submissions?page=1&page_size=100').catch(() => ({ items: [] }))])
  const items = await Promise.all((queue.items || []).map(async row => {
    const [review, validation] = await Promise.all([
      request(`/api/cases/${encodeURIComponent(row.case_id)}/review`).catch(() => null),
      request(`/api/cases/${encodeURIComponent(row.case_id)}/validation`).catch(() => null),
    ])
    const latest = (submissions.items || []).find(item => item.case_id === row.case_id)
    const decision = getReviewDecision(review), adminDecision = isAdminReview(review) ? decision : ''
    return { ...row, review, validation, latest, adminState: latest?.status === 'ACKNOWLEDGED' ? 'Acknowledged' : latest?.status === 'SUBMITTED' ? 'Submitted' : adminDecision === 'REQUEST_INFORMATION' || adminDecision === 'REJECT' ? 'Rejected / Returned for Correction' : adminDecision === 'APPROVE' ? 'Verified' : 'Pending Admin Verification' }
  }))
  return items
}

export function ReportingAdminDashboard() {
  const { data, error, busy, refresh } = useLoad(async () => {
    const [summary, queue, batches, submissions, deadlines, activity, agents] = await Promise.all([
      request('/api/admin/submission-dashboard'), getQueueWithReviews(), request('/api/admin/submission-batches').catch(() => ({ items: [] })),
      request('/api/submissions?page=1&page_size=100').catch(() => ({ items: [] })), request('/api/dashboard/deadlines').catch(() => ({ items: [] })),
      request('/api/dashboard/activity').catch(() => ({ items: [] })), request('/api/agents/status').catch(() => ({ agents: [] })),
    ])
    return { summary, queue, batches: batches.items || [], submissions: submissions.items || [], deadlines: deadlines.items || [], activity: activity.items || [], agents: agents.agents || [] }
  }, [])
  const d = data || {}, pending = (d.queue || []).filter(x => x.adminState === 'Pending Admin Verification')
  return <div className="ra-page"><Head eyebrow="SUPER ADMIN" title="Dashboard" sub="Real-time view of reporting operations, pending submissions, deadlines and SIGNAL Engine activity." right={<span className="ra-operational"><i/> SIGNAL Engine Operational</span>}/>
    <LoadingError busy={busy} error={error} retry={refresh}/>{data && <>
      <div className="ra-stats"><Stat label="READY FOR SUBMISSION" value={d.summary?.ready_for_submission} sub="Eligible cases after individual review" tone="green"/><Stat label="IMMEDIATE REPORTS" value={d.summary?.immediate_reports} sub="Deadline priority" tone="red"/><Stat label="CONFIGURABLE POC BATCHES" value={d.batches.length} sub="Optional workflow; PHA rules may differ" tone="orange"/><Stat label="SUBMISSION STATUS" value={d.submissions.length} sub={`${d.summary?.awaiting_acknowledgement || 0} awaiting acknowledgement`} tone="blue"/></div>
      <div className="ra-dashboard-grid"><div>
        <Panel title="Reporting Queue" sub="Cases awaiting individual verification and submission authorization." right={<Link className="ra-button" to="/admin/reporting-queue">Open queue <ArrowRight size={14}/></Link>}>
          <Table headers={['Reporting Type', 'Pending', 'Priority', 'Source', 'Action']} empty="No cases are waiting for admin verification.">{pending.slice(0, 8).map(row => <tr key={row.case_id}><td>{mode(row)}</td><td>{patient(row)}</td><td><Pill value={row.severity || 'Standard'}/></td><td>SIGNAL Engine</td><td><Link to={`/admin/reporting-queue/${row.case_id}`}>Review →</Link></td></tr>)}</Table>
        </Panel>
        <Panel title="Reporting Deadlines" sub="Persisted cases requiring attention based on reporting windows." right={<Link className="ra-button subtle" to="/admin/deadlines">View all</Link>}>
          <Table headers={['Case', 'Condition', 'Destination', 'Deadline', 'Status']} empty="No deadline records were returned by the backend.">{(d.deadlines || []).slice(0, 5).map((x, i) => <tr key={x.case_id || x.id || i}><td>{x.case_id || '—'}</td><td>{x.disease || x.condition || '—'}</td><td>{x.jurisdiction || x.destination || '—'}</td><td>{fmt(x.deadline || x.due_at)}</td><td><Pill value={x.status || 'Open'}/></td></tr>)}</Table>
        </Panel>
        <Panel title="Recent Submission Activity" sub="Latest available reporting events." right={<Link className="ra-button subtle" to="/admin/audit">Audit trail</Link>}>
          <div className="ra-activity">{d.activity.length ? d.activity.slice(0, 5).map((x, i) => <div key={x.event_id || x.id || i}><i/><small>{fmt(x.event_timestamp || x.created_at || x.timestamp)}</small><b>{x.event_type || x.action || 'Workflow activity'}</b><span>{x.entity_id || x.description || 'Persisted activity record'}</span></div>) : <p className="ra-empty">No recent activity records.</p>}</div>
        </Panel>
      </div><aside>
        <Panel title="Quick Actions"><div className="ra-actions"><Link to="/admin/reporting-queue?mode=Immediate">Review Immediate Reports <b>{d.summary?.immediate_reports || 0}</b></Link><Link to="/admin/reporting-queue">Review Individual Cases <b>{pending.length}</b></Link><Link to="/admin/submission-batches">Open POC Batches</Link><Link to="/admin/deadlines">View Deadlines</Link></div></Panel>
        <Panel title="SIGNAL Engine Status"><div className="ra-service-list">{d.agents.length ? d.agents.slice(0, 8).map((x, i) => <div key={x.name || x.agent_name || i}><Check size={14}/><span><b>{x.name || x.agent_name || x.service || 'Reporting service'}</b><small>{x.status || x.message || 'Status available'}</small></span></div>) : <p className="ra-empty">Service status unavailable.</p>}</div><p className="ra-note">Batch submission is an optional configurable POC workflow. Individual case review remains separate.</p></Panel>
      </aside></div>
    </>}
  </div>
}

export function ReportingAdminQueue() {
  const { data: items, error, busy, refresh } = useLoad(getQueueWithReviews, [])
  const [query, setQuery] = useState(''), [filter, setFilter] = useState('All statuses'), [modeFilter, setModeFilter] = useState('All types')
  const [selected, setSelected] = useState([]), [notice, setNotice] = useState(''), [saving, setSaving] = useState(false)
  const navigate = useNavigate()
  const rows = (items || []).filter(x => `${patient(x)} ${x.case_id} ${x.disease} ${x.jurisdiction}`.toLowerCase().includes(query.toLowerCase()) && (filter === 'All statuses' || x.adminState === filter) && (modeFilter === 'All types' || mode(x) === modeFilter))
  const ready = rows.filter(x => x.adminState === 'Verified' && x.eligibility?.eligible && mode(x) === 'Individual')
  const allSubmissions = (items || []).filter(x => ['Submitted', 'Acknowledged'].includes(x.adminState))
  const createBatch = async () => { setSaving(true); setNotice(''); try { const result = await request('/api/admin/submission-batches', { method: 'POST', body: JSON.stringify({ case_ids: selected }) }); navigate(`/admin/submission-batches/${result.batch_id}`) } catch (e) { setNotice(e.message || 'Unable to create the optional POC batch.') } finally { setSaving(false) } }
  const toggle = (id, checked) => setSelected(old => checked ? [...old, id] : old.filter(x => x !== id))
  return <div className="ra-page"><Head eyebrow="REPORTING OPERATIONS" title="Reporting Queue" sub="Review each case individually, validate its reporting details, and authorize submission." right={<span className="ra-operational"><i/> SIGNAL Engine Operational</span>}/>
    <LoadingError busy={busy} error={error} retry={refresh}/>{notice && <div className="ra-error" role="status">{notice}</div>}{items && <>
      <div className="ra-stats"><Stat label="IMMEDIATE" value={items.filter(x => mode(x) === 'Immediate' && x.adminState === 'Pending Admin Verification').length} sub="Review and submit per case" tone="red"/><Stat label="INDIVIDUAL" value={items.filter(x => mode(x) === 'Individual' && x.adminState === 'Pending Admin Verification').length} sub="One patient per submission"/><Stat label="READY FOR SUBMISSION" value={ready.length} sub="Verified individually" tone="orange"/><Stat label="SUBMISSION STATUS" value={allSubmissions.length} sub="Submitted or acknowledged" tone="blue"/></div>
      <div className="ra-config-notice"><ShieldCheck size={16}/><span><b>Individual verification required.</b> POC batches are optional and configurable; jurisdiction or PHA rules may require a different submission path.</span></div>
      <Panel title="Case queue" sub={`${rows.length} cases from persisted SIGNAL records`} right={<button className="ra-button subtle" onClick={refresh}><RefreshCw size={13}/> Refresh</button>}>
        <div className="ra-filters"><label><Search size={15}/><input placeholder="Search patient, case, condition or destination…" value={query} onChange={e => setQuery(e.target.value)}/></label><select value={modeFilter} onChange={e => setModeFilter(e.target.value)}><option>All types</option><option>Immediate</option><option>Individual</option></select><select value={filter} onChange={e => setFilter(e.target.value)}>{['All statuses', 'Pending Admin Verification', 'Verified', 'Rejected / Returned for Correction', 'Submitted', 'Acknowledged'].map(x => <option key={x}>{x}</option>)}</select></div>
        <Table headers={['Patient / Case', 'Condition', 'Jurisdiction', 'Deadline', 'Type', 'Status', 'Action']} empty="No cases match the current filters.">{rows.map(row => <tr key={row.case_id}><td><b>{patient(row)}</b><small>{row.case_id}</small></td><td>{row.disease || '—'}</td><td>{row.jurisdiction || '—'}</td><td>{fmt(row.deadline)}</td><td>{mode(row)}</td><td><Pill value={row.adminState}/></td><td><Link to={`/admin/reporting-queue/${row.case_id}`}>{['Pending Admin Verification', 'Rejected / Returned for Correction'].includes(row.adminState) ? 'Verify →' : 'Details →'}</Link></td></tr>)}</Table>
      </Panel>
      <Panel title="Selectable for optional POC batch" sub="Only individually verified, eligible Individual cases can be selected. Immediate cases remain per-case." right={<button className="ra-button primary" disabled={!selected.length || saving} onClick={createBatch}>{saving ? 'Creating…' : `Create batch (${selected.length})`}</button>}>
        <Table headers={['Select', 'Patient', 'Case ID', 'Condition', 'PHA / Jurisdiction', 'Eligibility']} empty="No verified and eligible cases are available for optional batching.">{ready.map(row => <tr key={row.case_id}><td><input type="checkbox" checked={selected.includes(row.case_id)} onChange={e => toggle(row.case_id, e.target.checked)}/></td><td>{patient(row)}</td><td>{row.case_id}</td><td>{row.disease || '—'}</td><td>{row.jurisdiction || '—'}</td><td><Pill value="Ready for Submission"/></td></tr>)}</Table>
      </Panel>
    </>}
  </div>
}

export function ReportingAdminCaseReview() {
  const { id } = useParams(), navigate = useNavigate()
  const { data: item, error, busy, refresh } = useLoad(async () => {
    const [reviewData, caseDetail] = await Promise.all([request(`/api/admin/cases/${encodeURIComponent(id)}/submission-review`), request(`/api/cases/${encodeURIComponent(id)}`).catch(() => null)])
    return { ...reviewData, caseDetail }
  }, [id])
  const { data: review } = useLoad(() => request(`/api/cases/${encodeURIComponent(id)}/review`).catch(() => null), [id])
  const { data: validation } = useLoad(() => request(`/api/cases/${encodeURIComponent(id)}/validation`).catch(() => null), [id])
  const [comments, setComments] = useState(''), [saving, setSaving] = useState(false), [errorDecision, setErrorDecision] = useState(''), [submitting, setSubmitting] = useState(false)
  const decision = getReviewDecision(review), isAdminDecision = isAdminReview(review), isVerified = isAdminDecision && decision === 'APPROVE', adminReturned = isAdminDecision && (decision === 'REQUEST_INFORMATION' || decision === 'REJECT')
  const eligibility = item?.eligibility || {}, canSubmit = isVerified && eligibility.eligible
  const decide = async result => { setSaving(true); setErrorDecision(''); try { await request(`/api/cases/${encodeURIComponent(id)}/review`, { method: 'POST', body: JSON.stringify({ reviewer_id: 'reporting-admin', reviewer_role: 'Reporting Administrator', decision: result, comments: comments || (result === 'APPROVE' ? 'Individually verified by Reporting Administrator.' : 'Returned for correction by Reporting Administrator.') }) }); await Promise.all([refresh()]); navigate('/admin/reporting-queue') } catch (e) { setErrorDecision(e.message || 'Could not save the review decision.') } finally { setSaving(false) } }
  const submit = async () => { setSubmitting(true); setErrorDecision(''); try { const result = await request(`/api/admin/cases/${encodeURIComponent(id)}/submit`, { method: 'POST', body: JSON.stringify({ submitted_by: 'reporting-admin' }) }); navigate(`/admin/submissions/${result.submission_id}`) } catch (e) { setErrorDecision(e.message || 'Submission failed.') } finally { setSubmitting(false) } }
  const evidence = item?.evidence || {}, fields = item?.caseDetail?.report_fields || item?.report?.report_data || item?.report?.fields || item?.patient || {}
  return <div className="ra-page ra-review-page"><div className="ra-backline"><Link to="/admin/reporting-queue"><ArrowLeft size={14}/> Back to Reporting Queue</Link><Pill value={mode(item)}/></div><Head eyebrow="INDIVIDUAL CASE VERIFICATION" title={patient(item)} sub={`Case ID: ${item?.case_id || id}`} right={<Pill value={item?.severity || 'Standard'}/>}/>
    <LoadingError busy={busy} error={error} retry={refresh}/>{item && <>
      <div className="ra-stats ra-four"><Stat label="REPORTING TYPE" value={mode(item)} sub="Case dispatch pathway"/><Stat label="CONDITION" value={item.disease || '—'} sub="Reportability record" tone="orange"/><Stat label="JURISDICTION / PHA" value={item.jurisdiction || 'Not resolved'} sub={item.facility?.name || 'Destination configuration'} tone="green"/><Stat label="REPORTING DEADLINE" value={fmt(item.deadline)} sub="From case record" tone="red"/></div>
      <Panel title="Patient & Case Information" sub="Persisted case and demographic fields" right={<Pill value={item.status || 'Case loaded'}/> }><div className="ra-info-grid">{Object.entries({ 'Patient name': patient(item), 'Case ID': item.case_id, 'Candidate ID': item.candidate_id, 'Date of birth': item.patient?.birth_date || item.patient?.dob, Sex: item.patient?.sex || item.patient?.gender, Address: item.patient?.address, Phone: item.patient?.phone, Facility: item.facility?.name || item.facility, Provider: item.provider?.name || item.provider, 'Final decision': item.final_decision, 'Reportability decision': item.reportability_decision }).filter(([,v]) => v != null && v !== '').map(([k,v]) => <div key={k}><small>{k}</small><b>{show(v)}</b></div>)}</div></Panel>
      <Panel title="Reporting Data" sub="Values from the persisted case and generated reporting record"><div className="ra-info-grid">{Object.entries(fields).filter(([,v]) => v != null && v !== '').map(([k,v]) => <div key={k}><small>{k.replaceAll('_',' ')}</small><b>{show(v)}</b></div>)}</div>{!Object.keys(fields).length && <p className="ra-note">No reporting fields are available in the persisted case record.</p>}</Panel>
      <Panel title="Clinical & Laboratory Evidence" sub="Evidence and source records attached to the case"><div className="ra-evidence-grid">{[['Clinical evidence', evidence.clinical], ['Laboratory evidence', evidence.laboratory], ['Source evidence', evidence.sources]].map(([label, value]) => <div key={label}><h3>{label}</h3>{array(value).length ? array(value).map((v,i) => <p key={i}>{show(v)}</p>) : <p>Not available in the case record.</p>}</div>)}</div></Panel>
      <Panel title="Reportability & Validation" sub="Backend eligibility checks and case validation results" right={<Pill value={eligibility.eligible ? 'Eligible' : 'Needs attention'}/> }><div className="ra-validation">{[['Reportability decision', item.reportability_decision || item.final_decision], ['Validation status', validation?.status || validation?.valid], ['Generated report', item.report?.report_id], ['Clinical review', eligibility.review_complete ? 'Complete' : 'Incomplete'], ['Attestation', eligibility.attestation_complete ? 'Complete' : 'Incomplete']].map(([k,v]) => <div key={k}><Check size={14}/><span>{k}</span><b>{show(v)}</b></div>)}</div>{array(eligibility.blockers).length > 0 && <div className="ra-blockers"><b>Submission blockers</b>{eligibility.blockers.map((x,i)=><p key={i}>{x}</p>)}</div>}{array(eligibility.warnings).length > 0 && <div className="ra-note">Warnings: {eligibility.warnings.join('; ')}</div>}</Panel>
      <Panel title="Reviewer Decision" sub="Each case must be reviewed and approved individually." right={<Pill value={adminReturned ? 'Returned for Correction' : isVerified ? 'Verified' : 'Pending Admin Verification'}/> }>
        {errorDecision && <div className="ra-error">{errorDecision}</div>}{(isVerified || adminReturned) && <div className="ra-decision-note">Saved Reporting Administrator decision: {decision}. {fmt(review?.updated_at || review?.created_at)}</div>}
        {!isVerified && <label className="ra-comment">Reviewer notes<textarea value={comments} onChange={e=>setComments(e.target.value)} placeholder="Add verification notes or correction instructions…"/></label>}
        <div className="ra-footer-actions"><button className="ra-button" onClick={()=>navigate('/admin/reporting-queue')}>Cancel</button>{!isVerified && <button className="ra-button danger" disabled={saving} onClick={()=>decide('REQUEST_INFORMATION')}>{saving?'Saving…':'Return for Correction'}</button>}{!isVerified && <button className="ra-button primary" disabled={saving || !eligibility.eligible} title={!eligibility.eligible ? 'Resolve backend eligibility blockers before approving submission.' : ''} onClick={()=>decide('APPROVE')}>{saving?'Saving…':'Approve for Submission'}</button>}{isVerified && <button className="ra-button primary" disabled={!canSubmit || submitting} onClick={submit}>{submitting?'Submitting…':'Submit Individual Case'}</button>}</div>
      </Panel>
    </>}
  </div>
}

export function ReportingAdminSubmissions() {
  const { data: result, error, busy, refresh } = useLoad(() => request('/api/submissions?page=1&page_size=100'), [])
  const [q, setQ] = useState(''), [status, setStatus] = useState('All statuses'), [type, setType] = useState('All types')
  const rows = result?.items || [], visible = rows.filter(x => `${x.submission_id} ${x.case_id} ${patient(x)} ${x.disease} ${x.destination}`.toLowerCase().includes(q.toLowerCase()) && (status === 'All statuses' || x.status === status) && (type === 'All types' || (x.batch_id ? 'Batch' : 'Individual') === type))
  const count = s => rows.filter(x => String(x.status).toUpperCase() === s).length
  return <div className="ra-page"><Head eyebrow="TRANSMISSION HISTORY" title="Submissions" sub="Track authorized reporting exchanges from submission through acknowledgement." right={<button className="ra-button subtle" onClick={refresh}><RefreshCw size={13}/> Refresh</button>}/><LoadingError busy={busy} error={error} retry={refresh}/>{result && <>
    <div className="ra-stats"><Stat label="SUBMITTED" value={count('SUBMITTED') + count('ACKNOWLEDGED')} sub="Persisted transmission records"/><Stat label="AWAITING RESPONSE" value={count('SUBMITTED')} sub="Technical acknowledgement pending" tone="orange"/><Stat label="ACKNOWLEDGED" value={count('ACKNOWLEDGED')} sub="Destination acknowledgement received" tone="green"/><Stat label="ERROR / RETRY" value={count('FAILED') + count('ERROR')} sub="Validation or transport exceptions" tone="red"/></div>
    <Panel title="Submission Operations" sub="Monitor persisted submissions across Immediate, Individual and optional POC batch pathways."><div className="ra-filters"><label><Search size={15}/><input placeholder="Search submission, patient, condition or destination…" value={q} onChange={e=>setQ(e.target.value)}/></label><select value={type} onChange={e=>setType(e.target.value)}><option>All types</option><option>Individual</option><option>Batch</option></select><select value={status} onChange={e=>setStatus(e.target.value)}>{['All statuses','SUBMITTED','ACKNOWLEDGED','FAILED','ERROR','REJECTED'].map(x=><option key={x}>{x}</option>)}</select></div></Panel>
    <Panel title="Submission Register" sub="Closed-loop transmission history" right={<span className="ra-live">Live database records</span>}><Table headers={['Submission / Case', 'Patient / Condition', 'Destination', 'Type', 'Submitted', 'Acknowledgement', 'Status', 'Action']} empty="No submissions are stored yet.">{visible.map(x=><tr key={x.submission_id}><td><b>{x.submission_id}</b><small>{x.batch_id ? `Batch ${x.batch_id}` : x.case_id}</small></td><td>{patient(x)}<small>{x.disease || '—'}</small></td><td>{x.destination || x.jurisdiction || '—'}</td><td><Pill value={x.batch_id ? 'Batch' : 'Individual'}/></td><td>{fmt(x.created_at)}</td><td>{x.acknowledgement_id || (x.status === 'ACKNOWLEDGED' ? 'Received' : 'Pending')}</td><td><Pill value={x.status}/></td><td><Link to={`/admin/submissions/${encodeURIComponent(x.submission_id)}`}>Details →</Link></td></tr>)}</Table></Panel>
  </>}</div>
}

export function ReportingAdminSubmissionDetail() {
  const { batchId: id } = useParams()
  const { data, error, busy, refresh } = useLoad(async () => {
    const [submission, acknowledgement] = await Promise.all([request(`/api/submissions/${encodeURIComponent(id)}`), request(`/api/submissions/${encodeURIComponent(id)}/acknowledgement`).catch(() => null)])
    return { submission, acknowledgement }
  }, [id])
  const [ackBusy, setAckBusy] = useState(false), [ackError, setAckError] = useState('')
  const simulateAck = async () => { setAckBusy(true); setAckError(''); try { await acknowledge(id); await refresh() } catch (e) { setAckError(e.message || 'Acknowledgement simulation failed.') } finally { setAckBusy(false) } }
  const x = data?.submission, ack = data?.acknowledgement, acknowledged = String(x?.status).toUpperCase() === 'ACKNOWLEDGED' || !!ack
  return <div className="ra-page ra-detail-page"><div className="ra-backline"><Link to="/admin/submissions"><ArrowLeft size={14}/> Submissions</Link></div><LoadingError busy={busy} error={error} retry={refresh}/>{x && <div className="ra-transmission"><div className="ra-status-icon">{acknowledged ? <Check/> : <Clock3/>}</div><small>SUBMISSION TRANSMITTED</small><h1>{acknowledged ? 'Acknowledgement Received' : 'Awaiting Acknowledgement'}</h1><p>{x.batch_id ? 'POC batch' : 'Individual case'} submitted to {x.destination || x.jurisdiction || 'the configured destination'}. Destination response {acknowledged ? 'has been recorded.' : 'has not yet been received.'}</p>
      <div className="ra-kv">{[['Patient', patient(x)], ['Case ID', x.case_id], ['Condition', x.disease], ['Destination', x.destination || x.jurisdiction], ['Submission ID', x.submission_id], ['Batch ID', x.batch_id || 'Not applicable'], ['Submitted at', fmt(x.created_at)], ['Status', x.status], ['Acknowledgement ID', ack?.acknowledgement_id || x.acknowledgement_id || 'Pending']].map(([k,v])=><div key={k}><span>{k}</span><b>{show(v)}</b></div>)}</div>
      <div className="ra-timeline">{[['Submission transmitted', 'Reporting package transmission record', true], ['Destination received', x.destination || x.jurisdiction || 'Configured reporting destination', true], [acknowledged ? 'Acknowledgement received' : 'Awaiting acknowledgement', ack ? `${ack.status || 'Received'} · ${fmt(ack.received_at)}` : 'Waiting for destination acknowledgement', acknowledged]].map(([title, note, done])=><div className={done ? 'done' : 'waiting'} key={title}><i>{done ? <Check size={13}/> : <Clock3 size={13}/>}</i><span><b>{title}</b><small>{note}</small></span></div>)}</div>
      {ackError && <div className="ra-error">{ackError}</div>}{x.status === 'SUBMITTED' && <div className="ra-simulate"><p>This POC can create a synthetic acknowledgement record for demonstration.</p><button className="ra-button primary" disabled={ackBusy} onClick={simulateAck}>{ackBusy ? 'Recording…' : 'Simulate Acknowledgement'}</button></div>}{x.errors?.length > 0 && <div className="ra-blockers">{x.errors.join('; ')}</div>}
    </div>}</div>
}

export function ReportingAdminDeadlines() {
  const { data, error, busy, refresh } = useLoad(async () => { const [deadlines, queue] = await Promise.all([request('/api/dashboard/deadlines'), request('/api/admin/submission-queue')]); return { deadlines: deadlines.items || [], queue: queue.items || [] } }, [])
  return <div className="ra-page"><Head eyebrow="REPORTING OPERATIONS" title="Deadlines" sub="Reporting windows returned by the backend for active cases."/><LoadingError busy={busy} error={error} retry={refresh}/>{data && <Panel title="Reporting deadlines"><Table headers={['Case', 'Condition', 'Destination', 'Deadline', 'Status', 'Action']} empty="No deadline records returned.">{data.deadlines.map((x,i) => { const row=data.queue.find(y=>y.case_id===x.case_id); return <tr key={x.case_id||i}><td>{x.case_id||'—'}</td><td>{x.disease||row?.disease||'—'}</td><td>{x.jurisdiction||row?.jurisdiction||'—'}</td><td>{fmt(x.deadline||x.due_at)}</td><td><Pill value={x.status||'Open'}/></td><td>{row && <Link to={`/admin/reporting-queue/${row.case_id}`}>Review →</Link>}</td></tr>})}</Table></Panel>}</div>
}

export function ReportingAdminSettings() {
  const { data, error, busy, refresh } = useLoad(() => request('/api/agents/status'), [])
  const items = data?.agents || data?.items || data?.services || (Array.isArray(data) ? data : [])
  return <div className="ra-page"><Head eyebrow="ADMINISTRATION" title="Settings" sub="Current reporting service status and configurable POC workflow context."/><LoadingError busy={busy} error={error} retry={refresh}/>{data && <><Panel title="SIGNAL service status" right={<button className="ra-button subtle" onClick={refresh}><RefreshCw size={13}/> Refresh</button>}><div className="ra-service-list">{items.map((x,i)=><div key={x.name||x.agent_name||i}><Activity size={14}/><span><b>{x.name||x.agent_name||x.service||'Service'}</b><small>{x.status||x.message||'Status available'}</small></span></div>)}</div></Panel><div className="ra-config-notice"><ShieldCheck size={16}/><span>Batching is a configurable POC workflow. Confirm destination jurisdiction requirements before adopting a production submission pathway.</span></div></>}</div>
}
