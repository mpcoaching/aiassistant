import { useState, useCallback, useRef, useEffect } from "react";
import { chat, chatResume } from "../api.js";

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
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, loading]);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = { id: String(Date.now()), role: "user", text: text.trim(), time: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    setHumanInput(null);

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
