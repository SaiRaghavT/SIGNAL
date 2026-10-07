const STORAGE_KEY = 'signal.reportingAdmin.demoSubmissions.v1'

function readDemoSubmissions() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

function getDemoSubmission(submissionId) {
  return readDemoSubmissions().find(item => item.submission_id === submissionId) || null
}

function createDemoSubmission(caseRecord) {
  const submissions = readDemoSubmissions()
  const now = new Date()
  const submissionId = `DEMO-${now.toISOString().replaceAll(/[-:.TZ]/g, '').slice(0, 14)}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`
  const submission = {
    demo_only: true,
    submission_id: submissionId,
    case_id: caseRecord.case_id,
    candidate_id: caseRecord.candidate_id,
    patient: caseRecord.patient || {},
    disease: caseRecord.disease || null,
    jurisdiction: caseRecord.jurisdiction || null,
    destination: caseRecord.jurisdiction ? `Demo only · ${caseRecord.jurisdiction}` : 'Demo destination',
    batch_id: null,
    channel: 'DEMO_LOCAL',
    status: 'SUBMITTED',
    acknowledgement_id: null,
    acknowledgement_status: 'PENDING',
    created_at: now.toISOString(),
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify([submission, ...submissions]))
  return submission
}

function acknowledgeDemoSubmission(submissionId) {
  const submissions = readDemoSubmissions()
  const updated = submissions.map(item => item.submission_id === submissionId
    ? { ...item, status: 'ACKNOWLEDGED', acknowledgement_status: 'ACKNOWLEDGED', acknowledgement_id: `DEMO-ACK-${Math.random().toString(36).slice(2, 10).toUpperCase()}`, acknowledged_at: new Date().toISOString() }
    : item)
  const result = updated.find(item => item.submission_id === submissionId)
  if (result) localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  return result || null
}

export { acknowledgeDemoSubmission, createDemoSubmission, getDemoSubmission, readDemoSubmissions }
