import { useState, useCallback, useRef, useEffect } from "react";
import { chat, chatResume, executeCapability, createCapabilityRequest } from "../api.js";

export default function Chat({ toast }) {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text: "Hello! I'm your assistant. Ask me anything — I'll check if we've solved this before, or figure out a new approach.",
      time: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [humanInput, setHumanInput] = useState(null);
  const [capabilityCandidates, setCapabilityCandidates] = useState(null);
  const [showCapabilityForm, setShowCapabilityForm] = useState(false);
  const [capabilityForm, setCapabilityForm] = useState({
    name: "",
    purpose: "",
    inputs: "",
    outputs: "",
    acceptance_criteria: "",
  });
  const [executionResult, setExecutionResult] = useState(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, loading, capabilityCandidates, showCapabilityForm, executionResult]);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = { id: String(Date.now()), role: "user", text: text.trim(), time: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    setHumanInput(null);
    setCapabilityCandidates(null);
    setShowCapabilityForm(false);
    setExecutionResult(null);

    try {
      const body = { message: text.trim(), session_id: sessionId || undefined, context: {} };
      const data = await chat(body);

      const assistantMsg = {
        id: String(Date.now() + 1),
        role: "assistant",
        text: data.message || "OK",
        time: Date.now(),
        status: data.status,
        reasoning: data.reasoning,
        previous_solution: data.previous_solution,
        human_input_request: data.human_input_request,
        capability_candidates: data.capability_candidates,
        telemetry: data.telemetry,
      };
      setMessages((m) => [...m, assistantMsg]);
      if (data.session_id) setSessionId(data.session_id);
      if (data.status === "awaiting_human_input" && data.human_input_request) {
        setHumanInput({ sessionId: data.session_id, question: data.human_input_request.question });
      }
      if (data.status === "awaiting_confirmation" && data.previous_solution) {
        toast("Found a previous solution — confirm to reuse it?", false);
      }
      if (data.capability_candidates) {
        setCapabilityCandidates(data.capability_candidates);
      }
    } catch (err) {
      const errMsg = { id: String(Date.now() + 1), role: "assistant", text: "Error: " + err.message, time: Date.now(), isErr: true };
      setMessages((m) => [...m, errMsg]);
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [loading, sessionId, toast]);

  const handleHumanResponse = useCallback(async (response) => {
    if (!humanInput || !humanInput.sessionId) return;
    setLoading(true);
    try {
      const data = await chatResume(humanInput.sessionId, { response });
      const assistantMsg = {
        id: String(Date.now()),
        role: "assistant",
        text: data.message || "Done.",
        time: Date.now(),
        status: data.status,
        telemetry: data.telemetry,
      };
      setMessages((m) => [...m, assistantMsg]);
      setHumanInput(null);
      toast("Session resumed", false);
    } catch (err) {
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [humanInput, toast]);

  const handleExecuteCapability = useCallback(async (capabilityId) => {
    setLoading(true);
    try {
      const result = await executeCapability(capabilityId, {});
      setExecutionResult(result);
      const resultMsg = {
        id: String(Date.now()),
        role: "assistant",
        text: `Executed capability. Outputs: ${JSON.stringify(result.outputs)}`,
        time: Date.now(),
        executionResult: result,
      };
      setMessages((m) => [...m, resultMsg]);
      setCapabilityCandidates(null);
      toast("Capability executed", false);
    } catch (err) {
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const handleNoneMatch = useCallback(() => {
    setShowCapabilityForm(true);
  }, []);

  const handleCapabilityFormSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (!capabilityForm.name.trim() || !capabilityForm.purpose.trim()) return;
    setLoading(true);
    try {
      const requestId = `req-${Date.now()}`;
      await createCapabilityRequest(requestId, {
        capability_request: {
          name: capabilityForm.name.trim(),
          purpose: capabilityForm.purpose.trim(),
          inputs: capabilityForm.inputs
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
            .map((name) => ({ name, type: "string" })),
          outputs: capabilityForm.outputs
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
            .map((name) => ({ name, type: "string" })),
          acceptance_criteria: capabilityForm.acceptance_criteria
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        },
      });
      const msg = {
        id: String(Date.now()),
        role: "assistant",
        text: `Capability request "${capabilityForm.name.trim()}" submitted for approval.`,
        time: Date.now(),
      };
      setMessages((m) => [...m, msg]);
      setCapabilityCandidates(null);
      setShowCapabilityForm(false);
      setCapabilityForm({ name: "", purpose: "", inputs: "", outputs: "", acceptance_criteria: "" });
      toast("Capability request submitted", false);
    } catch (err) {
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [capabilityForm, toast]);

  const handleCapabilityFormChange = useCallback((field, value) => {
    setCapabilityForm((f) => ({ ...f, [field]: value }));
  }, []);

  const dismissCapabilityUI = useCallback(() => {
    setCapabilityCandidates(null);
    setShowCapabilityForm(false);
    setExecutionResult(null);
  }, []);

  return (
    <div className="cc-chat">
      <div className="cc-chat-header">
        <h2>Assistant</h2>
        {sessionId && <span className="cc-chat-session">Session: {sessionId}</span>}
      </div>
      <div className="cc-chat-messages" ref={listRef}>
        {messages.map((msg) => (
          <div key={msg.id} className={"cc-chat-msg " + msg.role + (msg.isErr ? " err" : "")}>
            <div className="cc-chat-bubble">
              <div className="cc-chat-text">{msg.text}</div>
              {msg.status && <div className="cc-chat-meta">status: {msg.status}</div>}
              {msg.reasoning && <div className="cc-chat-meta">reasoning: {msg.reasoning}</div>}
              {msg.previous_solution && (
                <div className="cc-chat-previous">
                  <strong>Previous solution:</strong> {msg.previous_solution.summary}
                  <br />
                  <small>Used {msg.previous_solution.invocation_count} times</small>
                </div>
              )}
              {msg.executionResult && (
                <div className="cc-chat-execution">
                  <strong>Execution result:</strong>
                  <pre>{JSON.stringify(msg.executionResult.outputs, null, 2)}</pre>
                </div>
              )}
              <div className="cc-chat-time">{new Date(msg.time).toLocaleTimeString()}</div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="cc-chat-msg assistant">
            <div className="cc-chat-bubble">
              <div className="cc-chat-text cc-chat-typing">Thinking...</div>
            </div>
          </div>
        )}
      </div>
      {capabilityCandidates && !showCapabilityForm && (
        <div className="cc-chat-capabilities">
          <div className="cc-chat-capabilities-header">
            <strong>Available capabilities</strong>
            <button onClick={dismissCapabilityUI} disabled={loading} className="secondary">Dismiss</button>
          </div>
          {capabilityCandidates.map((cap) => (
            <div key={cap.id} className="cc-chat-capability-card">
              <div className="cc-chat-capability-name">{cap.name}</div>
              <div className="cc-chat-capability-desc">{cap.description}</div>
              <div className="cc-chat-capability-meta">
                <span>kind: {cap.kind}</span>
                <span>mode: {cap.execution_mode}</span>
                {cap.tags && cap.tags.length > 0 && <span>tags: {cap.tags.join(", ")}</span>}
              </div>
              <button
                onClick={() => handleExecuteCapability(cap.id)}
                disabled={loading}
                className="cc-chat-capability-execute"
              >
                Use this capability
              </button>
            </div>
          ))}
          <button onClick={handleNoneMatch} disabled={loading} className="secondary">
            None of these matches
          </button>
        </div>
      )}
      {showCapabilityForm && (
        <div className="cc-chat-capability-form">
          <strong>Request a new capability</strong>
          <form onSubmit={handleCapabilityFormSubmit}>
            <input
              type="text"
              placeholder="Name"
              value={capabilityForm.name}
              onChange={(e) => handleCapabilityFormChange("name", e.target.value)}
              disabled={loading}
              required
            />
            <input
              type="text"
              placeholder="Purpose"
              value={capabilityForm.purpose}
              onChange={(e) => handleCapabilityFormChange("purpose", e.target.value)}
              disabled={loading}
              required
            />
            <input
              type="text"
              placeholder="Inputs (comma-separated)"
              value={capabilityForm.inputs}
              onChange={(e) => handleCapabilityFormChange("inputs", e.target.value)}
              disabled={loading}
            />
            <input
              type="text"
              placeholder="Outputs (comma-separated)"
              value={capabilityForm.outputs}
              onChange={(e) => handleCapabilityFormChange("outputs", e.target.value)}
              disabled={loading}
            />
            <input
              type="text"
              placeholder="Acceptance criteria (comma-separated)"
              value={capabilityForm.acceptance_criteria}
              onChange={(e) => handleCapabilityFormChange("acceptance_criteria", e.target.value)}
              disabled={loading}
            />
            <div className="cc-chat-capability-form-actions">
              <button type="submit" disabled={loading || !capabilityForm.name.trim() || !capabilityForm.purpose.trim()}>
                Submit request
              </button>
              <button type="button" onClick={() => setShowCapabilityForm(false)} disabled={loading} className="secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
      {executionResult && (
        <div className="cc-chat-execution-result">
          <strong>Last execution result</strong>
          <pre>{JSON.stringify(executionResult.outputs, null, 2)}</pre>
          <button onClick={() => setExecutionResult(null)} disabled={loading} className="secondary">Dismiss</button>
        </div>
      )}
      {humanInput && (
        <div className="cc-chat-human">
          <div className="cc-chat-human-question">{humanInput.question}</div>
          <div className="cc-chat-human-actions">
            <button onClick={() => handleHumanResponse("yes, proceed")} disabled={loading}>Approve</button>
            <button onClick={() => handleHumanResponse("no, stop")} disabled={loading} className="secondary">Reject</button>
            <button onClick={() => handleHumanResponse("modify: " + input)} disabled={loading || !input.trim()} className="secondary">Modify</button>
          </div>
        </div>
      )}
      <div className="cc-chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (humanInput) {
                handleHumanResponse(input.trim());
              } else {
                send(input);
              }
            }
          }}
          placeholder={humanInput ? "Type your response..." : "Type a message..."}
          disabled={loading}
        />
        <button onClick={() => humanInput ? handleHumanResponse(input.trim()) : send(input)} disabled={loading || !input.trim()}>
          {humanInput ? "Send" : "Send"}
        </button>
      </div>
    </div>
  );
}
