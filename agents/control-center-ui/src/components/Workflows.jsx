import { useEffect, useState } from "react";
import { getWorkflows, runWorkflow } from "../api.js";
import { esc } from "../api.js";
import CreateWorkflow from "./CreateWorkflow.jsx";

function RunForm({ name, toast, onStarted }) {
  const [ctx, setCtx] = useState("{}");
  const [role, setRole] = useState("");
  const [result, setResult] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    let context = {};
    if (ctx.trim()) {
      try {
        context = JSON.parse(ctx);
      } catch (err) {
        setResult({ err: "Invalid context JSON: " + err.message });
        return;
      }
    }
    const body = { initial_context: context };
    if (role.trim()) body.role_override = role.trim();
    try {
      const summary = await runWorkflow(name, body);
      setResult({ ok: true, id: summary.workflow_id });
      toast("Started " + name);
      onStarted(summary);
    } catch (err) {
      setResult({ err: err.message });
    }
  };

  return (
    <form className="cc-runform" onSubmit={submit}>
      <div className="cc-field">
        <label>Initial context (JSON)</label>
        <textarea
          rows="3"
          value={ctx}
          onChange={(e) => setCtx(e.target.value)}
          placeholder='{"key":"value"}'
        />
      </div>
      <div className="cc-field">
        <label>Role override (optional)</label>
        <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="developer" />
      </div>
      <div className="cc-row-actions">
        <button className="cc-btn cc-btn-primary" type="submit">Start</button>
      </div>
      {result && (
        <div className="cc-runresult">
          {result.err ? (
            <span className="cc-err">{result.err}</span>
          ) : (
            <>
              <span className="cc-status completed">done</span> id: <code>{esc(result.id)}</code>
            </>
          )}
        </div>
      )}
    </form>
  );
}

function Card({ wf, toast, onStarted, onSchedule }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="cc-card">
      <div className="cc-card-head">
        <h3>{wf.name}</h3>
        <span className="cc-dot" />
      </div>
      <p className="cc-card-desc">{wf.description || "No description"}</p>
      <div className="cc-card-actions">
        <button className="cc-btn cc-btn-primary" onClick={() => setOpen((o) => !o)}>
          {open ? "Hide" : "Run"}
        </button>
        <button className="cc-btn cc-btn-ghost" onClick={() => onSchedule(wf.name)}>Schedule</button>
      </div>
      {open && <RunForm name={wf.name} toast={toast} onStarted={onStarted} />}
    </div>
  );
}

export default function Workflows({ toast, onRunStarted, onSchedule }) {
  const [list, setList] = useState([]);
  const [count, setCount] = useState("");
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const load = async () => {
    try {
      const data = await getWorkflows();
      setList(data);
      setCount(data.length + " workflow(s)");
      setError("");
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <section>
      <div className="cc-toolbar">
        <button className="cc-btn cc-btn-primary" onClick={() => setShowCreate((s) => !s)}>
          + New workflow
        </button>
        <button className="cc-btn cc-btn-ghost" onClick={load}>Refresh</button>
        <span className="cc-muted">{count}</span>
      </div>

      {showCreate && <CreateWorkflow toast={toast} onCreated={load} />}

      {error ? (
        <div className="cc-empty cc-err">Failed to load workflows: {error}</div>
      ) : list.length === 0 ? (
        <div className="cc-empty">No workflows found.</div>
      ) : (
        <div className="cc-grid">
          {list.map((wf) => (
            <Card key={wf.name} wf={wf} toast={toast} onStarted={onRunStarted} onSchedule={onSchedule} />
          ))}
        </div>
      )}
    </section>
  );
}
