const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
let seedCandidatesRequest

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  headers.set('Accept', 'application/json')

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
  })
  const payload = response.status === 204 ? null : await response.json().catch(() => null)

  if (!response.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : `Request failed (${response.status})`
    throw new Error(detail)
  }

  return payload
}

const postJson = (path, body) => request(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export function processCandidateWorkflow(candidate) {
  return postJson('/api/candidate/process', {
    candidate_id: candidate.candidate_id || candidate.id,
  })
}

export const signalApi = {
  getHealth: () => request('/health'),
  getSeedFhirCandidates: () => {
    seedCandidatesRequest ??= request('/api/ingestion/fhir/seed-candidates')
    return seedCandidatesRequest
  },
  getCanonicalPatient: patientId => request(`/api/canonical/patients/${encodeURIComponent(patientId)}`),
  detectCandidates: patientId => postJson('/api/detection/candidates', { patient_id: patientId }),
  processCandidate: processCandidateWorkflow,
  ingestFhirBundle: (bundle, source = 'fhir') => postJson(`/api/ingestion/fhir?source=${encodeURIComponent(source)}`, bundle),
  ingestFhirBatch: (bundles, source = 'fhir') => postJson(`/api/ingestion/fhir/batch?source=${encodeURIComponent(source)}`, { bundles }),
  ingestHl7Message: message => postJson('/api/ingestion/hl7', { message }),
  uploadClinicalDocument: ({ file, patientId, sourceDocumentId, documentType, title }) => {
    const body = new FormData()
    body.set('file', file)
    body.set('patient_id', patientId)
    body.set('source_document_id', sourceDocumentId)
    if (documentType) body.set('document_type', documentType)
    if (title) body.set('title', title)
    return request('/api/ingestion/documents', { method: 'POST', body })
  },
  recordAuditEvent: event => postJson('/api/agents/audit/events', event),
  submitEcr: caseId => postJson('/api/agents/ecr-submission/submit', { case_id: caseId }),
  trackSubmission: submissionId => postJson('/api/agents/submission-tracking/track', { submission_id: submissionId }),
  recordPublicHealthFollowup: body => postJson('/api/agents/public-health-followup/process', body),
}
