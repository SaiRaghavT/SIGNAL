import { useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { Activity, AlertTriangle, Bell, Check, ChevronRight, ClipboardList, FileCheck2, LayoutDashboard, Search, Settings, ShieldCheck, Users, BriefcaseBusiness, ArrowLeft, ArrowRight, CheckCircle2, Menu, RefreshCw, Eye, EyeOff } from 'lucide-react'
import './App.css'
import './components/AnatomyVisualization.css'
import { GovernanceOverview, MonitoringPage, EvaluationPage, ExplainabilityPage, AgentGovernancePage, OutcomeLearningPage, LearningSignalDetail, AgentDetailPage } from './pages/AiGovernance.jsx'
import SeedReportingFormPage from './pages/SeedReportingFormPage.jsx'
import { reportingWorkflowService } from './services/reportingWorkflowService.js'
import { signalApi } from './services/backendApi.js'
import anatomyDashboard from './assets/anatomy-dashboard.png'

const seedCandidates = window.__signalSeedCandidates || (window.__signalSeedCandidates = [])
const seedCandidateLoad = window.__signalSeedCandidateLoad || (window.__signalSeedCandidateLoad = { status: 'loading', error: '' })
const sources = Array(5).fill('FHIR seed bundle')
const ROLE_CLINICAL = 'clinical_staff'
const ROLE_ADMIN = 'reporting_admin'
const DEMO_PASSWORD = 'SIGNAL2026'
const DEFAULT_CLINICAL_USERNAME = 'sarah.mitchell@signal.local'
const DEFAULT_ADMIN_USERNAME = 'alex.morgan@signal.local'

function getUserDisplayName(role = localStorage.getItem('signalRole')) {
  let username = ''
  try {
    username = JSON.parse(localStorage.getItem('signal-user') || '{}').name || ''
  } catch {
    username = ''
  }
  const displayName = username.split('@')[0].replace(/[._-]+/g, ' ').trim()
  if (!displayName || ['clinical staff', 'reporting admin', 'reporting administrator'].includes(displayName.toLowerCase())) {
    return role === ROLE_ADMIN || role === 'admin' ? 'Alex Morgan' : 'Sarah Mitchell'
  }
  return displayName.split(/\s+/).map(part => part[0].toUpperCase() + part.slice(1)).join(' ')
}

function App() {
  const [, setCandidateDataRevision] = useState(0)
  const [queue, setQueue] = useState(() => JSON.parse(localStorage.getItem('signalQueue') || '[]'))
  const [role,setRole] = useState(()=>localStorage.getItem('signalRole')||'')
  const [caseStates,setCaseStates] = useState(()=>reportingWorkflowService.getCaseStates())
  const [batches,setBatches] = useState(()=>reportingWorkflowService.getBatches())

  useEffect(() => {
    let active = true
    signalApi.getSeedFhirCandidates()
      .then(response => {
        if (!active) return
        seedCandidates.splice(0, seedCandidates.length, ...(response.items || []))
        Object.assign(seedCandidateLoad, { status: seedCandidates.length ? 'ready' : 'empty', error: '' })
        setCandidateDataRevision(revision => revision + 1)
      })
      .catch(error => {
        if (!active) return
        Object.assign(seedCandidateLoad, { status: 'error', error: error.message })
        setCandidateDataRevision(revision => revision + 1)
      })

    return () => { active = false }
  }, [])
  const setActiveRole = nextRole => {
    const activeRole = nextRole === 'admin' ? ROLE_ADMIN : nextRole === 'clinical' ? ROLE_CLINICAL : nextRole
    localStorage.setItem('signalRole',activeRole)
    setRole(activeRole)
  }
  const logout = () => {
    localStorage.removeItem('signalRole')
    sessionStorage.removeItem('signalRole')
    localStorage.removeItem('signal-user')
    sessionStorage.removeItem('signal-user')
    setRole('')
  }
  const addToQueue = (id) => { setQueue(current => { const next = current.includes(id) ? current : [...current, id]; localStorage.setItem('signalQueue', JSON.stringify(next)); return next }); reportingWorkflowService.setCaseState(id,{clinicalReviewStatus:'Complete',clinicalReviewer:getUserDisplayName(),clinicalCompletedAt:new Date().toLocaleString(),adminVerificationStatus:'Pending Admin Verification',submissionStatus:'Not Submitted',status:'Pending Admin Verification',queuedAt:new Date().toLocaleString()});setCaseStates(reportingWorkflowService.getCaseStates()) }
  const setCaseState=(id,patch)=>{if(patch.submissionStatus==='Acknowledged')reportingWorkflowService.acknowledgeCase(id);else reportingWorkflowService.setCaseState(id,patch);setCaseStates(reportingWorkflowService.getCaseStates());setBatches(reportingWorkflowService.getBatches())}
  const submitBatch=(ids,phaByCase)=>{const batch=reportingWorkflowService.submitBatch(ids,phaByCase);setCaseStates(reportingWorkflowService.getCaseStates());setBatches(reportingWorkflowService.getBatches());return batch}
  return <BrowserRouter><InteractionDialogs/><Routes>
    <Route path="/login" element={role?<Navigate to={role===ROLE_ADMIN?'/admin/dashboard':'/dashboard'} replace/>:<Login onLogin={setActiveRole}/>} />
    <Route path="/admin/login" element={<Navigate to="/login" replace/>} />
    <Route path="*" element={role?<Shell queue={queue} role={role===ROLE_ADMIN?'admin':'clinical'} setRole={setActiveRole} onLogout={logout}><Routes>
      <Route path="/" element={<RoleGate role={role} required={ROLE_CLINICAL}><Dashboard caseStates={caseStates}/></RoleGate>} /><Route path="/dashboard" element={<RoleGate role={role} required={ROLE_CLINICAL}><Dashboard caseStates={caseStates}/></RoleGate>} />
      <Route path="/admin/dashboard" element={<RoleGate role={role} required={ROLE_ADMIN}><AdminDashboard queue={queue} caseStates={caseStates}/></RoleGate>}/>
      <Route path="/candidates" element={<RoleGate role={role} required={ROLE_CLINICAL}><Candidates caseStates={caseStates}/></RoleGate>} /><Route path="/candidates/:id" element={<RoleGate role={role} required={ROLE_CLINICAL}><CandidateDetails caseStates={caseStates}/></RoleGate>} />
      <Route path="/candidates/:id/reporting-form" element={<RoleGate role={role} required={ROLE_CLINICAL}><SeedReportingFormPage/></RoleGate>} />
      <Route path="/candidates/:id/extraction" element={<RoleGate role={role} required={ROLE_CLINICAL}><Extraction /></RoleGate>} /><Route path="/candidates/:id/reporting-data" element={<RoleGate role={role} required={ROLE_CLINICAL}><ReportingData /></RoleGate>} />
      <Route path="/candidates/:id/review" element={<RoleGate role={role} required={ROLE_CLINICAL}><ClinicalReviewPage addToQueue={addToQueue} caseStates={caseStates}/></RoleGate>} />
      <Route path="/queue-confirmation/:id" element={<RoleGate role={role} required={ROLE_CLINICAL}><QueueConfirmation caseStates={caseStates}/></RoleGate>}/>
      <Route path="/admin/reporting-queue" element={<RoleGate role={role} required={ROLE_ADMIN}><FinalAdminQueue queue={queue} caseStates={caseStates} submitBatch={submitBatch}/></RoleGate>}/>
      <Route path="/admin/reporting-queue/batch" element={<RoleGate role={role} required={ROLE_ADMIN}><BatchSubmission queue={queue} caseStates={caseStates} submitBatch={submitBatch}/></RoleGate>}/>
      <Route path="/admin/reporting-queue/:id" element={<RoleGate role={role} required={ROLE_ADMIN}><FinalAdminVerification caseStates={caseStates} setCaseState={setCaseState}/></RoleGate>}/>
      <Route path="/admin/submissions" element={<RoleGate role={role} required={ROLE_ADMIN}><FinalAdminSubmissions queue={queue} caseStates={caseStates} batches={batches} setCaseState={setCaseState}/></RoleGate>}/>
      <Route path="/admin/submissions/:batchId" element={<RoleGate role={role} required={ROLE_ADMIN}><BatchDetail batches={batches}/></RoleGate>}/>
      <Route path="/reporting-queue" element={<RoleGate role={role} required={ROLE_ADMIN}><FinalAdminQueue queue={queue} caseStates={caseStates} submitBatch={submitBatch}/></RoleGate>} />
      <Route path="/reporting-queue/:id/verify" element={<RoleGate role={role} required={ROLE_ADMIN}><FinalAdminVerification caseStates={caseStates} setCaseState={setCaseState}/></RoleGate>} />
      <Route path="/reporting-queue/batch" element={<RoleGate role={role} required={ROLE_ADMIN}><BatchSubmission queue={queue} caseStates={caseStates} submitBatch={submitBatch}/></RoleGate>} />
      <Route path="/submissions" element={<RoleGate role={role} required={ROLE_ADMIN}><FinalAdminSubmissions queue={queue} caseStates={caseStates} batches={batches} setCaseState={setCaseState}/></RoleGate>} />
      <Route path="/cases" element={<Cases />} /><Route path="/analytics" element={<AnalyticsPage caseStates={caseStates}/>} /><Route path="/investigation" element={<Investigation />} /><Route path="/governance" element={<Governance />} />
      <Route path="/governance/monitoring" element={<MonitoringPage/>}/><Route path="/governance/evaluation" element={<EvaluationPage/>}/><Route path="/governance/explainability" element={<ExplainabilityPage/>}/><Route path="/governance/agents" element={<AgentGovernancePage/>}/><Route path="/governance/outcome-learning" element={<OutcomeLearningPage/>}/><Route path="/governance/outcome-learning/:signalId" element={<LearningSignalDetail/>}/><Route path="/governance/agents/:agentId" element={<AgentDetailPage/>}/>
    </Routes></Shell>:<Navigate to="/login" replace/>} />
  </Routes></BrowserRouter>
}

function RoleGate({role,required,children}) {
  if (!role) return <Navigate to="/login" replace/>
  if (role === required) return children
  return <Navigate to={role===ROLE_ADMIN?'/admin/dashboard':'/dashboard'} replace/>
}

function BackendConnectionStatus() {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    let active = true
    signalApi.getHealth()
      .then(response => {
        if (active) setStatus(response.status === 'ok' ? 'connected' : 'unavailable')
      })
      .catch(() => {
        if (active) setStatus('unavailable')
      })

    return () => { active = false }
  }, [])

  const label = status === 'checking' ? 'Checking backend...' : status === 'connected' ? 'Backend connected' : 'Backend unavailable'
  return <div className={`system-status backend-status ${status}`} role="status" aria-live="polite"><span className="status-dot"/>{label}</div>
}

