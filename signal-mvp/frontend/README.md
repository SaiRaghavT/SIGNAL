# SIGNAL Frontend

React + TypeScript + Vite frontend built against the uploaded SIGNAL backend.

## Run

1. Start the SIGNAL backend on `http://localhost:8000`.
2. Install dependencies:
   `npm install`
3. Start:
   `npm run dev`

Vite proxies `/api/*` and `/health` to `http://localhost:8000`, so local development does not require CORS middleware.

## Important backend truth

This UI intentionally does not invent list endpoints for patients, candidates, submissions, or follow-ups because the current backend exposes actions/lookups for those areas rather than durable list APIs.

Implemented read/list paths represented here:
- `GET /health`
- `GET /api/dashboard/summary`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `GET /api/workflow/cases/{case_id}/journey`
- `GET /api/canonical/patients/{patient_id}`

Implemented actions represented here include FHIR/HL7/document ingestion, candidate detection, reportability processing, report-field updates, manual reporting, form rendering, attestation, eCR submission, tracking, acknowledgement, retry, follow-up, and audit events.

## Validation

The source was generated successfully, but dependency installation in this execution environment timed out, so a complete `npm run build` could not be completed here.
