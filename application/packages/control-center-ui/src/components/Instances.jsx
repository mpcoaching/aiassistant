import { useEffect, useRef, useState } from "react";
import { getStatus, controlInstance } from "../api.js";
import { esc } from "../api.js";

const ACTIVE = ["running", "pending", "scheduled"];

function InstanceCard({ id, entry, toast, control }) {
  const st = entry.status;
  if (!st) {
    return (
      <div className="cc-card">
        <h3>{entry.workflow_name || id}</h3>
        <p className="cc-muted">Loading…</p>
      </div>
    );
  }
  const pct = st.total_steps ? Math.round((st.current_step_index / st.total_steps) * 100) : 0;
  return (
    <div className="cc-card">
      <h3>{entry.workflow_name || id}</h3>
      <div className="cc-instance-meta">
        <span className={"cc-status " + st.status}>{st.status}</span>
        <span className="cc-muted">step {st.current_step_index}/{st.total_steps}</span>
        <span className="cc-muted">{id}</span>
      </div>
      <div className="cc-progress"><div style={{ width: pct + "%" }} /></div>
      <div className="cc-row-actions">
        <button className="cc-btn cc-btn-ghost" onClick={() => control(id, "pause")}>Pause</button>
        <button className="cc-btn cc-btn-ghost" onClick={() => control(id, "resume")}>Resume</button>
        <button className="cc-btn cc-btn-danger" onClick={() => control(id, "stop")}>Stop</button>
        <button className="cc-btn cc-btn-ghost" onClick={() => control(id, "refresh")}>Refresh</button>
      </div>
      {st.error && <div className="cc-err">{st.error}</div>}
      {st.step_results && st.step_results.length > 0 && (
        <div className="cc-steps-result">
          {st.step_results.map((r, i) => {
            if (!r) return null;
            return (
              <div className="cc-stepres" key={i}>
                <span className="cc-stepname">{r.step_name || "?"}</span>{" "}
                <span className={"cc-status " + r.status}>{r.status}</span>
                {r.duration_seconds != null && (
                  <span className="cc-muted"> {r.duration_seconds.toFixed(1)}s</span>
                )}
                {r.error && <div className="cc-err">{r.error}</div>}
                {r.output != null && (
                  <pre>{typeof r.output === "string" ? r.output : JSON.stringify(r.output, null, 2)}</pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Instances({ toast, pending }) {
  const [tracked, setTracked] = useState({});
  const [idInput, setIdInput] = useState("");
  const timers = useRef({});

  const poll = async (id) => {
    try {
      const st = await getStatus(id);
      setTracked((t) => ({ ...t, [id]: { ...(t[id] || {}), status: st } }));
      if (ACTIVE.includes(st.status)) {
        timers.current[id] = setTimeout(() => poll(id), 3000);
      }
    } catch (e) {
      toast("Failed to load " + id + ": " + e.message, true);
    }
  };

  const track = (summary) => {
    setTracked((t) => ({
      ...t,
      [summary.workflow_id]: { workflow_name: summary.workflow_name || "", status: null },
    }));
    clearTimeout(timers.current[summary.workflow_id]);
    poll(summary.workflow_id);
  };

  useEffect(() => {
    if (pending && pending.summary) track(pending.summary);
    return () => Object.values(timers.current).forEach(clearTimeout);
  }, [pending]);

  const loadById = async () => {
    const id = idInput.trim();
    if (!id) return;
    try {
      const st = await getStatus(id);
      setTracked((t) => ({ ...t, [id]: { workflow_name: st.workflow_name || id, status: st } }));
      clearTimeout(timers.current[id]);
      poll(id);
    } catch (e) {
      toast("Instance not found: " + e.message, true);
    }
  };

  const control = async (id, action) => {
    if (action === "refresh") {
      clearTimeout(timers.current[id]);
      poll(id);
      return;
    }
    try {
      await controlInstance(id, action);
      toast(action + " sent");
      clearTimeout(timers.current[id]);
      poll(id);
    } catch (e) {
      toast(e.message, true);
    }
  };

  const ids = Object.keys(tracked);
  return (
    <section>
      <div className="cc-toolbar">
        <input
          className="cc-inline-input"
          placeholder="workflow_id to inspect"
          value={idInput}
          onChange={(e) => setIdInput(e.target.value)}
        />
        <button className="cc-btn cc-btn-primary" onClick={loadById}>Load by ID</button>
        <span className="cc-muted">Runs launched from the Workflows tab appear here automatically.</span>
      </div>
      {ids.length === 0 ? (
        <div className="cc-empty">No instances yet. Run a workflow or load by ID.</div>
      ) : (
        <div className="cc-grid">
          {ids.map((id) => (
            <InstanceCard key={id} id={id} entry={tracked[id]} toast={toast} control={control} />
          ))}
        </div>
      )}
    </section>
  );
}
