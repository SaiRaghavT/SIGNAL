import React, { useState } from "react";
import "../styles/informationReceived.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export default function InformationReceived() {
  const [activeModal, setActiveModal] = useState(null);

  const ingestionOptions = [
    {
      id: "fhir",
      icon: "⚕",
      title: "FHIR",
      subtitle: "Import a FHIR Bundle",
      description:
        "Receive structured clinical information from an EHR or FHIR-compatible source.",
      endpoint: "/api/ingestion/fhir",
    },
    {
      id: "hl7",
      icon: "⇄",
      title: "HL7",
      subtitle: "Import an HL7 message",
      description:
        "Receive clinical messages from hospital and healthcare information systems.",
      endpoint: "/api/ingestion/hl7",
    },
    {
      id: "documents",
      icon: "▤",
      title: "Documents",
      subtitle: "Upload clinical documents",
      description:
        "Upload patient documents for clinical evidence extraction.",
      endpoint: "/api/ingestion/documents",
    },
  ];

  return (
    <div className="information-page">
      {/* SIDEBAR */}

      {/* MAIN */}
      <main className="information-main">
        <header className="information-topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> Information Received
          </div>

          <div className="topbar-right">
            <span className="system-status">
              <span className="status-dot"></span>
              System Operational
            </span>

            <div className="topbar-avatar">SR</div>
          </div>
        </header>

        <div className="information-content">
          {/* HEADER */}
          <section className="page-header">
            <div>
              <div className="eyebrow">DATA INGESTION</div>

              <h1>Information Received</h1>

              <p>
                Receive clinical information from healthcare systems and
                prepare it for SIGNAL's detection and reporting workflow.
              </p>
            </div>

            <div className="api-status">
              <span className="status-dot"></span>
              Backend Connected
            </div>
          </section>

          {/* INGESTION OPTIONS */}
          <section className="section-block">
            <div className="section-heading">
              <div>
                <h2>Receive Information</h2>

                <p>
                  Select the source through which clinical information enters
                  SIGNAL.
                </p>
              </div>
            </div>

            <div className="ingestion-grid">
              {ingestionOptions.map((option) => (
                <div className="ingestion-card" key={option.id}>
                  <div className="ingestion-card-top">
                    <div className="ingestion-icon">{option.icon}</div>

                    <span className="source-badge">API</span>
                  </div>

                  <h3>{option.title}</h3>

                  <h4>{option.subtitle}</h4>

                  <p>{option.description}</p>

                  <div className="endpoint">
                    <span>POST</span>
                    {option.endpoint}
                  </div>

                  <button
                    className="primary-button"
                    onClick={() => setActiveModal(option.id)}
                  >
                    Open {option.title} Ingestion
                    <span>→</span>
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* PIPELINE */}
          <section className="section-block">
            <div className="section-heading">
              <div>
                <h2>Information Pipeline</h2>

                <p>
                  Information received by SIGNAL moves into normalization,
                  detection and candidate processing.
                </p>
              </div>
            </div>

            <div className="pipeline-card">
              <PipelineStep
                number="01"
                title="Information Received"
                subtitle="FHIR / HL7 / Documents"
              />

              <div className="pipeline-arrow">→</div>

              <PipelineStep
                number="02"
                title="Normalization"
                subtitle="Canonical clinical data"
              />

              <div className="pipeline-arrow">→</div>

              <PipelineStep
                number="03"
                title="Detection"
                subtitle="Clinical signals"
              />

              <div className="pipeline-arrow">→</div>

              <PipelineStep
                number="04"
                title="Candidate"
                subtitle="Potential reportable case"
              />
            </div>
          </section>

          {/* HISTORY */}
          <section className="section-block">
            <div className="section-heading">
              <div>
                <h2>Recent Information</h2>

                <p>
                  Ingestion activity received by the SIGNAL backend.
                </p>
              </div>
            </div>

            <div className="empty-state">
              <div className="empty-icon">▤</div>

              <h3>No ingestion history available</h3>

              <p>
                The current backend processes and persists ingested clinical
                resources, but does not expose a dedicated ingestion-history
                listing endpoint for this screen.
              </p>

              <button
                className="secondary-button"
                onClick={() => setActiveModal("fhir")}
              >
                Receive Information
              </button>
            </div>
          </section>
        </div>
      </main>

      {/* MODAL */}
      {activeModal && (
        <IngestionModal
          type={activeModal}
          onClose={() => setActiveModal(null)}
        />
      )}
    </div>
  );
}


/* =====================================================
   PIPELINE STEP
===================================================== */

function PipelineStep({ number, title, subtitle }) {
  return (
    <div className="pipeline-step">
      <div className="pipeline-number">{number}</div>

      <div>
        <strong>{title}</strong>
        <span>{subtitle}</span>
      </div>
    </div>
  );
}


/* =====================================================
   INGESTION MODAL
===================================================== */

function IngestionModal({ type, onClose }) {
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);

  const [patientId, setPatientId] = useState("");
  const [sourceDocumentId, setSourceDocumentId] = useState("");

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  const configs = {
    fhir: {
      title: "FHIR Ingestion",
      description:
        "Submit a FHIR Bundle directly to the SIGNAL ingestion API.",
      endpoint: "/api/ingestion/fhir",
    },

    hl7: {
      title: "HL7 Ingestion",
      description:
        "Submit an HL7 message to the SIGNAL ingestion API.",
      endpoint: "/api/ingestion/hl7",
    },

    documents: {
      title: "Document Ingestion",
      description:
        "Upload a clinical document and associate it with a patient.",
      endpoint: "/api/ingestion/documents",
    },
  };

  const config = configs[type];

  const submitFHIR = async () => {
    let parsed;

    try {
      parsed = JSON.parse(input);
    } catch {
      throw new Error("FHIR input is not valid JSON.");
    }

    if (parsed.resourceType !== "Bundle") {
      throw new Error(
        "FHIR payload must have resourceType set to 'Bundle'."
      );
    }

    const response = await fetch(
      `${API_BASE_URL}${config.endpoint}`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify(parsed),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
          data.message ||
          `FHIR ingestion failed with status ${response.status}.`
      );
    }

    return data;
  };


  const submitHL7 = async () => {
    if (!input.trim()) {
      throw new Error("Please enter an HL7 message.");
    }

    const response = await fetch(
      `${API_BASE_URL}${config.endpoint}`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          message: input,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
          data.message ||
          `HL7 ingestion failed with status ${response.status}.`
      );
    }

    return data;
  };


  const submitDocument = async () => {
    if (!file) {
      throw new Error("Please select a document.");
    }

    if (!patientId.trim()) {
      throw new Error("Patient ID is required.");
    }

    const formData = new FormData();

    formData.append("file", file);
    formData.append("patient_id", patientId.trim());

    if (sourceDocumentId.trim()) {
      formData.append(
        "source_document_id",
        sourceDocumentId.trim()
      );
    }

    const response = await fetch(
      `${API_BASE_URL}${config.endpoint}`,
      {
        method: "POST",
        body: formData,
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
          data.message ||
          `Document ingestion failed with status ${response.status}.`
      );
    }

    return data;
  };


  const handleSubmit = async (event) => {
    event.preventDefault();

    setLoading(true);
    setSuccess(null);
    setError(null);

    try {
      let result;

      if (type === "fhir") {
        result = await submitFHIR();
      }

      if (type === "hl7") {
        result = await submitHL7();
      }

      if (type === "documents") {
        result = await submitDocument();
      }

      console.log("SIGNAL ingestion response:", result);

      setSuccess(result);
    } catch (err) {
      console.error("SIGNAL ingestion error:", err);

      setError(err.message);
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="ingestion-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <div className="eyebrow">INFORMATION RECEIVED</div>

            <h2>{config.title}</h2>

            <p>{config.description}</p>
          </div>

          <button
            className="close-button"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* FHIR */}
          {type === "fhir" && (
            <div className="input-group">
              <label>FHIR Bundle JSON</label>

              <textarea
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                placeholder={`{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": []
}`}
                rows={15}
              />

              <small className="field-help">
                The payload must be a FHIR Bundle.
              </small>
            </div>
          )}

          {/* HL7 */}
          {type === "hl7" && (
            <div className="input-group">
              <label>HL7 Message</label>

              <textarea
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                placeholder={`MSH|^~\\&|SYSTEM|HOSPITAL|SIGNAL|PUBLICHEALTH
PID|1||12345||DOE^JOHN`}
                rows={15}
              />

              <small className="field-help">
                The message will be submitted as the backend's
                <strong> message </strong> field.
              </small>
            </div>
          )}

          {/* DOCUMENT */}
          {type === "documents" && (
            <>
              <div className="input-group">
                <label>Patient ID *</label>

                <input
                  type="text"
                  value={patientId}
                  onChange={(event) =>
                    setPatientId(event.target.value)
                  }
                  placeholder="Enter patient UUID"
                />
              </div>

              <div className="input-group">
                <label>Source Document ID</label>

                <input
                  type="text"
                  value={sourceDocumentId}
                  onChange={(event) =>
                    setSourceDocumentId(event.target.value)
                  }
                  placeholder="Optional source document identifier"
                />
              </div>

              <div className="file-upload">
                <label>Clinical Document *</label>

                <input
                  type="file"
                  onChange={(event) =>
                    setFile(
                      event.target.files?.[0] || null
                    )
                  }
                />

                {file && (
                  <div className="selected-file">
                    Selected: <strong>{file.name}</strong>
                  </div>
                )}
              </div>
            </>
          )}

          {/* ERROR */}
          {error && (
            <div className="form-error">
              <strong>Ingestion failed</strong>
              <br />
              {error}
            </div>
          )}

          {/* SUCCESS */}
          {success && (
            <div className="form-success">
              <strong>Information successfully received.</strong>

              <pre>
                {JSON.stringify(success, null, 2)}
              </pre>
            </div>
          )}

          {/* ACTIONS */}
          <div className="modal-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={onClose}
            >
              Close
            </button>

            <button
              type="submit"
              className="primary-button"
              disabled={loading}
            >
              {loading ? "Sending..." : "Submit to SIGNAL"}

              {!loading && <span>→</span>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}