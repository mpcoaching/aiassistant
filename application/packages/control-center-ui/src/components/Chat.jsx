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
  const [validationState, setValidationState] = useState(null);
  const [validationAction, setValidationAction] = useState(null);
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
  const [documentName, setDocumentName] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [investigationState, setInvestigationState] = useState(null);
  const fileInputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, loading, capabilityCandidates, showCapabilityForm, executionResult]);

  const handleFileSelected = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setDocumentName(file.name);
      setDocumentContent(ev.target.result);
    };
    reader.readAsText(file);
  }, []);

  const clearDocument = useCallback(() => {
    setDocumentName("");
    setDocumentContent("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = { id: String(Date.now()), role: "user", text: text.trim(), time: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    setHumanInput(null);
    setValidationState(null);
    setValidationAction(null);
    setInvestigationState(null);
    setCapabilityCandidates(null);
    setShowCapabilityForm(false);
    setExecutionResult(null);

    try {
      const context = { ...(documentContent ? { input_text: documentContent, document_name: documentName } : {}) };
      const body = { message: text.trim(), session_id: sessionId || undefined, context };
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
        execution_outputs: data.execution_outputs,
        execution_artifacts: data.execution_artifacts,
      };
      setMessages((m) => [...m, assistantMsg]);
      clearDocument();
      if (data.session_id) setSessionId(data.session_id);
      if (data.status === "awaiting_human_input" && data.human_input_request) {
        setHumanInput({ sessionId: data.session_id, question: data.human_input_request.question });
      }
      if (data.status === "awaiting_validation" && data.human_input_request) {
        setValidationState({
          sessionId: data.session_id,
          question: data.human_input_request.question,
          options: data.human_input_request.options || [],
          proposed: data.message,
          validationType: data.human_input_request.validation_type,
        });
      }
      if (data.status === "completed" && data.execution_outputs && data.execution_outputs.analysis_context) {
        setInvestigationState({ sessionId: data.session_id, pending: null });
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
  }, [loading, sessionId, toast, documentContent, documentName, clearDocument]);

  const sendValidationResponse = useCallback(async (responseText) => {
    if (!validationState || !validationState.sessionId) return;
    setLoading(true);
    setValidationAction(responseText);
    try {
      const data = await chatResume(validationState.sessionId, { response: responseText });
      const assistantMsg = {
        id: String(Date.now()),
        role: "assistant",
        text: data.message || "Done.",
        time: Date.now(),
        status: data.status,
        reasoning: data.reasoning,
        previous_solution: data.previous_solution,
        human_input_request: data.human_input_request,
        telemetry: data.telemetry,
      };
      setMessages((m) => [...m, assistantMsg]);
      if (data.status === "awaiting_validation" && data.human_input_request) {
        setValidationState({
          sessionId: data.session_id,
          question: data.human_input_request.question,
          options: data.human_input_request.options || [],
          proposed: data.message,
          validationType: data.human_input_request.validation_type,
        });
        toast("Understanding updated", false);
      } else {
        setValidationState(null);
        setValidationAction(null);
        toast("Session resumed", false);
      }
      if (data.session_id) setSessionId(data.session_id);
    } catch (err) {
      toast(err.message, true);
      setValidationAction(null);
    } finally {
      setLoading(false);
    }
  }, [validationState, toast]);

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
        reasoning: data.reasoning,
        previous_solution: data.previous_solution,
        human_input_request: data.human_input_request,
        telemetry: data.telemetry,
      };
      setMessages((m) => [...m, assistantMsg]);
      setHumanInput(null);
      if (data.status === "awaiting_validation" && data.human_input_request) {
        setValidationState({
          sessionId: data.session_id,
          question: data.human_input_request.question,
          options: data.human_input_request.options || [],
          proposed: data.message,
          validationType: data.human_input_request.validation_type,
        });
        toast("Review the understanding below", false);
      } else {
        toast("Session resumed", false);
      }
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

  const sendInvestigation = useCallback(async (investigationText) => {
    if (!investigationState || !investigationState.sessionId) return;
    setLoading(true);
    setInvestigationState((prev) => ({ ...prev, pending: investigationText }));
    try {
      const data = await chatResume(investigationState.sessionId, { response: investigationText, investigation: true });
      const assistantMsg = {
        id: String(Date.now()),
        role: "assistant",
        text: data.message || "Done.",
        time: Date.now(),
        status: data.status,
        reasoning: data.reasoning,
        telemetry: data.telemetry,
      };
      setMessages((m) => [...m, assistantMsg]);
      setInvestigationState(null);
      if (data.session_id) setSessionId(data.session_id);
      toast("Investigation updated", false);
    } catch (err) {
      toast(err.message, true);
      setInvestigationState((prev) => ({ ...prev, pending: null }));
    } finally {
      setLoading(false);
    }
  }, [investigationState, toast]);

  return (
    <div className="cc-chat">
      <div className="cc-chat-header">
        <h2>Assistant</h2>
        {sessionId && <span className="cc-chat-session">Session: {sessionId}</span>}
      </div>
      <div className="cc-chat-messages" ref={listRef}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            data-runtime={msg.telemetry?.runtime || "other"}
            className={"cc-chat-msg " + msg.role + (msg.isErr ? " err" : "")}
          >
            <div className="cc-chat-bubble">
              <div className="cc-chat-text">{msg.text}</div>
              {msg.status && <div className="cc-chat-meta">status: {msg.status}</div>}
              {msg.reasoning && <div className="cc-chat-meta">reasoning: {msg.reasoning}</div>}
              {msg.telemetry && (
                <div className="cc-chat-execution">
                  {msg.telemetry.work_id && (
                    <div><strong>Work:</strong> {msg.telemetry.work_id}</div>
                  )}
                  {msg.telemetry.work_status && (
                    <div><strong>Status:</strong> {msg.telemetry.work_status}</div>
                  )}
                  {msg.telemetry.delegated && (
                    <div><strong>Backend:</strong> Organisation Worker</div>
                  )}
                </div>
              )}
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
      {validationState && (
        <div className="cc-chat-validation">
          <div className="cc-chat-validation-header">Here's what I understand</div>
          <div className="cc-chat-validation-proposed">{validationState.proposed}</div>
          <div className="cc-chat-validation-actions">
            <button onClick={() => sendValidationResponse("Yes, proceed.")} disabled={loading || validationAction === "Yes, proceed."} className="cc-chat-validation-confirm">
              Yes, proceed
            </button>
            <button onClick={() => { setInput("Also, "); }} disabled={loading} className="cc-chat-validation-update">
              Add information
            </button>
            <button onClick={() => { setInput("Actually, "); }} disabled={loading} className="cc-chat-validation-contradict">
              Change goal
            </button>
            <button onClick={() => sendValidationResponse("Can you clarify what you mean?")} disabled={loading} className="secondary">
              Clarify
            </button>
          </div>
          {validationAction && (
            <div className="cc-chat-validation-pending">Sending: "{validationAction}"...</div>
          )}
        </div>
      )}
      {investigationState && (
        <div className="cc-chat-investigation">
          <div className="cc-chat-investigation-header">Follow-up investigation</div>
          <div className="cc-chat-investigation-actions">
            <button onClick={() => sendInvestigation("Why?")} disabled={loading || investigationState.pending} className="cc-chat-investigation-why">Why?</button>
            <button onClick={() => sendInvestigation("What would prove it?")} disabled={loading || investigationState.pending} className="cc-chat-investigation-prove">What would prove it?</button>
            <button onClick={() => sendInvestigation("What should I investigate next?")} disabled={loading || investigationState.pending} className="cc-chat-investigation-next">What should I investigate next?</button>
          </div>
          {investigationState.pending && (
            <div className="cc-chat-investigation-pending">Sending: "{investigationState.pending}"...</div>
          )}
        </div>
      )}
      {documentName && (
        <div className="cc-chat-document">
          <span className="cc-chat-document-name">📎 {documentName}</span>
          <button onClick={clearDocument} disabled={loading} className="cc-chat-document-clear">×</button>
        </div>
      )}
      <div className="cc-chat-input-row">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelected}
          accept=".txt,.md,.text"
          style={{ display: "none" }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
          className="cc-chat-attach"
          title="Attach document"
        >
          📎
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (validationState) {
                sendValidationResponse(input.trim());
              } else if (humanInput) {
                handleHumanResponse(input.trim());
              } else if (investigationState) {
                sendInvestigation(input.trim());
              } else {
                send(input);
              }
            }
          }}
          placeholder={validationState ? "Type your response or use the actions above..." : investigationState ? "Type your follow-up..." : humanInput ? "Type your response..." : "Type a message..."}
          disabled={loading}
        />
        <button onClick={() => validationState ? sendValidationResponse(input.trim()) : investigationState ? sendInvestigation(input.trim()) : humanInput ? handleHumanResponse(input.trim()) : send(input)} disabled={loading || (!input.trim() && !documentContent && !validationState && !investigationState)}>
          {validationState ? "Respond" : investigationState ? "Investigate" : humanInput ? "Send" : "Send"}
        </button>
      </div>
    </div>
  );
}