function InteractionDialogs() {
  const [dialog,setDialog] = useState(null)

  useEffect(() => {
    const handleClick = event => {
      if (!(event.target instanceof Element)) return
      const sourceLink = event.target.closest('a[href="#source"], a[href="#evidence"]')
      const forgotPassword = event.target.closest('a[href="#forgot"]')

      if (sourceLink) {
        event.preventDefault()
        const candidateId = window.location.pathname.match(/\/candidates\/([^/]+)/)?.[1]
        setDialog({ kind: 'source', candidateId, details: sourceLink.closest('.source-row')?.innerText.trim() || 'Source details are not available.' })
      } else if (forgotPassword) {
        event.preventDefault()
        setDialog({ kind: 'password' })
      }
    }

    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  if (!dialog) return null

  const close = () => setDialog(null)
  return <div className="interaction-backdrop" role="presentation" onClick={close}><section className="interaction-dialog" role="dialog" aria-modal="true" aria-labelledby="interaction-dialog-title" onClick={event=>event.stopPropagation()}><div className="interaction-dialog-heading"><h2 id="interaction-dialog-title">{dialog.kind==='source'?'Source Details':'Password Help'}</h2><button type="button" className="text-link" onClick={close}>Close</button></div>{dialog.kind==='source'?<><dl><div><dt>Candidate</dt><dd>{dialog.candidateId||'Not linked'}</dd></div><div><dt>Visible source record</dt><dd className="source-record-text">{dialog.details}</dd></div></dl><p>The raw source document is not attached to this synthetic demo record.</p></>:<p>Password reset is not configured in this demo. Contact your SIGNAL administrator for account assistance.</p>}</section></div>
}

function Shell({ children, queue, role, setRole, onLogout }) {
  const [open, setOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const nav = role==='admin'?[['Dashboard','/admin/dashboard',LayoutDashboard],['Reporting Queue','/admin/reporting-queue',ClipboardList],['Submissions','/admin/submissions',FileCheck2],['Analytics','/analytics',Activity]]:[['Dashboard','/dashboard',LayoutDashboard],['Candidates','/candidates',Users],['Cases','/cases',BriefcaseBusiness],['Analytics','/analytics',Activity]]
  const userName = getUserDisplayName()
  const userInitials = userName.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase()
  return <div className="app-shell"><aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
    <Link className="brand" to={role==='admin'?'/admin/dashboard':'/dashboard'}><div className="brand-logo">S</div><div><b>SIGNAL</b><small>INTELLIGENCE LAYER</small></div></Link>
    <div className="sidebar-scroll"><div className="nav-title">WORKSPACE</div><nav className="navigation">{nav.map(([label,path,Icon])=><NavLink key={path} to={path} className={({isActive})=>`nav-item ${isActive?'active':''}`}><Icon size={17}/><span>{label}</span>{label==='Submissions'&&queue.length>0&&<i className="nav-count">{queue.length}</i>}</NavLink>)}</nav>
      <div className="sidebar-governance"><div className="nav-title">AI GOVERNANCE</div>{[['Overview','/governance'],['AI Monitoring','/governance/monitoring'],['Model Evaluation','/governance/evaluation'],['Explainability','/governance/explainability'],['Agent Governance','/governance/agents'],['Outcome Learning','/governance/outcome-learning']].map(([label,path])=><NavLink end key={path} to={path} className={({isActive})=>`nav-item ${isActive?'active':''}`}><ShieldCheck size={15}/><span>{label}</span></NavLink>)}</div>
      <div className="sidebar-extra"><NavLink to="/investigation" className="nav-item"><Search size={17}/><span>Investigation</span></NavLink><button type="button" className="nav-item" onClick={()=>setShowSettings(true)}><Settings size={17}/><span>Settings</span></button></div>
    </div><div className="sidebar-footer"><div className="user-card"><div className="avatar">{userInitials}</div><div><div className="user-name">{userName}</div><div className="user-role">{role==='admin'?'Reporting Admin':'Clinical Staff'}</div></div></div><Link to="/login" onClick={onLogout} className="switch-role">Logout</Link><div className="powered">Powered by <b>feuji</b></div></div>
  </aside><main className="main-content"><header className="header"><button type="button" className="mobile-menu" aria-label="Toggle navigation" aria-expanded={open} onClick={()=>setOpen(!open)}><Menu/></button><span className="mobile-brand">SIGNAL</span><div className="header-actions"><div className="system-status"><span className="status-dot"/>Demo Environment ┬╖ Synthetic Data</div><button type="button" className="notification-button" aria-label={`Notifications (${queue.length})`} aria-expanded={showNotifications} aria-controls="notification-panel" onClick={()=>setShowNotifications(value=>!value)}><Bell size={18}/>{queue.length>0&&<i className="nav-count">{queue.length}</i>}</button>{showNotifications&&<section className="notification-popover" id="notification-panel" aria-label="Notifications"><div className="notification-heading"><b>Notifications</b><button type="button" className="text-link" onClick={()=>setShowNotifications(false)}>Close</button></div>{queue.length?queue.map(id=>{const candidate=seedCandidates.find(item=>item.id===id);return candidate&&<Link key={id} to={role==='admin'?`/admin/reporting-queue/${id}`:`/candidates/${id}`} onClick={()=>setShowNotifications(false)}><b>{candidate.id} ┬╖ {candidate.patient}</b><small>{candidate.condition} ┬╖ {candidate.jurisdiction}</small></Link>}):<p>No reporting queue notifications.</p>}</section>}<div className="header-profile"><div className="header-avatar">{userInitials}</div><div><b>{userName}</b><small>{role==='admin'?'Reporting Administrator':'Clinical Staff'}</small></div></div></div></header>{children}{showSettings&&<div className="interaction-backdrop" role="presentation" onClick={()=>setShowSettings(false)}><section className="interaction-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title" onClick={event=>event.stopPropagation()}><div className="notification-heading"><h2 id="settings-title">Settings</h2><button type="button" className="text-link" onClick={()=>setShowSettings(false)}>Close</button></div><label className="settings-role">Active role<select value={role} onChange={event=>{localStorage.setItem('signalRole',event.target.value);setRole(event.target.value)}}><option value="clinical">Clinical Staff</option><option value="admin">Reporting Administrator</option></select></label><p>Role selection controls access to clinical review and reporting administration workflows.</p><small>API: {import.meta.env.VITE_API_BASE_URL||'Vite development proxy'}</small></section></div>}</main></div>
}
function Page({title,subtitle,children}) {
  const candidate = useCandidate()
  return <div className="page"><div className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div></div>{seedCandidateLoad.status !== 'ready' && <SeedDataNotice/>}{title==='Candidate Details'&&seedCandidateLoad.status==='ready'&&<section className="panel candidate-anatomy-panel"><PanelTitle title="FHIR Source Record" sub="Patient and resources from the original seed bundle"/><div className="info-grid">{[['SOURCE FILE',candidate.source_file||'Loading'],['FHIR RESOURCES',Object.values(candidate.fhir_resource_counts||{}).reduce((sum,count)=>sum+count,0)],['DOCUMENTED CONDITIONS',(candidate.conditions||[]).length],['WORKFLOW STATUS','Not evaluated']].map(([label,value])=><Info key={label} label={label} value={value}/>)}</div><CandidateWorkflowAction/></section>}{children}</div>
}

function CandidateWorkflowAction() {
  const candidate = useCandidate()
  return <div className="candidate-workflow-action"><div className="workflow-action-heading"><div><b>Reportability evaluation</b><small>This FHIR seed bundle has not been ingested as a SIGNAL workflow candidate.</small></div><span className="badge unreviewed">Not evaluated</span></div></div>
}
function AnalyticsPage({caseStates}) {
  const conditions = seedCandidates.reduce((counts, candidate) => {
    for (const condition of candidate.conditions || [candidate.condition]) {
      if (!condition) continue
      counts[condition] = (counts[condition] || 0) + 1
    }
    return counts
  }, {})
  const jurisdictions = seedCandidates.reduce((counts, candidate) => {
    if (candidate.jurisdiction) counts[candidate.jurisdiction] = (counts[candidate.jurisdiction] || 0) + 1
    return counts
  }, {})
  const workflowStatuses = Object.values(caseStates).reduce((counts, state) => {
    const status = state.status || state.submissionStatus || state.adminVerificationStatus || 'Not started'
    counts[status] = (counts[status] || 0) + 1
    return counts
  }, {})
  const resourceTotals = seedCandidates.reduce((totals, candidate) => {
    Object.entries(candidate.fhir_resource_counts || {}).forEach(([resource, count]) => {
      totals[resource] = (totals[resource] || 0) + Number(count || 0)
    })
    return totals
  }, {})
  const totalResources = Object.values(resourceTotals).reduce((sum, value) => sum + value, 0)
  const rankedConditions = Object.entries(conditions).sort((a,b) => b[1] - a[1])
  const topConditions = rankedConditions.slice(0, 5)
  const otherConditionCount = rankedConditions.slice(5).reduce((sum, [,count]) => sum + count, 0)
  const conditionSlices = otherConditionCount ? [...topConditions, ['Other', otherConditionCount]] : topConditions
  const workflowEntries = Object.entries(workflowStatuses).sort((a,b) => b[1] - a[1])
  const totalWorkflow = workflowEntries.reduce((sum, [,count]) => sum + count, 0)
  const conditionTotal = Object.values(conditions).reduce((sum, value) => sum + value, 0)
  const topResourceTypes = Object.entries(resourceTotals).sort((a,b) => b[1] - a[1]).slice(0, 6)

  return <Page title="Analytics" subtitle="Operational intelligence across patients, conditions, FHIR resources, and reporting workflow.">
    <div className="metrics-grid">
      <Metric label="FHIR PATIENTS" value={seedCandidates.length} note="Patient bundles in the seed dataset"/>
      <Metric label="FHIR RESOURCES" value={totalResources} note="Resources across all bundles" tone="orange"/>
      <Metric label="CONDITIONS" value={Object.keys(conditions).length} note="Distinct documented conditions" tone="green"/>
      <Metric label="WORKFLOW RECORDS" value={Object.keys(caseStates).length} note="Saved reporting workflow activity" tone="blue"/>
    </div>

    <div className="two-column">
      <section className="panel">
        <PanelTitle title="Condition distribution" sub="Share of documented patient-condition records"/>
        <div style={{display:'flex',gap:28,alignItems:'center',flexWrap:'wrap'}}>
          <div style={{position:'relative',width:210,height:210,borderRadius:'50%',background:`conic-gradient(${conditionSlices.map(([,count], index) => { const start=conditionSlices.slice(0,index).reduce((sum, item)=>sum+item[1],0)/Math.max(conditionTotal,1)*360; const end=(start+count/Math.max(conditionTotal,1)*360); const shades=['#ff6b3d','#173b5e','#22a88a','#7c8da6','#f2b134','#6b5b95']; return `${shades[index % shades.length]} ${start}deg ${end}deg` }).join(', ')})`}}><div style={{position:'absolute',inset:45,background:'#fff',borderRadius:'50%',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center'}}><strong style={{fontSize:28,color:'#173b5e'}}>{seedCandidates.length}</strong><small style={{color:'#7c8da6'}}>patients</small></div></div>
          <div style={{minWidth:260,flex:1}}>{conditionSlices.map(([condition,count], index)=>{const shades=['#ff6b3d','#173b5e','#22a88a','#7c8da6','#f2b134','#6b5b95']; return <div key={condition} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 0',borderBottom:'1px solid #edf1f4'}}><span style={{width:10,height:10,borderRadius:'50%',background:shades[index % shades.length],display:'inline-block'}}/><b>{condition}</b><span>{count}</span></div>})}</div>
        </div>
      </section>

      <section className="panel">
        <PanelTitle title="Condition volume" sub="Patients represented by each documented condition"/>
        <div>{topConditions.map(([condition,count])=><div key={condition} style={{marginBottom:14}}><div style={{display:'flex',justifyContent:'space-between',gap:12,marginBottom:5}}><b>{condition}</b><span>{count}</span></div><div style={{height:10,background:'#edf1f4',borderRadius:999,overflow:'hidden'}}><div style={{height:'100%',background:'#ff6b3d',borderRadius:999,width:`${Math.max(4,(count/Math.max(topConditions[0]?.[1]||1,1))*100)}%`}}/></div></div>)}</div>
      </section>

      <section className="panel">
        <PanelTitle title="Workflow status" sub="Current reporting workflow distribution"/>
        {workflowEntries.length ? <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:12}}>{workflowEntries.map(([status,count], index)=><div key={status} style={{display:'flex',alignItems:'center',gap:12,padding:16,border:'1px solid #e4e9ee',borderRadius:12,background:'#fafcfd'}}><div style={{width:32,height:32,borderRadius:'50%',background:'#173b5e',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:700}}>{index+1}</div><div style={{flex:1}}><b style={{display:'block'}}>{status}</b><small style={{display:'block',color:'#7c8da6',marginTop:3}}>{count} record{count===1?'':'s'}</small></div><strong>{Math.round((count/Math.max(totalWorkflow,1))*100)}%</strong></div>)}</div> : <div className="empty-state"><h3>No workflow activity</h3><p>Workflow analytics will appear as candidates move through review and reporting.</p></div>}
      </section>

      <section className="panel">
        <PanelTitle title="FHIR resource mix" sub="Most common resource types across the seed dataset"/>
        <div>{topResourceTypes.map(([resource,count])=><div key={resource} style={{marginBottom:14}}><div style={{display:'flex',justifyContent:'space-between',gap:12,marginBottom:5}}><b>{resource}</b><span>{count.toLocaleString()}</span></div><div style={{height:10,background:'#edf1f4',borderRadius:999,overflow:'hidden'}}><div style={{height:'100%',background:'#173b5e',borderRadius:999,width:`${Math.max(4,(count/Math.max(topResourceTypes[0]?.[1]||1,1))*100)}%`}}/></div></div>)}</div>
      </section>
    </div>

    <section className="panel">
      <PanelTitle title="SIGNAL reporting flow" sub="Operational path from source data to public health reporting"/>
      <div style={{display:'flex',alignItems:'stretch',gap:8,flexWrap:'wrap'}}>
        {['FHIR / HL7 / Documents','Detection & AI','Candidate + Evidence','Clinical Review','Reportability + Validation','PHA Submission'].map((step,index)=><div key={step} style={{position:'relative',flex:'1 1 150px',minWidth:150,padding:16,border:'1px solid #e2e8ed',borderRadius:12,background:'#f9fbfc'}}><div style={{width:28,height:28,borderRadius:'50%',background:'#ff6b3d',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:700,marginBottom:9}}>{index+1}</div><b style={{fontSize:13,lineHeight:1.35}}>{step}</b>{index<5&&<ChevronRight style={{position:'absolute',right:-15,top:'50%',transform:'translateY(-50%)',background:'#fff',zIndex:2}} size={20}/>}</div>)}
      </div>
    </section>

    <section className="panel">
      <PanelTitle title="Jurisdiction overview" sub="Patient distribution by documented state"/>
      <div className="info-grid">{Object.entries(jurisdictions).map(([jurisdiction,count])=><div key={jurisdiction}><span style={{display:'block',fontSize:12,color:'#7c8da6'}}>JURISDICTION</span><strong style={{display:'block',fontSize:24,color:'#173b5e',marginTop:5}}>{jurisdiction}</strong><small>{count} patients</small></div>)}</div>
    </section>
  </Page>
}

function Metric({label,value,note,tone='blue'}) { return <div className={`metric-card ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small><Activity className="metric-spark" size={19}/></div> }
function SeedDataNotice() {
  if (seedCandidateLoad.status === 'loading') return <div className="note" role="status">Loading FHIR seed records...</div>
  if (seedCandidateLoad.status === 'error') return <div className="workflow-api-error" role="alert">FHIR seed data could not be loaded: {seedCandidateLoad.error}</div>
  if (seedCandidateLoad.status === 'empty') return <div className="empty-state"><h3>No FHIR patient records found</h3><p>The data/seed/fhir directory contains no usable patient bundles.</p></div>
  return <div className="note">Loaded {seedCandidates.length} patient bundles from data/seed/fhir.</div>
}
function Dashboard({caseStates}) {
  const dataReady = seedCandidateLoad.status === 'ready'
  const patientRecords = seedCandidates

  const conditionCount = seedCandidates.reduce(
    (total, candidate) =>
      total + (candidate.fhir_resource_counts?.Condition || 0),
    0
  )

  const resourceCount = seedCandidates.reduce(
    (total, candidate) =>
      total +
      Object.values(candidate.fhir_resource_counts || {}).reduce(
        (sum, count) => sum + count,
        0
      ),
    0
  )

  const jurisdictionCount = new Set(
    seedCandidates
      .map(candidate => candidate.jurisdiction)
      .filter(value => value && value !== 'Not recorded')
  ).size

  // Pagination — display only 10 records per page
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

  const totalPages = Math.max(
    1,
    Math.ceil(patientRecords.length / pageSize)
  )

  const startIndex = (currentPage - 1) * pageSize

  const paginatedRecords = patientRecords.slice(
    startIndex,
    startIndex + pageSize
  )

  return (
    <Page
      title="Dashboard"
      subtitle="Public health reporting operations at a glance"
    >
      <BackendConnectionStatus />

      <section className="metrics-grid">
        <Metric
          label="FHIR PATIENTS"
          value={dataReady ? seedCandidates.length : '—'}
          note="Patient bundles in the seed dataset"
        />

        <Metric
          label="CONDITION RESOURCES"
          value={dataReady ? conditionCount : '—'}
          note="FHIR Condition resources"
          tone="orange"
        />

        <Metric
          label="FHIR RESOURCES"
          value={dataReady ? resourceCount : '—'}
          note="Resources across all bundles"
          tone="green"
        />

        <Metric
          label="JURISDICTIONS"
          value={dataReady ? jurisdictionCount : '—'}
          note="Distinct documented states"
          tone="blue"
        />
      </section>

      <section className="panel priority-panel">
        <div className="panel-header">
          <div>
            <h3>
              FHIR Patient Records{' '}
              <span className="dark-pill">
                {dataReady ? patientRecords.length : '—'} seed records
              </span>
            </h3>

            <p>
              All patient bundles from data/seed/fhir; reportability has not
              been evaluated.
            </p>
          </div>

          <Link
            className="button secondary"
            to="/candidates"
          >
            View All Patients
          </Link>
        </div>

        {/* Existing candidate table — only the displayed rows are paginated */}
        <CandidateTable
          rows={dataReady ? paginatedRecords : []}
          compact
          caseStates={caseStates}
        />

        {/* Pagination */}
        {dataReady && patientRecords.length > pageSize && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              gap: '8px',
              padding: '20px 0 8px',
              flexWrap: 'wrap'
            }}
          >
            <button
              className="button secondary small"
              disabled={currentPage === 1}
              onClick={() =>
                setCurrentPage(page => Math.max(1, page - 1))
              }
            >
              Previous
            </button>
            <span className="muted" style={{fontSize:'13px',minWidth:'90px',textAlign:'center'}}>
              Page {currentPage} of {totalPages}
            </span>
<button
              className="button secondary small"
              disabled={currentPage === totalPages}
              onClick={() =>
                setCurrentPage(page =>
                  Math.min(totalPages, page + 1)
                )
              }
            >
              Next
            </button>
          </div>
        )}

        {dataReady && patientRecords.length > 0 && (
          <div
            style={{
              textAlign: 'center',
              padding: '4px 0 16px',
              fontSize: '13px',
              color: '#718096'
            }}
          >
            Showing {startIndex + 1}–
            {Math.min(startIndex + pageSize, patientRecords.length)}
            {' '}of {patientRecords.length} records
          </div>
        )}
      </section>
    </Page>
  )
}

function CandidateTable({rows,compact=false,caseStates={}}) {
  return <div className="table-wrapper"><table className={compact?'priority-candidate-table':''}>
    <thead><tr>{(compact?['Patient','Condition','Jurisdiction','Priority Assessment','Workflow Status','Action']:['FHIR Patient ID','Patient','Condition','Jurisdiction','Priority Assessment','FHIR Activity Date','Workflow Status','Action']).map(label=><th key={label}>{label}</th>)}</tr></thead>
    <tbody>{rows.map(candidate=>{
      const status=caseStates[candidate.id]?.status||candidate.status
      return <tr key={candidate.id}>
        <td><div className="table-patient"><div className="small-avatar">{candidate.initials}</div><div><b>{candidate.patient}</b><small>{candidate.id}</small></div></div></td>
        {compact?<><td><span className="condition-pill">{candidate.condition}</span></td><td>{candidate.jurisdiction}</td><td><Badge value={candidate.priority}/></td><td><Badge value={status}/></td></>:<><td>{candidate.patient}</td><td>{candidate.condition}</td><td>{candidate.jurisdiction}</td><td><Badge value={candidate.priority}/></td><td>{candidate.detected}</td><td><Badge value={status}/></td></>}
        <td><Link className="button small secondary" to={`/candidates/${candidate.id}`}>View</Link></td>
      </tr>
    })}</tbody>
  </table></div>
}
function Badge({value}) { let key=value.toLowerCase().replaceAll(' ','-'); return <span className={`badge ${key}`}>{value}</span> }
function Candidates({caseStates}) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('All statuses')
  const [priority, setPriority] = useState('All priorities')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10
  const rows = seedCandidates.map(candidate => ({
    ...candidate,
    status: caseStates[candidate.id]?.status || candidate.status,
  }))
  const priorities = [...new Set(rows.map(candidate => candidate.priority).filter(Boolean))]
  const list = rows.filter(candidate => {
    const searchable = `${candidate.id} ${candidate.patient} ${(candidate.conditions || []).join(' ')} ${candidate.jurisdiction}`.toLowerCase()
    return searchable.includes(query.toLowerCase())
      && (status === 'All statuses' || candidate.status === status)
      && (priority === 'All priorities' || candidate.priority === priority)
  })
  const totalPages=Math.max(1,Math.ceil(list.length/pageSize))
  const safePage=Math.min(currentPage,totalPages)
  const startIndex=(safePage-1)*pageSize
  const visibleRows=list.slice(startIndex,startIndex+pageSize)

  useEffect(()=>{setCurrentPage(1)},[query,status,priority])

  return <Page title="Candidates" subtitle="Patients represented by the complete FHIR seed dataset.">
    <div className="toolbar">
      <label className="search-field"><Search size={17}/><input placeholder="Search patients or conditions" value={query} onChange={event => setQuery(event.target.value)}/></label>
      <select aria-label="Filter by status" value={status} onChange={event => setStatus(event.target.value)}><option>All statuses</option>{[...new Set(rows.map(candidate => candidate.status))].map(value => <option key={value}>{value}</option>)}</select>
      <select aria-label="Filter by priority assessment" value={priority} onChange={event => setPriority(event.target.value)}><option>All priorities</option>{priorities.map(value => <option key={value}>{value}</option>)}</select>
      <span className="result-count">{list.length} patients</span>
    </div>
    <section className="panel">
      <CandidateTable rows={visibleRows} caseStates={caseStates}/>
      {list.length>pageSize&&<div style={{display:'flex',alignItems:'center',justifyContent:'center',gap:8,padding:'16px 0 4px',borderTop:'1px solid #e7ecef',marginTop:4}}>
        <button type="button" className="button small secondary" disabled={safePage===1} onClick={()=>setCurrentPage(page=>Math.max(1,page-1))}>Previous</button>
        <span className="muted" style={{fontSize:13,minWidth:78,textAlign:'center'}}>Page {safePage} of {totalPages}</span>
        <button type="button" className="button small secondary" disabled={safePage===totalPages} onClick={()=>setCurrentPage(page=>Math.min(totalPages,page+1))}>Next</button>
      </div>}
      {list.length>0&&<div style={{textAlign:'center',padding:'4px 0 12px',fontSize:13,color:'#718096'}}>
        Showing {startIndex+1}–{Math.min(startIndex+pageSize,list.length)} of {list.length} patients
      </div>}
    </section>
  </Page>
}
function Crumbs({active,id}) { const candidate=seedCandidates.find(item=>item.id===id)||seedCandidates[0]; const patientName=candidate?.patient||(seedCandidateLoad.status==='loading'?'Loading patient...':'Patient not found'); return <div className="crumbs"><Link to="/candidates">Candidates</Link><ChevronRight/><Link to={`/candidates/${id}`}>{patientName}</Link>{active!=='Candidate Details'&&<span><ChevronRight/>{active}</span>}</div> }
function EvidencePager({page,setPage,total,pageSize=10}) {
  const totalPages=Math.max(1,Math.ceil(total/pageSize))
  const start=total===0?0:(page-1)*pageSize+1
  const end=Math.min(page*pageSize,total)
  const goTo=next=>setPage(Math.min(totalPages,Math.max(1,next)))
  return <div className="evidence-pagination" style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:16,padding:'14px 4px 2px',borderTop:'1px solid #e7ecef',marginTop:4}}>
    <span className="muted" style={{fontSize:13}}>{total?`Showing ${start}–${end} of ${total} resources`:'No resources available'}</span>
    <div style={{display:'flex',alignItems:'center',gap:6}}>
      <button type="button" className="button small secondary" disabled={page===1} onClick={()=>goTo(page-1)}>Previous</button>
       <span className="muted" style={{fontSize:13,minWidth:78,textAlign:'center'}}>Page {page} of {totalPages}</span>
<button type="button" className="button small secondary" disabled={page===totalPages} onClick={()=>goTo(page+1)}>Next</button>
    </div>
  </div>
}
function CandidateDetails() {
  const candidate = useCandidate()
  const [resourcePage,setResourcePage]=useState(1)
  const [encounterPage,setEncounterPage]=useState(1)
  const resourcePageSize=10
  const encounterPageSize=10
  if (seedCandidateLoad.status !== 'ready') {
    return <Page title="Candidate Details" subtitle="Loading patient data from FHIR seed bundles."/>
  }
  const conditionSummary = candidate.conditions?.length ? candidate.conditions.join(' ┬╖ ') : candidate.condition
  const resourceSource = candidate.source_file || 'FHIR seed bundle'
  const resources=candidate.evidence||[]
  const encounters=candidate.encounters||[]
  const resourceStart=(resourcePage-1)*resourcePageSize
  const encounterStart=(encounterPage-1)*encounterPageSize
  const visibleResources=resources.slice(resourceStart,resourceStart+resourcePageSize)
  const visibleEncounters=encounters.slice(encounterStart,encounterStart+encounterPageSize)

  return <Page title="Candidate Details" subtitle="FHIR patient demographics, conditions, encounters, and source evidence.">
    <Crumbs active="FHIR Patient" id={candidate.id}/>
    <div className="candidate-banner"><div className="case-info"><div className="large-avatar">{candidate.initials}</div><div><h2>{candidate.patient} <Badge value="FHIR Seed"/></h2><p>Patient ID: {candidate.id} ┬╖ MRN: {candidate.mrn} ┬╖ DOB: {candidate.dob} ┬╖ {candidate.sex} ┬╖ Age {candidate.age}</p></div></div><div className="case-id"><small>FHIR SOURCE</small><b>{resourceSource}</b></div></div>
    <div className="two-column">
      <section className="panel pad"><PanelTitle title="Patient Information" sub="Values mapped from the FHIR Patient resource"/><div className="info-grid">{[['FULL NAME',candidate.patient],['MEDICAL RECORD NUMBER',candidate.mrn],['DATE OF BIRTH',candidate.dob],['SEX',candidate.sex],['AGE',candidate.age],['LANGUAGE',candidate.language],['CITY',candidate.patient_context?.city||'Not recorded'],['COUNTY',candidate.patient_context?.county||'Not recorded'],['STATE',candidate.patient_context?.state||'Not recorded'],['FACILITY',candidate.facility]].map(([label,value])=><Info key={label} label={label} value={value}/>)}</div></section>
      <section className="panel pad"><PanelTitle title="FHIR Record Summary" sub="Source data; reportability has not been evaluated"/><div className="info-grid">{[['CONDITIONS',conditionSummary],['DOCUMENTED JURISDICTION',candidate.jurisdiction],['SOURCE FILE',resourceSource],['WORKFLOW STATUS',candidate.status],['REPORTING RULE',candidate.rule],['DEADLINE',candidate.deadline]].map(([label,value])=><Info key={label} label={label} value={value}/>)}</div>{candidate.conditions?.some(condition=>condition.toLowerCase().includes('measles'))&&<Link className="button primary full" to={`/candidates/${candidate.id}/reporting-form`}>Open Texas Measles Form <ArrowRight size={15}/></Link>}</section>
    </div>
    <section className="panel">
      <PanelTitle title="FHIR Resource Evidence" sub="All FHIR resources for this patient are shown here only; paginated to keep the page compact." right={`${resources.length} resources`}/>
      <div className="table-wrapper"><table><thead><tr><th>Resource</th><th>Source</th></tr></thead><tbody>{visibleResources.map((item,index)=><tr key={`${candidate.id}-resource-${resourceStart+index}`}><td><b>{item}</b></td><td>{resourceSource}</td></tr>)}</tbody></table></div>
      <EvidencePager page={resourcePage} setPage={setResourcePage} total={resources.length} pageSize={resourcePageSize}/>
    </section>
    <section className="panel pad">
      <PanelTitle title="Encounters" sub="Encounter resources in this FHIR bundle; paginated when there are many records." right={`${encounters.length} encounters`}/>
      {visibleEncounters.length ? <div className="encounters">{visibleEncounters.map((encounter,index)=><div key={`${candidate.id}-encounter-${encounterStart+index}`}><b>{encounter.date} ┬╖ {encounter.type}</b><p>{encounter.reason}</p><small>{encounter.status} ┬╖ {encounter.facility}</small></div>)}</div> : <div className="empty-state"><p>No Encounter resources were included in this bundle.</p></div>}
      {encounters.length>0&&<EvidencePager page={encounterPage} setPage={setEncounterPage} total={encounters.length} pageSize={encounterPageSize}/>} 
    </section>
  </Page>
}
function PanelTitle({title,sub,right}) { return <div className="panel-header"><div><h3>{title}</h3>{sub&&<p>{sub}</p>}</div>{right&&<small className="muted">{right}</small>}</div> }
function Info({label,value}) { return <div className="info"><small>{label}</small><b>{value}</b></div> }
function useCandidate() {
  const {id} = useParams()
  return seedCandidates.find(candidate => candidate.id === id) || seedCandidates[0] || {
    id,
    patient: 'Loading FHIR patient...',
    initials: '',
    mrn: 'Not loaded',
    dob: 'Not loaded',
    sex: 'Not loaded',
    age: 'N/A',
    facility: 'Not loaded',
    condition: 'Not loaded',
    jurisdiction: 'Not loaded',
    priority: 'Not assessed',
    detected: 'Not recorded',
    status: 'Loading',
    rule: 'Not evaluated',
    deadline: 'Not calculated',
    confidence: 'Not available',
    evidence: [],
    laboratory_evidence: [],
    language: 'Not recorded',
    encounters: [],
  }
}
function StepPage({title,subtitle,children,id}) { return <Page title={title} subtitle={subtitle}><Crumbs active={title} id={id}/>{children}</Page> }
function Extraction() { const c=useCandidate(),[done,setDone]=useState(false),nav=useNavigate(); return <StepPage title="Reporting Data Extraction" subtitle="Cross-encounter synthesis and source-backed extraction for the Texas Measles CRF." stage="Data Extraction" id={c.id}><div className="success-banner"><CheckCircle2/><div><b>{done?'Extraction complete':'Ready to extract reporting data'}</b><p>{done?'Reporting data received from EHR / ELR. Evidence has been mapped to reporting fields.':'SIGNAL will gather available synthetic patient information from connected clinical sources.'}</p></div></div><div className="extract-grid"><section className="panel navy-panel"><small>LONGITUDINAL CROSS-ENCOUNTER SYNTHESIS</small><h2>Clinical evidence is ready for reporting.</h2><p>SIGNAL analyzed 4 patient encounters and mapped available clinical evidence to the Texas Measles Case Report Form requirements.</p><div className="stat-row"><div><b>4</b><small>Encounters Analyzed</small></div><div><b>5</b><small>Evidence Items</small></div><div><b>6</b><small>CRF Sections</small></div></div></section><section className="panel pad"><PanelTitle title="Clinical Visualization" sub="Documented clinical context"/><figure className="clinical-visual"><img src={anatomyDashboard} alt="Synthetic anatomy reference showing front and back views with highlighted clinical findings"/><figcaption>Sample anatomy reference ┬╖ synthetic demonstration visual</figcaption></figure><small className="muted">Visualization provides contextual reference for documented information.</small></section><section className="panel"><PanelTitle title="Source-Backed Extraction" sub="Evidence identified across available records" right={`${c.evidence?.length||0} resources`}/><p className="muted" style={{margin:'0 0 14px'}}>The complete FHIR resource evidence is maintained in one place on Candidate Details and is paginated there to avoid repeating a long evidence list across workflow pages.</p><Link className="button secondary" to={`/candidates/${c.id}`}>View FHIR Resource Evidence <ArrowRight size={15}/></Link></section><section className="panel pad"><PanelTitle title="Texas Measles CRF Coverage" sub="Reporting sections identified from available evidence"/>{['Patient Information','Demographics','Rash & Fever','Hospitalization','Laboratory Results','Exposure / Epidemiology'].map((e,i)=><div className="coverage-row" key={e}><span>{i===2||i===5?'!':'Γ£ô'}</span><b>{e}</b><Badge value={i===2||i===5?'Needs Verification':'Source-backed'}/></div>)}</section></div><div className="bottom-action"><span>Continue when extraction is complete.</span>{done?<button className="button primary" onClick={()=>nav(`/candidates/${c.id}/reporting-data`)}>Continue to Reporting Data <ArrowRight size={15}/></button>:<button className="button primary" onClick={()=>{setDone(true)}}>Run Extraction <ArrowRight size={15}/></button>}</div></StepPage> }
function ReportingData() { const c=useCandidate(),nav=useNavigate(); const fields=[['Patient & Administrative',`${c.patient} ┬╖ MRN ${c.mrn}`,'Clinical documentation'],['Clinical Presentation','Fever, rash, cough and coryza','Clinical documentation'],['Diagnostic Evidence','Measles IgM Positive','Laboratory result ┬╖ Sep 12, 2026'],['Reporting & Jurisdiction','Measles ┬╖ Texas DSHS','Reporting rule / jurisdiction configuration']]; return <StepPage title="Reporting Data" subtitle="Review mapped reporting values and source evidence." stage="Reporting Data" id={c.id}><div className="two-column"><section className="panel reporting-data-card"><PanelTitle title="Reporting Data" sub="Mapped values from available candidate records" right="28 Fields Validated"/>{fields.map(([a,b,s])=><div className="reporting-data-row" key={a}><div className="reporting-data-label"><span/><b>{a}</b></div><div className="reporting-data-value"><small>VALUE</small><p>{b}</p></div><div className="reporting-data-source"><small>SOURCE</small><p>{s}</p></div><div className="reporting-data-status"><Badge value="Source-backed"/></div></div>)}</section><section className="panel pad"><PanelTitle title="Extraction Summary" sub="Current reporting package status"/><div className="summary-stats"><div><b>28</b><small>Valid</small></div><div><b>0</b><small>Need Attention</small></div><div><b>0</b><small>Blocking</small></div></div><div className="success-banner compact"><CheckCircle2/><div><b>Evidence Updated</b><p>Available source evidence mapped to report fields.</p></div></div>{['Patient identifiers complete','Jurisdiction and condition mapped','Laboratory evidence linked','Source evidence available'].map(x=><div className="check-row" key={x}><Check size={15}/>{x}<span>Complete</span></div>)}</section><section className="panel"><PanelTitle title="Source Evidence" sub="Records used to populate reporting values" right="3 source records"/>{[['Sep 16, 2026','Clinical note and hospitalization evidence'],['Sep 12, 2026','Measles IgM Positive ┬╖ Specimen date available'],['Sep 10, 2026','Initial symptom and presentation documentation']].map(([a,b])=><div className="source-row" key={a}><b>{a}</b><span>{b}</span><a href="#evidence">View Source</a></div>)}</section><section className="panel pad"><PanelTitle title="Next Step" sub="Reviewer decision and validation"/><p>Confirm mapped values and supporting records in Review &amp; Validation.</p><button className="button primary full" onClick={()=>nav(`/candidates/${c.id}/review`)}>Proceed to Review &amp; Validation <ArrowRight size={15}/></button></section></div><div className="bottom-action"><Link className="button secondary" to={`/candidates/${c.id}/extraction`}><ArrowLeft size={15}/> Back</Link><button className="button primary" onClick={()=>nav(`/candidates/${c.id}/review`)}>Continue to Review <ArrowRight size={15}/></button></div></StepPage> }
function Review({addToQueue}) { const c=useCandidate(),[checked,setChecked]=useState(false),[ready,setReady]=useState(false),nav=useNavigate(); const queued=JSON.parse(localStorage.getItem('signalQueue')||'[]').includes(c.id); return <StepPage title="Review & Validation" subtitle="Review mapped reporting values, validation checks, and source evidence before authorized submission." stage="Review & Validation" id={c.id}><div className="two-column"><section className="panel"><PanelTitle title="Reporting Data" sub="Mapped values from available candidate records" right="28 Fields Validated"/>{[['Patient & Administrative',`${c.patient} ┬╖ MRN ${c.mrn}`],['Clinical Presentation','Fever, rash, cough and coryza'],['Diagnostic Evidence','Measles IgM Positive'],['Reporting & Jurisdiction','Measles ┬╖ Texas DSHS']].map(([a,b])=><div className="review-row" key={a}><span className="green-dot"/><b>{a}</b><p>{b}</p><small>Source: {a.includes('Diagnostic')?'Laboratory result ┬╖ Sep 12, 2026':'Clinical documentation'}</small></div>)}</section><section className="panel pad"><PanelTitle title="Validation Summary" sub="Current reporting package status"/><div className="summary-stats"><div><b>28</b><small>Valid</small></div><div><b>0</b><small>Need Attention</small></div><div><b>0</b><small>Blocking</small></div></div><div className="warning-note">Γ£ô All reporting fields have supporting evidence.</div>{['Required patient identifiers complete','Jurisdiction and condition mapped','Laboratory evidence linked','All reporting fields have supporting evidence'].map(x=><div className="check-row" key={x}><Check size={15}/>{x}<span>Complete</span></div>)}</section><section className="panel"><PanelTitle title="Source Evidence" sub="Records used to populate reporting values" right="3 source records"/>{['Clinical note and hospitalization evidence','Measles IgM Positive ┬╖ Specimen date available','Initial symptom and presentation documentation'].map((s,i)=><div className="source-row" key={s}><b>Sep {16-i*2}, 2026</b><span>Γ£ô &nbsp;{s}</span><a href="#source">View Source</a></div>)}</section><section className="panel pad"><PanelTitle title="Reviewer Decision" sub="Choose how to proceed" right="Ready"/><label className="radio-card"><input type="radio" checked={ready} onChange={()=>setReady(true)}/><span><b>Ready to Add to Queue</b><small>All available reporting information has been reviewed.</small></span></label><label className="review-confirm"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/> I reviewed the reporting values and available source evidence.</label><div className="audit-note">Reviewer: Sarah Mitchell, RN ┬╖ Decision will be recorded in the audit trail.</div></section></div><div className="bottom-action"><span>{queued?'Candidate is in the Reporting Queue.':'Confirm your reviewer decision before adding the report to the queue.'}</span><button disabled={!checked||!ready||queued} className="button primary" onClick={()=>{addToQueue(c.id);nav('/reporting-queue')}}>{queued?'Added to Queue':'Add to Reporting Queue'} <ArrowRight size={15}/></button></div></StepPage> }
function ReportingQueue({queue}) { const rows=seedCandidates.filter(c=>queue.includes(c.id)); return <Page title="Reporting Queue" subtitle="Reviewer-approved reporting packages ready for submission."><section className="panel"><PanelTitle title="Ready for Submission" sub="Candidates added to the reporting queue" right={`${rows.length} queued`}/>{rows.length?<CandidateTable rows={rows}/>:<div className="empty-state"><ClipboardList size={32}/><h3>No candidates in the queue yet</h3><p>Complete Review &amp; Validation and add an approved candidate to begin.</p><Link className="button primary" to="/candidates">Browse Candidates</Link></div>}</section></Page> }
function Submissions({queue}) { return <Page title="Submissions" subtitle="Track reporting packages and acknowledgements from public health agencies."><section className="panel"><PanelTitle title="Submission Activity" sub="Synthetic demo data ┬╖ no real PHA connection" right="Demo Environment"/>{queue.length?seedCandidates.filter(c=>queue.includes(c.id)).map(c=><div className="source-row" key={c.id}><b>{c.id} ┬╖ {c.patient}</b><span>{c.condition} ┬╖ {c.jurisdiction}</span><Badge value="Ready to Submit"/></div>):<div className="empty-state"><FileCheck2 size={32}/><h3>No submissions yet</h3><p>Items added to the Reporting Queue will appear here when submission begins.</p><Link className="button secondary" to="/reporting-queue">Open Reporting Queue</Link></div>}</section></Page> }
function Cases() {
  const [currentPage,setCurrentPage] = useState(1)
  const pageSize = 10
  const conditionCounts = useMemo(() => {
    const counts = seedCandidates.reduce((result, candidate) => {
      for (const condition of candidate.conditions || [candidate.condition]) {
        if (!condition || condition.toLowerCase().includes('rabies')) continue
        result[condition] = (result[condition] || 0) + 1
      }
      return result
    }, {})
    return Object.entries(counts).sort((a,b) => b[1] - a[1])
  }, [seedCandidates.length])
  const totalPages = Math.max(1, Math.ceil(conditionCounts.length / pageSize))
  const safePage = Math.min(currentPage,totalPages)
  const visible = conditionCounts.slice((safePage-1)*pageSize, safePage*pageSize)
  useEffect(() => { if (currentPage > totalPages) setCurrentPage(totalPages) }, [currentPage,totalPages])

  return <Page title="Cases" subtitle="Patient cases grouped by condition for investigation and public health follow-up.">
    <div className="metrics-grid">
      <Metric label="PATIENT CASES" value={seedCandidates.length} note="Patients represented in the case registry"/>
      <Metric label="CONDITIONS" value={conditionCounts.length} note="Conditions available for case review" tone="orange"/>
      <Metric label="MEASLES CASES" value={seedCandidates.filter(candidate => candidate.condition?.toLowerCase().includes('measles')).length} note="Current Texas measles candidates" tone="green"/>
    </div>
    <section className="panel">
      <PanelTitle title="Patients by condition" sub="Case-oriented view of the documented patient-condition distribution" right={`${conditionCounts.length} conditions`}/>
      <div className="table-wrapper"><table><thead><tr><th>CONDITION</th><th>PATIENTS</th><th>CASE FOCUS</th></tr></thead><tbody>{visible.map(([condition,count])=><tr key={condition}><td><b>{condition}</b></td><td>{count}</td><td><Badge value={condition.toLowerCase().includes('measles')?'Priority reporting condition':'Case review'}/></td></tr>)}</tbody></table></div>
      <div className="pagination-bar"><span>Showing {conditionCounts.length ? (safePage-1)*pageSize+1 : 0}–{Math.min(safePage*pageSize,conditionCounts.length)} of {conditionCounts.length} conditions</span><div className="pagination-controls"><button className="button small secondary" disabled={safePage===1} onClick={()=>setCurrentPage(page=>Math.max(1,page-1))}><ArrowLeft size={14}/> Previous</button><span>Page {safePage} of {totalPages}</span><button className="button small secondary" disabled={safePage===totalPages} onClick={()=>setCurrentPage(page=>Math.min(totalPages,page+1))}>Next <ArrowRight size={14}/></button></div></div>
    </section>
    <section className="panel"><PanelTitle title="Case investigation focus" sub="Active reporting scope"/><div className="info-grid"><div><span style={{display:'block',fontSize:12,color:'#7c8da6'}}>JURISDICTION</span><b>Texas</b><small>Documented jurisdiction</small></div><div><span style={{display:'block',fontSize:12,color:'#7c8da6'}}>PRIMARY CONDITION</span><b>Measles</b><small>Primary reporting condition in the seed dataset</small></div><div><span style={{display:'block',fontSize:12,color:'#7c8da6'}}>NEXT STEP</span><b>Candidate review</b><small>Use Candidates for patient-level evidence and reporting workflow</small></div></div></section>
  </Page>
}

function Investigation() { return <Module title="Investigation" sub="Review longitudinal evidence and investigation activity." icon={Search} items={['Clinical evidence timeline','Exposure history documented','Laboratory result linked']}/> }
function Governance() { return <GovernanceOverview/> }
function Module({title,sub,icon:Icon,items}) { return <Page title={title} subtitle={sub}><section className="panel pad module-panel"><Icon size={25}/><h3>{title} overview</h3>{items.map(x=><div className="check-row" key={x}><CheckCircle2 size={16}/>{x}</div>)}</section></Page> }
function ClinicalReview({addToQueue,caseStates}) { const c=useCandidate(),[checked,setChecked]=useState(false),[ready,setReady]=useState(false),[confirmed,setConfirmed]=useState(false); const status=caseStates[c.id]?.status;const alreadyQueued=['Pending Admin Verification','Ready for Submission','Verified','Submitted','Acknowledged'].includes(status);return <StepPage title="Review & Validation" subtitle="Review mapped reporting values, validation checks, and source evidence." stage="Review & Validation" id={c.id}><div className="two-column"><section className="panel"><PanelTitle title="Reporting Data" sub="Mapped values from available candidate records" right="28 Fields Validated"/>{[['Patient & Administrative',`${c.patient} ┬╖ MRN ${c.mrn}`],['Clinical Presentation','Fever, rash, cough and coryza'],['Diagnostic Evidence','Measles IgM Positive'],['Reporting & Jurisdiction',`${c.condition} ┬╖ ${c.jurisdiction}`]].map(([a,b])=><div className="review-row" key={a}><span className="green-dot"/><b>{a}</b><p>{b}</p><small>Source: {a.includes('Diagnostic')?'Laboratory result ┬╖ Sep 12, 2026':'Clinical documentation'}</small></div>)}</section><section className="panel pad"><PanelTitle title="Validation Summary" sub="Current reporting package status"/><div className="summary-stats"><div><b>28</b><small>Valid</small></div><div><b>0</b><small>Need Attention</small></div><div><b>0</b><small>Blocking</small></div></div>{['Required patient identifiers complete','Jurisdiction and condition mapped','Laboratory evidence linked','All reporting fields have supporting evidence'].map(x=><div className="check-row" key={x}><Check size={15}/>{x}<span>Complete</span></div>)}</section><section className="panel"><PanelTitle title="Source Evidence" sub="Records used to populate reporting values" right={`${c.evidence.length} source records`}/>{c.evidence.map((e,i)=><div className="source-row" key={e}><b>Sep {i===3?'12':'16'}, 2026</b><span>Γ£ô &nbsp;{e} ┬╖ {sources[i%sources.length]}</span><a href="#source">View Source</a></div>)}</section><section className="panel pad"><PanelTitle title="Human Verification" sub="Clinical reviewer decision" right="Required"/><label className="review-confirm"><input type="checkbox" checked={checked} disabled={alreadyQueued} onChange={e=>setChecked(e.target.checked)}/> I reviewed the reporting values and available source evidence.</label><label className="radio-card"><input type="radio" checked={ready} disabled={alreadyQueued} onChange={()=>setReady(true)}/><span><b>Ready to Add to Reporting Queue</b><small>Admin verification is required before submission.</small></span></label><div className="audit-note">Clinical Staff ┬╖ Decision recorded for admin verification.</div></section></div><div className="bottom-action"><span>{confirmed||alreadyQueued?<>Case added to Reporting Queue ┬╖ <b>{status==='Rejected / Returned for Correction'?'Returned for correction':'Pending Admin Verification'}</b></>:"Confirm your review before sending this case for admin verification."}</span><button disabled={!checked||!ready||alreadyQueued} className="button primary" onClick={()=>{addToQueue(c.id);nav('/dashboard')}}>{alreadyQueued?'Added to Queue':'Add to Reporting Queue'} <ArrowRight size={15}/></button></div></StepPage> }
function AdminQueue({queue,caseStates}) { const rows=queue.map(id=>seedCandidates.find(c=>c.id===id)).filter(Boolean);return <Page title="Reporting Queue" subtitle="Verify each case individually, then select ready cases for an optional batch submission."><div className="admin-callout">Individual verification is required. Batch submission is an optional POC workflow and may vary by jurisdiction.</div><section className="panel"><PanelTitle title="Queued Cases" sub="All cases submitted by Clinical Staff" right={`${rows.length} queued`}/><div className="table-wrapper"><table><thead><tr>{['Candidate','Condition','Jurisdiction / PHA','Queued At','Status','Action'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{rows.map(c=>{const s=caseStates[c.id]||{status:'Pending Admin Verification'};return <tr key={c.id}><td><div className="table-patient"><div className="small-avatar">{c.initials}</div><div><b>{c.patient}</b><small>{c.id}</small></div></div></td><td>{c.condition}</td><td>{c.jurisdiction}</td><td>{s.queuedAt||'ΓÇö'}</td><td><Badge value={s.status}/></td><td><Link className="button small secondary" to={`/reporting-queue/${c.id}/verify`}>{s.status==='Pending Admin Verification'?'Verify Case':'View Case'}</Link></td></tr>})}</tbody></table></div>{!rows.length&&<div className="empty-state"><ClipboardList size={30}/><h3>No cases waiting for admin verification</h3><p>Cases appear after Clinical Staff complete review.</p></div>}</section><div className="bottom-action"><span>Cases must be individually verified before they can be selected for submission.</span><Link className="button primary" to="/reporting-queue/batch">Batch Submission <ArrowRight size={15}/></Link></div></Page> }
function AdminVerification({caseStates,setCaseState}) { const c=useCandidate(),nav=useNavigate(),s=caseStates[c.id]||{status:'Pending Admin Verification'};const decide=(status)=>{setCaseState(c.id,{status,adminDecisionAt:new Date().toLocaleString(),adminReviewer:'Reporting Administrator'});nav('/reporting-queue')};return <Page title="Individual Case Verification" subtitle="Verify this candidate before it can be included in a submission batch."><Crumbs active="Individual Case Verification" id={c.id}/><div className="candidate-banner"><div className="case-info"><div className="large-avatar">{c.initials}</div><div><h2>{c.patient}</h2><p>{c.id} ┬╖ MRN {c.mrn} ┬╖ {c.condition}</p></div></div><div className="case-id"><small>ADMIN STATUS</small><Badge value={s.status}/></div></div><div className="two-column"><section className="panel pad"><PanelTitle title="Candidate / Patient Information" sub="Synthetic candidate record"/><div className="info-grid">{[['PATIENT',c.patient],['CANDIDATE ID',c.id],['MRN',c.mrn],['FACILITY',c.facility],['CONDITION',c.condition],['JURISDICTION / PHA',c.jurisdiction],['REPORTING RULE',c.rule],['DEADLINE',c.deadline]].map(([a,b])=><Info key={a} label={a} value={b}/>)}</div></section><section className="panel"><PanelTitle title="Reporting Data" sub="Mapped values for administrator review"/>{[['Patient','MRN '+c.mrn],['Clinical Presentation','Fever, rash, cough and coryza'],['Diagnostic Evidence',c.evidence.find(e=>e.toLowerCase().includes('igm'))||c.evidence[0]],['Jurisdiction',c.jurisdiction]].map(([a,b])=><div className="report-field" key={a}><div className="field-title"><span/><b>{a}</b></div><div className="field-columns"><p>{b}</p><small>Source-backed demo data</small></div></div>)}</section><section className="panel"><PanelTitle title="Clinical & Source Evidence" sub="Records provided for verification"/>{c.evidence.map((e,i)=><div className="source-row" key={e}><b>{i===3?'ELR':'EHR'}</b><span>{e} ┬╖ {sources[i%sources.length]}</span><Badge value="Source-backed"/></div>)}</section><section className="panel pad"><PanelTitle title="Validation Results" sub="Reporting package checks"/><div className="summary-stats"><div><b>28</b><small>Valid</small></div><div><b>0</b><small>Attention</small></div><div><b>0</b><small>Blocking</small></div></div>{['Identifiers complete','Jurisdiction mapped','Evidence linked'].map(x=><div className="check-row" key={x}><Check size={15}/>{x}<span>Complete</span></div>)}</section></div><section className="panel pad admin-decision"><PanelTitle title="Reviewer Decision" sub="Record an individual verification decision"/><div className="admin-actions"><button className="button primary" disabled={s.status==='Ready for Submission'||s.status==='Submitted'} onClick={()=>decide('Ready for Submission')}>Approve for Submission</button><button className="button secondary" disabled={s.status==='Submitted'} onClick={()=>decide('Rejected / Returned for Correction')}>Return for Correction</button><span>Verified cases become eligible for batch selection.</span></div></section></Page> }
function BatchSubmissionOld({queue,caseStates,submitBatch}) { const [selected,setSelected]=useState([]),[result,setResult]=useState(null);const rows=queue.map(id=>seedCandidates.find(c=>c.id===id)).filter(c=>c&&['Ready for Submission','Verified'].includes(caseStates[c.id]?.status));const toggle=id=>setSelected(v=>v.includes(id)?v.filter(x=>x!==id):[...v,id]);return <Page title="Batch Submission" subtitle="Select individually verified cases for a configurable mock batch submission."><div className="admin-callout">PHA requirements vary. Grouped submission is enabled here as a configurable POC workflow.</div><section className="panel"><PanelTitle title="Ready for Submission" sub="Only individually approved cases can be selected" right={`${rows.length} eligible`}/><div className="table-wrapper"><table><thead><tr><th>Select</th><th>Candidate</th><th>Condition</th><th>Jurisdiction / PHA</th><th>Status</th></tr></thead><tbody>{rows.map(c=><tr key={c.id}><td><input type="checkbox" checked={selected.includes(c.id)} onChange={()=>toggle(c.id)}/></td><td>{c.id} ┬╖ {c.patient}</td><td>{c.condition}</td><td>{c.jurisdiction}</td><td><Badge value={caseStates[c.id]?.status}/></td></tr>)}</tbody></table></div>{!rows.length&&<div className="empty-state"><h3>No verified cases ready</h3><p>Complete individual verification in the Reporting Queue first.</p><Link className="button secondary" to="/reporting-queue">Return to Queue</Link></div>}</section><div className="bottom-action"><span>{result?<>Created <b>{result.id}</b> ┬╖ {result.submittedAt} ┬╖ {result.pha} ┬╖ {result.acknowledgement}</>:`${selected.length} verified case(s) selected`}</span><button className="button primary" disabled={!selected.length} onClick={()=>{setResult(submitBatch(selected,Object.fromEntries(selected.map(id=>[id,seedCandidates.find(c=>c.id===id)?.jurisdiction]))));setSelected([])}}>Submit Selected Cases <ArrowRight size={15}/></button></div></Page> }
function AdminSubmissions({queue,caseStates,batches,setCaseState}) { const rows=queue.map(id=>seedCandidates.find(c=>c.id===id)).filter(Boolean).filter(c=>['Submitted','Acknowledged'].includes(caseStates[c.id]?.status));return <Page title="Submission Status" subtitle="Track mock batch IDs, jurisdictional PHA delivery, and acknowledgements."><section className="panel"><PanelTitle title="Submission Batches" sub="Demo submissions ┬╖ no live PHA connection" right={`${batches.length} batches`}/>{batches.length?batches.map(b=><div className="batch-card" key={b.id}><div><b>{b.id}</b><small>{b.submittedAt} ┬╖ {b.pha}</small></div><Badge value={b.acknowledgement}/><span>{b.ids.length} case(s)</span></div>):<div className="empty-state"><FileCheck2 size={30}/><h3>No batch submissions yet</h3><p>Verified cases can be submitted from Batch Submission.</p><Link className="button secondary" to="/reporting-queue/batch">Open Batch Submission</Link></div>}</section><section className="panel"><PanelTitle title="Submitted Cases" sub="Case-level submission status"/>{rows.map(c=>{const s=caseStates[c.id];return <div className="source-row" key={c.id}><b>{c.id} ┬╖ {c.patient} ┬╖ {s.batchId}</b><span>{s.submittedAt} ┬╖ {s.pha}</span><Badge value={s.status}/>{s.status==='Submitted'&&<button className="button small secondary" onClick={()=>setCaseState(c.id,{status:'Acknowledged',acknowledgement:'Acknowledged'})}>Mark Acknowledged</button>}</div>})}</section></Page> }
function AdminDashboard({queue,caseStates}) { const ready=queue.filter(id=>caseStates[id]?.adminVerificationStatus==='Verified').length,submitted=queue.filter(id=>['Submitted','Acknowledged'].includes(caseStates[id]?.submissionStatus)).length;return <Page title="Reporting Administration" subtitle="Verify completed clinical reports and manage public health submissions."><div className="metrics-grid"><Metric label="QUEUED CASES" value={queue.length} note="Awaiting or in admin review"/><Metric label="PENDING VERIFICATION" value={queue.filter(id=>(caseStates[id]?.adminVerificationStatus||'Pending Admin Verification')==='Pending Admin Verification').length} note="Requires individual review" tone="orange"/><Metric label="READY FOR SUBMISSION" value={ready} note="Individually verified" tone="green"/><Metric label="SUBMITTED" value={submitted} note="Awaiting PHA acknowledgement" tone="blue"/></div><section className="panel"><div className="panel-header"><div><h3>Admin Work Queue</h3><p>Open each case to verify the reporting package individually.</p></div><Link className="button primary" to="/admin/reporting-queue">Open Reporting Queue <ArrowRight size={15}/></Link></div></section><section className="panel"><PanelTitle title="Recent Batches" sub="Mock PHA submission activity"/><div className="panel-header"><Link className="text-link" to="/admin/submissions">View Submission Status <ArrowRight size={14}/></Link></div></section></Page> }
function QueueConfirmation({caseStates}) { const c=useCandidate(),s=caseStates[c.id]||{};return <Page title="Case Added to Reporting Queue" subtitle="Clinical review and validation are complete."><section className="panel handoff-panel"><div className="handoff-check"><CheckCircle2 size={28}/></div><h2>{c.id} ΓÇö {c.patient}</h2><p>The case has been added to the Reporting Queue and is now awaiting Reporting Administrator verification.</p><StatusLine value={s.adminVerificationStatus||'Pending Admin Verification'}/><div className="handoff-note">Clinical Staff responsibilities for this case are complete.</div><Link className="button primary" to="/dashboard">Return to Clinical Staff Dashboard <ArrowRight size={15}/></Link></section></Page> }
function StatusLine({value}) { return <div className="handoff-status"><small>ADMIN VERIFICATION</small><Badge value={value}/></div> }
function ClinicalReviewPage({addToQueue,caseStates}) {
  const c=useCandidate(),nav=useNavigate(),s=caseStates[c.id]||{},[checked,setChecked]=useState(false),[attestedAt,setAttestedAt]=useState('')
  const reviewerName=getUserDisplayName(), reviewerRole='Clinical Staff'
  const handleAttestation=e=>{
    const value=e.target.checked
    setChecked(value)
    setAttestedAt(value?new Date().toLocaleString():'')
  }
  if(s.adminVerificationStatus==='Pending Admin Verification'||s.adminVerificationStatus==='Verified'||s.submissionStatus==='Submitted'||s.submissionStatus==='Acknowledged')return <Navigate to={`/queue-confirmation/${c.id}`} replace/>
  return <StepPage title="Review & Validation" subtitle="Review mapped values and evidence before completing clinical verification." id={c.id}>
    <div className="two-column">
      <section className="panel"><PanelTitle title="Reporting Data" sub="Mapped report information" right="28 Fields Validated"/>{[['Patient',`${c.patient} ┬╖ MRN ${c.mrn}`],['Condition',c.condition],['Clinical Presentation','Fever, cough, generalized rash'],['Jurisdiction / PHA',c.jurisdiction]].map(([a,b])=><div className="review-row" key={a}><span className="green-dot"/><b>{a}</b><p>{b}</p><small>Source-backed synthetic reporting data</small></div>)}</section>
      <section className="panel"><PanelTitle title="Validation Results" sub="All required checks completed"/>{['Required identifiers complete','Jurisdiction and condition mapped','Source evidence linked','No blocking validation issues'].map(x=><div className="check-row" key={x}><Check size={15}/>{x}<span>Complete</span></div>)}</section>
      <section className="panel"><PanelTitle title="Evidence Available" sub="FHIR resource evidence is maintained in one location" right={`${c.evidence?.length||0} resources`}/><p className="muted" style={{margin:'0 0 14px'}}>To avoid duplicate long evidence lists, the complete FHIR Resource Evidence table is shown only on Candidate Details and is paginated there.</p><Link className="button secondary" to={`/candidates/${c.id}`}>View FHIR Resource Evidence <ArrowRight size={15}/></Link></section>
      <section className="panel pad">
        <PanelTitle title="Human Verification & Attestation" sub="Clinical Staff verification is required before queueing" right="Required"/>
        <div className="reviewer-card" style={{marginBottom:14}}>
          <div><small className="muted">CLINICAL REVIEWER</small><strong style={{display:'block',fontSize:16,marginTop:4}}>{reviewerName}</strong></div>
          <div><small className="muted">ROLE</small><strong style={{display:'block',fontSize:14,marginTop:4}}>{reviewerRole}</strong></div>
          <div><small className="muted">VERIFICATION STATUS</small><strong style={{display:'block',fontSize:14,marginTop:4}}>{checked?'Attested':'Pending Attestation'}</strong></div>
        </div>
        <label className="review-confirm"><input type="checkbox" checked={checked} onChange={handleAttestation}/> I reviewed the reporting values and source evidence and attest that the information is ready for reporting queue review.</label>
        <div className="audit-note">Reviewer: <b>{reviewerName}</b> ┬╖ Clinical Staff{attestedAt&&<> ┬╖ Attested: {attestedAt}</>}</div>
      </section>
    </div>
    <div className="bottom-action"><span>{checked?'Clinical Staff attestation complete. The case can now be added to the Reporting Queue for administrator verification.':'Complete the Clinical Staff attestation above to enable the Reporting Queue action.'}</span><button disabled={!checked} className="button primary" onClick={()=>{addToQueue(c.id);nav('/dashboard')}}>{checked?'Add to Reporting Queue':'Attestation Required'} <ArrowRight size={15}/></button></div>
  </StepPage>
}
function FinalAdminQueue({queue,caseStates,submitBatch}) {
  const [tab,setTab]=useState('All Cases'),[search,setSearch]=useState(''),[filters,setFilters]=useState({condition:'',jurisdiction:'',priority:'',status:'',date:''}),[selected,setSelected]=useState([]),[batchResult,setBatchResult]=useState(null)
  const rows=useMemo(()=>queue.map(id=>seedCandidates.find(candidate=>candidate.id===id)).filter(Boolean).map(candidate=>({candidate,state:caseStates[candidate.id]||{}})),[queue,caseStates])
  const stateOf=({state})=>({admin:state.adminVerificationStatus||'Pending Admin Verification',submission:state.submissionStatus||'Not Submitted'})
  const isReady=row=>{const status=stateOf(row);return status.admin==='Verified'&&status.submission==='Ready for Submission'}
  const pendingCount=rows.filter(row=>stateOf(row).admin==='Pending Admin Verification').length
  const verifiedCount=rows.filter(row=>stateOf(row).admin==='Verified').length
  const readyRows=rows.filter(isReady),submittedCount=rows.filter(row=>['Submitted','Acknowledged'].includes(stateOf(row).submission)).length
  const tabRows=rows.filter(row=>{const {admin,submission}=stateOf(row);if(tab==='Pending Verification')return admin==='Pending Admin Verification';if(tab==='Ready for Submission')return admin==='Verified'&&submission==='Ready for Submission';if(tab==='Submitted')return ['Submitted','Acknowledged'].includes(submission);return true})
  const visibleRows=tabRows.filter(({candidate:c,state:s})=>{
    const q=search.trim().toLowerCase(),date=new Date(c.detected).toISOString().slice(0,10),status=s.adminVerificationStatus||'Pending Admin Verification'
    return (!q||c.id.toLowerCase().includes(q)||c.patient.toLowerCase().includes(q))&&(!filters.condition||c.condition===filters.condition)&&(!filters.jurisdiction||c.jurisdiction===filters.jurisdiction)&&(!filters.priority||c.priority===filters.priority)&&(!filters.status||status===filters.status||(s.submissionStatus||'Not Submitted')===filters.status)&&(!filters.date||date===filters.date)
  })
  const updateFilter=(key,value)=>setFilters(current=>({...current,[key]:value}))
  const toggle=id=>setSelected(current=>current.includes(id)?current.filter(item=>item!==id):[...current,id])
  const selectAll=()=>setSelected(selected.length===readyRows.length?[]:readyRows.map(({candidate})=>candidate.id))
  const submitSelected=()=>{const eligible=selected.filter(id=>{const state=caseStates[id]||{};return state.adminVerificationStatus==='Verified'&&state.submissionStatus==='Ready for Submission'});if(!eligible.length)return;const phaByCase=Object.fromEntries(eligible.map(id=>[id,seedCandidates.find(candidate=>candidate.id===id)?.jurisdiction]));const result=submitBatch(eligible,phaByCase);if(result){setBatchResult(result);setSelected([])}}
  const tabs=[['All Cases',rows.length],['Pending Verification',pendingCount],['Ready for Submission',readyRows.length],['Submitted',submittedCount]]
  const unique=(key)=>[...new Set(rows.map(({candidate})=>candidate[key]).filter(Boolean))]
  return <Page title="Reporting Queue" subtitle="Review and verify completed cases before submitting them to the Public Health Authority.">
    <div className="queue-heading-action"><span>Demo queue data ┬╖ refreshed from the current case registry</span><button className="button small secondary queue-refresh" onClick={()=>window.location.reload()}><RefreshCw size={13}/> Refresh</button></div>
    <section className="metrics-grid queue-summary"><Metric label="PENDING VERIFICATION" value={pendingCount} note="Requires individual review" tone="orange"/><Metric label="VERIFIED" value={verifiedCount} note="Admin decision recorded" tone="blue"/><Metric label="READY FOR SUBMISSION" value={readyRows.length} note="Eligible for selection" tone="green"/><Metric label="SUBMITTED" value={submittedCount} note="Submitted or acknowledged" tone="blue"/></section>
    <section className="panel queue-panel"><div className="queue-tabs" role="tablist" aria-label="Reporting queue status">{tabs.map(([label,count])=><button key={label} role="tab" aria-selected={tab===label} className={tab===label?'selected':''} onClick={()=>setTab(label)}>{label}<span>{count}</span></button>)}</div>
      <div className="queue-filters"><label className="queue-search"><Search size={15}/><input aria-label="Search Candidate ID or Name" placeholder="Search Candidate ID / Name" value={search} onChange={event=>setSearch(event.target.value)}/></label><select aria-label="Condition filter" value={filters.condition} onChange={event=>updateFilter('condition',event.target.value)}><option value="">All Conditions</option>{unique('condition').map(value=><option key={value}>{value}</option>)}</select><select aria-label="Jurisdiction filter" value={filters.jurisdiction} onChange={event=>updateFilter('jurisdiction',event.target.value)}><option value="">All Jurisdictions</option>{unique('jurisdiction').map(value=><option key={value}>{value}</option>)}</select><select aria-label="Priority filter" value={filters.priority} onChange={event=>updateFilter('priority',event.target.value)}><option value="">All Priorities</option>{unique('priority').map(value=><option key={value}>{value}</option>)}</select><select aria-label="Status filter" value={filters.status} onChange={event=>updateFilter('status',event.target.value)}><option value="">All Statuses</option>{['Pending Admin Verification','Verified','Returned for Correction','Not Submitted','Ready for Submission','Submitted','Acknowledged'].map(value=><option key={value}>{value}</option>)}</select><input aria-label="Date filter" type="date" value={filters.date} onChange={event=>updateFilter('date',event.target.value)}/></div>
      <div className="queue-table-title"><div><h3>{tab}</h3><p>Each case is reviewed individually before it becomes eligible for submission.</p></div><span>{visibleRows.length} case{visibleRows.length===1?'':'s'}</span></div>
      <div className="table-wrapper queue-table-wrap"><table className="queue-table"><thead><tr><th className="queue-select-col">Select</th><th>Case</th><th>Condition</th><th>Jurisdiction</th><th>Clinical Review</th><th>Admin Verification</th><th>Submission</th><th>Action</th></tr></thead><tbody>{visibleRows.map(({candidate:c,state:s})=>{const ready=isReady({candidate:c,state:s}),admin=s.adminVerificationStatus||'Pending Admin Verification',submission=s.submissionStatus||'Not Submitted';return <tr key={c.id}><td className="queue-select-col"><input type="checkbox" aria-label={`Select ${c.id} for submission`} checked={selected.includes(c.id)} disabled={!ready} onChange={()=>toggle(c.id)}/></td><td><b>{c.id}</b><small>{c.patient}</small></td><td>{c.condition}</td><td>{c.jurisdiction}</td><td><Badge value={s.clinicalReviewStatus||'Complete'}/></td><td><Badge value={admin==='Pending Admin Verification'?'Pending':admin==='Returned for Correction'?'Returned for Correction':admin}/></td><td><Badge value={submission}/></td><td><Link className="button small secondary" to={`/admin/reporting-queue/${c.id}`}>Review Case <ArrowRight size={13}/></Link></td></tr>})}</tbody></table></div>
      {!visibleRows.length&&<div className="empty-state queue-empty"><ClipboardList size={28}/><h3>{tab==='Pending Verification'?'No cases pending verification.':tab==='Ready for Submission'?'No cases are currently ready for submission.':tab==='Submitted'?'No cases have been submitted yet.':'No cases match these filters.'}</h3><p>{tab==='Pending Verification'?'All queued cases have an administrator decision.':'Try another status tab or adjust your search and filters.'}</p></div>}
    </section>
    {readyRows.length>0&&<section className="panel queue-batch-panel"><div className="queue-batch-copy"><div><span className="queue-batch-kicker">READY FOR SUBMISSION</span><h3>{readyRows.length} {readyRows.length===1?'case is':'cases are'} ready for submission</h3><p>Select individually verified cases and submit them together. Batch submission is configurable for this POC; PHA requirements may differ.</p></div><div className="queue-batch-actions"><button className="button secondary small" onClick={selectAll}><Check size={13}/>{selected.length===readyRows.length?'Clear Selection':'Select All Verified'}</button><button className="button primary small" disabled={!selected.length} onClick={submitSelected}>Submit Selected Cases <ArrowRight size={14}/></button></div></div><div className="queue-batch-meta"><span>{selected.length} selected ┬╖ Pending and returned cases cannot be selected</span><Link to="/admin/reporting-queue/batch">Open full submission view <ArrowRight size={13}/></Link></div>{batchResult&&<div className="queue-batch-result"><CheckCircle2 size={16}/><div><b>{batchResult.id} submitted</b><span>{batchResult.ids.length} case(s) ┬╖ {batchResult.pha} ┬╖ {batchResult.submittedAt} ┬╖ {batchResult.acknowledgement}</span></div><Link to="/admin/submissions">View submission status</Link></div>}</section>}
    {!readyRows.length&&batchResult&&<section className="panel queue-batch-result standalone"><CheckCircle2 size={16}/><div><b>{batchResult.id} submitted</b><span>{batchResult.ids.length} case(s) ┬╖ {batchResult.pha} ┬╖ {batchResult.submittedAt} ┬╖ {batchResult.acknowledgement}</span></div><Link to="/admin/submissions">View submission status</Link></section>}
  </Page>
}
function FinalAdminVerification({caseStates,setCaseState}) { const c=useCandidate(),s=caseStates[c.id]||{},nav=useNavigate(),adminStatus=s.adminVerificationStatus||'Pending Admin Verification';const update=status=>{const approved=status==='Verified';setCaseState(c.id,{adminVerificationStatus:status,submissionStatus:approved?'Ready for Submission':'Not Submitted',status:approved?'Ready for Submission':'Returned for Correction',adminReviewer:'Reporting Administrator',adminDecisionAt:new Date().toLocaleString()});nav('/admin/reporting-queue')};return <Page title="Individual Case Verification" subtitle="Review the complete reporting package before approval."><Crumbs active="Individual Case Verification" id={c.id}/><div className="candidate-banner"><div className="case-info"><div className="large-avatar">{c.initials}</div><div><h2>{c.patient}</h2><p>{c.id} ┬╖ MRN {c.mrn} ┬╖ {c.condition}</p></div></div><div className="case-id"><small>ADMIN VERIFICATION</small><Badge value={adminStatus}/></div></div><div className="two-column"><section className="panel pad"><PanelTitle title="Candidate Information" sub="Synthetic reporting candidate"/><div className="info-grid">{[['Candidate ID',c.id],['Patient',c.patient],['MRN',c.mrn],['DOB / Sex',`${c.dob} ┬╖ ${c.sex}`],['Facility',c.facility],['Condition',c.condition],['Jurisdiction / PHA',c.jurisdiction],['Reporting Rule',c.rule]].map(([a,b])=><Info key={a} label={a.toUpperCase()} value={b}/>)}</div></section><section className="panel"><PanelTitle title="Reporting Data" sub="Read-only values prepared by Clinical Staff"/>{[['Patient identifiers',`${c.patient} ┬╖ MRN ${c.mrn}`],['Clinical presentation','Fever, cough, generalized rash'],['Diagnostic evidence',c.evidence.find(e=>e.toLowerCase().includes('igm'))||c.evidence[0]],['Jurisdiction',c.jurisdiction]].map(([a,b])=><div className="report-field" key={a}><div className="field-title"><span/><b>{a}</b><Badge value="Source-backed"/></div><div className="field-columns"><p>{b}</p><small>Clinical reporting package</small></div></div>)}</section><section className="panel"><PanelTitle title="Evidence Available" sub="Complete FHIR resource evidence is maintained in one location" right={`${c.evidence?.length||0} resources`}/><p className="muted" style={{margin:'0 0 14px'}}>The full evidence list is available on Candidate Details, where it is paginated for easier review.</p><Link className="button secondary" to={`/candidates/${c.id}`}>View FHIR Resource Evidence <ArrowRight size={15}/></Link></section><section className="panel"><PanelTitle title="Extraction & Validation" sub="Clinical review package"/>{[['Clinical review',s.clinicalReviewStatus||'Complete'],['Extracted at',s.clinicalCompletedAt||'Demo extraction complete'],['Validation','28 valid ┬╖ 0 blocking'],['PHA destination',c.jurisdiction]].map(([a,b])=><div className="check-row" key={a}>{a}<span>{b}</span></div>)}</section></div><section className="panel pad admin-decision"><PanelTitle title="Admin Verification Decision" sub="This decision applies to this case only"/><div className="audit-note">Clinical reviewer: {s.clinicalReviewer||'Clinical Staff'} ┬╖ Completed: {s.clinicalCompletedAt||'Demo record'}<br/>Admin reviewer: {s.adminReviewer||'Not yet reviewed'} ┬╖ Decision: {s.adminDecisionAt||'Pending'}</div><div className="admin-actions"><button className="button primary" disabled={adminStatus==='Verified'||s.submissionStatus==='Submitted'} onClick={()=>update('Verified')}>Approve for Submission</button><button className="button secondary" disabled={s.submissionStatus==='Submitted'} onClick={()=>update('Returned for Correction')}>Return for Correction</button><span>Approval sets Admin Verification to Verified and Submission to Ready for Submission.</span></div></section></Page> }
function BatchSubmission({queue,caseStates,submitBatch}) { const [selected,setSelected]=useState([]),[result,setResult]=useState(null);const rows=queue.map(id=>seedCandidates.find(c=>c.id===id)).filter(c=>c&&caseStates[c.id]?.adminVerificationStatus==='Verified'&&caseStates[c.id]?.submissionStatus==='Ready for Submission');const toggle=id=>setSelected(v=>v.includes(id)?v.filter(x=>x!==id):[...v,id]);const toggleAll=()=>setSelected(selected.length===rows.length?[]:rows.map(c=>c.id));return <Page title="Ready for Submission" subtitle="Select individually verified cases for optional grouped PHA submission."><div className="admin-callout">Grouped submission is a configurable POC demonstration. It does not imply that a PHA requires batch submission.</div><section className="panel"><PanelTitle title="Verified Cases" sub="Only Admin Verification = Verified cases are eligible" right={`${rows.length} eligible`}/><div className="batch-toolbar"><label><input type="checkbox" disabled={!rows.length} checked={rows.length>0&&selected.length===rows.length} onChange={toggleAll}/> Select All Verified</label><span>{selected.length} selected</span></div><div className="table-wrapper"><table><thead><tr><th>Select</th><th>Candidate ID</th><th>Patient</th><th>Condition</th><th>PHA Destination</th><th>Admin Verification</th><th>Submission</th></tr></thead><tbody>{rows.map(c=><tr key={c.id}><td><input type="checkbox" checked={selected.includes(c.id)} onChange={()=>toggle(c.id)}/></td><td>{c.id}</td><td>{c.patient}</td><td>{c.condition}</td><td>{c.jurisdiction}</td><td><Badge value={caseStates[c.id].adminVerificationStatus}/></td><td><Badge value={caseStates[c.id].submissionStatus}/></td></tr>)}</tbody></table></div>{!rows.length&&<div className="empty-state"><h3>No verified cases are ready</h3><p>Pending and returned cases cannot be selected. Verify cases individually first.</p><Link className="button secondary" to="/admin/reporting-queue">Open Reporting Queue</Link></div>}</section><div className="bottom-action"><span>{result?<>Created <b>{result.id}</b> ┬╖ {result.submittedAt} ┬╖ {result.pha} ┬╖ {result.ids.length} case(s) ┬╖ Awaiting Acknowledgement</>:`${selected.length} verified case(s) selected`}</span><button className="button primary" disabled={!selected.length} onClick={()=>{const batch=submitBatch(selected);setResult(batch);setSelected([])}}>Submit Selected Cases <ArrowRight size={15}/></button></div></Page> }
function FinalAdminSubmissions({queue,caseStates,batches,setCaseState}) { const rows=queue.map(id=>seedCandidates.find(c=>c.id===id)).filter(Boolean).filter(c=>['Submitted','Acknowledged'].includes(caseStates[c.id]?.submissionStatus));return <Page title="Submission Status" subtitle="Track batch submission, PHA destination, and acknowledgement status."><section className="panel"><PanelTitle title="Submission Batches" sub="Mock submission records ┬╖ no live PHA connection" right={`${batches.length} batch(es)`}/>{batches.length?batches.map(b=><Link className="batch-card batch-link" key={b.id} to={`/admin/submissions/${b.id}`}><div><b>{b.id}</b><small>{b.submittedAt} ┬╖ {b.pha}</small></div><Badge value={b.acknowledgement}/><span>{b.ids.length} case(s)</span></Link>):<div className="empty-state"><FileCheck2 size={30}/><h3>No batch submissions yet</h3><p>Verified cases will appear in Ready for Submission.</p><Link className="button secondary" to="/admin/reporting-queue/batch">Open Ready for Submission</Link></div>}</section><section className="panel"><PanelTitle title="Submitted Cases" sub="Per-case submission status"/>{rows.map(c=>{const s=caseStates[c.id];return <div className="source-row" key={c.id}><b>{c.id} ┬╖ {c.patient} ┬╖ {s.batchId}</b><span>{s.submittedAt} ┬╖ {s.pha}</span><Badge value={s.submissionStatus}/>{s.submissionStatus==='Submitted'&&<button className="button small secondary" onClick={()=>setCaseState(c.id,{submissionStatus:'Acknowledged',status:'Acknowledged',acknowledgement:'Acknowledged'})}>Mark Acknowledged</button>}</div>})}</section></Page> }
function BatchDetail({batches}) { const {batchId}=useParams(),b=batches.find(item=>item.id===batchId);if(!b)return <Page title="Batch not found" subtitle="No matching mock submission batch."/>;return <Page title={`Submission ${b.id}`} subtitle="Mock PHA submission details."><Crumbs active={b.id} id={b.ids?.[0]||'CAND-001'}/><section className="panel pad"><div className="info-grid">{[['BATCH ID',b.id],['SUBMITTED AT',b.submittedAt],['PHA DESTINATION',b.pha],['CASES',b.ids.length],['SUBMISSION STATUS',b.status],['ACKNOWLEDGEMENT',b.acknowledgement]].map(([a,v])=><Info key={a} label={a} value={v}/>)}</div></section>{b.ids.map(id=>{const c=seedCandidates.find(x=>x.id===id);return c&&<div className="panel batch-card" key={id}><b>{c.id} ┬╖ {c.patient}</b><span>{c.condition} ┬╖ {c.jurisdiction}</span></div>})}</Page> }
function PasswordField({id}) {
  const [visible, setVisible] = useState(false)
  return <span className="password-field-control">
    <input id={id} name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" defaultValue={DEMO_PASSWORD} required/>
    <button type="button" className="password-visibility-toggle" aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible} title={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(value => !value)}>
      {visible ? <EyeOff size={16}/> : <Eye size={16} />}
    </button>
  </span>
}

function Login({onLogin}) {
  const navigate = useNavigate()
  const submit = (event, role) => {
    event.preventDefault()
    const username = new FormData(event.currentTarget).get('username')
    if (typeof username === 'string' && username.trim()) {
      localStorage.setItem('signal-user', JSON.stringify({ name: username.trim() }))
    }
    onLogin(role)
    navigate(role === ROLE_ADMIN ? '/admin/dashboard' : '/dashboard')
  }
  const renderRoleCard = (role, username, title, description) => (
    <form className="login-form login-role-card" onSubmit={event => submit(event, role)}>
      <span className="eyebrow">{role === ROLE_ADMIN ? 'REPORTING ADMIN' : 'CLINICAL STAFF'}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      <label>Email / Username<input name="username" type="text" autoComplete="username" defaultValue={username} required/></label>
      <label htmlFor={`${role}-password`}>Password<PasswordField id={`${role}-password`}/></label>
      <div className="form-options"><label><input type="checkbox" defaultChecked/> Remember me</label><a href="#forgot">Forgot password?</a></div>
      <button type="submit" className="button primary full">Login <ArrowRight size={16}/></button>
    </form>
  )

  return <div className="login-screen">
    <section className="login-aside">
      <div className="brand"><div className="brand-logo">S</div><div><b>SIGNAL</b><small>PUBLIC HEALTH INTELLIGENCE LAYER</small></div></div>
      <h1>Intelligent public health reporting for healthcare organizations</h1>
      <div className="login-stages">{[['01','Prepare','Organize source information for required fields.'],['02','Report','Prepare jurisdiction-specific reporting data.'],['03','Execute','Track submission, acknowledgement, and follow-up.']].map(([number,label,description])=><div key={number}><b>{number}</b><span><strong>{label}</strong><small>{description}</small></span></div>)}</div>
      <small>Demo Environment ┬╖ Synthetic Data</small>
    </section>
    <section className="login-role-options" aria-label="Choose a login role">
      {renderRoleCard(ROLE_CLINICAL, DEFAULT_CLINICAL_USERNAME, 'Clinical Staff', 'Identify and review reporting candidates.')}
      {renderRoleCard(ROLE_ADMIN, DEFAULT_ADMIN_USERNAME, 'Reporting Admin', 'Review, verify, and manage PHA submissions.')}
    </section>
  </div>
}
export default App
