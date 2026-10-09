import { useRef, useState } from "react";
import { Bot, MessageCircle, Send, Sparkles, Trash2, X } from "lucide-react";
import { request } from "../../api/client.js";
import "../../styles/chatWidget.css";

const PROMPTS = [
  "Summarize patient DEMO-P001",
  "Give me the summary for Alex Morgan",
  "Explain the reporting deadline for DEMO-P001",
  "Show submission status for DEMO-P001",
];

const WELCOME = "Explore patient summaries using predefined synthetic records. Try ‘Summarize patient DEMO-P001’.";

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const conversationRef = useRef(null);

  async function sendMessage(value = draft) {
    const question = value.trim();
    if (!question || loading) return;

    setDraft("");
    setMessages((current) => [...current, { role: "user", text: question }]);
    setLoading(true);
    try {
      const response = await request("/api/assistant/demo/chat", {
        method: "POST",
        body: JSON.stringify({ question, selected_patient_id: selectedPatientId }),
      });
      if (response.selected_patient_id) setSelectedPatientId(response.selected_patient_id);
      else if (["selection_required", "no_match", "needs_patient"].includes(response.status)) setSelectedPatientId(null);
      setMessages((current) => [...current, { role: "assistant", response }]);
    } catch (error) {
      const unavailable = error.status === 503
        ? error.message
        : "SIGNAL Assistant is unavailable right now. Your message was not processed. Please try again.";
      setMessages((current) => [...current, { role: "assistant", text: unavailable, retry: question }]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => conversationRef.current?.scrollTo({ top: conversationRef.current.scrollHeight, behavior: "smooth" }));
    }
  }

  function clearChat() {
    setMessages([]);
    setSelectedPatientId(null);
  }

  return (
    <div className="signal-assistant">
      {open && (
        <section className="signal-chat-card" aria-label="SIGNAL Assistant chat" aria-live="polite">
          <header className="signal-chat-header">
            <span className="signal-chat-avatar"><Bot size={20} aria-hidden="true" /></span>
            <span className="signal-chat-title"><strong>SIGNAL Assistant</strong><small>Synthetic demo assistant</small></span>
            <span className="signal-chat-demo-badge">DEMO MODE</span>
            <button className="signal-chat-icon-button" type="button" onClick={clearChat} aria-label="Clear chat" title="Clear chat"><Trash2 size={17} /></button>
            <button className="signal-chat-icon-button" type="button" onClick={() => setOpen(false)} aria-label="Close chat" title="Close"><X size={19} /></button>
          </header>

          <div className="signal-chat-demo-notice">Synthetic data only. No real patient records are accessed.</div>
          <div className="signal-chat-conversation" ref={conversationRef}>
            {messages.length === 0 ? (
              <div className="signal-chat-welcome">
                <span className="signal-chat-welcome-icon"><Sparkles size={20} /></span>
                <strong>How can I help?</strong>
                <p>{WELCOME}</p>
                <div className="signal-chat-prompts">
                  {PROMPTS.map((prompt) => <button type="button" key={prompt} onClick={() => { setDraft(prompt); }}>{prompt}</button>)}
                </div>
              </div>
            ) : messages.map((message, index) => (
              <div className={`signal-chat-message ${message.role}`} key={`${index}-${message.role}`}>
                <div className={`signal-chat-bubble${message.response ? " has-structured" : ""}`}>
                  {message.response ? (
                    <div className="signal-chat-structured">
                      <strong className="signal-chat-disclaimer">{message.response.label}</strong>
                      <p>{message.response.message}</p>
                      {message.response.candidates?.map((candidate) => (
                        <button
                          className="signal-chat-candidate"
                          type="button"
                          key={candidate.patient_id}
                          onClick={() => sendMessage(`Summarize patient ${candidate.patient_id}`)}
                        >
                          {candidate.name} · {candidate.patient_id}
                        </button>
                      ))}
                      {message.response.sections?.map((section) => (
                        <section className="signal-chat-summary-section" key={section.title}>
                          <strong>{section.title}</strong>
                          <dl>{section.items.map(([label, value]) => (
                            <div key={label}><dt>{label}</dt><dd>{Array.isArray(value) ? value.map((item) => typeof item === "object" ? Object.values(item).filter(Boolean).join(" · ") : item).join("; ") : value}</dd></div>
                          ))}</dl>
                        </section>
                      ))}
                    </div>
                  ) : message.text}
                </div>
                {message.retry && <button type="button" className="signal-chat-retry" disabled={loading} onClick={() => sendMessage(message.retry)}>Retry</button>}
              </div>
            ))}
            {loading && <div className="signal-chat-message assistant"><div className="signal-chat-bubble signal-chat-loading"><span /><span /><span /><span className="sr-only">Generating response</span></div></div>}
          </div>

          <form className="signal-chat-composer" onSubmit={(event) => { event.preventDefault(); sendMessage(); }}>
            <textarea
              aria-label="Message SIGNAL Assistant"
              placeholder="Ask about a patient or case…"
              rows={1}
              value={draft}
              disabled={loading}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />
            <button type="submit" aria-label="Send message" disabled={loading || !draft.trim()}><Send size={18} /></button>
          </form>
        </section>
      )}
      <button
        type="button"
        className={`signal-chat-launcher${open ? " is-open" : ""}`}
        aria-label={open ? "Close SIGNAL Assistant" : "Open SIGNAL Assistant"}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <X size={23} /> : <MessageCircle size={24} />}
      </button>
    </div>
  );
}
