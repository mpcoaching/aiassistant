import { useEffect, useState } from "react";
import { getSchedules, createSchedule, deleteSchedule } from "../api.js";
import { esc } from "../api.js";

export default function Schedules({ toast, prefill }) {
  const [list, setList] = useState([]);
  const [wf, setWf] = useState("");
  const [sid, setSid] = useState("");
  const [cron, setCron] = useState("");
  const [ctx, setCtx] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getSchedules();
      setList(data);
    } catch (e) {
      toast("Failed to load schedules: " + e.message, true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (prefill) setWf(prefill);
  }, [prefill]);

  const submit = async (e) => {
    e.preventDefault();
    if (!wf.trim() || !sid.trim() || !cron.trim()) {
      toast("workflow name, id and cron are required", true);
      return;
    }
    let context = {};
    if (ctx.trim()) {
      try {
        context = JSON.parse(ctx);
      } catch (err) {
        toast("Invalid context JSON", true);
        return;
      }
    }
    try {
      await createSchedule({
        workflow_name: wf.trim(),
        schedule_id: sid.trim(),
        cron: cron.trim(),
        initial_context: context,
      });
      toast("Schedule created");
      setWf("");
      setSid("");
      setCron("");
      setCtx("");
      load();
    } catch (err) {
      toast(err.message, true);
    }
  };

  const remove = async (id) => {
    try {
      await deleteSchedule(id);
      toast("Schedule removed");
      load();
    } catch (err) {
      toast(err.message, true);
    }
  };

  return (
    <section>
      <div className="cc-panel">
        <h2>New schedule</h2>
        <form className="cc-row" onSubmit={submit}>
          <div className="cc-field">
            <label>Workflow name</label>
            <input value={wf} onChange={(e) => setWf(e.target.value)} placeholder="requirements.analysis.define-requirements" />
          </div>
          <div className="cc-field">
            <label>Schedule ID</label>
            <input value={sid} onChange={(e) => setSid(e.target.value)} placeholder="daily-requirements" />
          </div>
          <div className="cc-field">
            <label>Cron</label>
            <input value={cron} onChange={(e) => setCron(e.target.value)} placeholder="0 8 * * *" />
          </div>
          <div className="cc-field">
            <label>Initial context (JSON, optional)</label>
            <input value={ctx} onChange={(e) => setCtx(e.target.value)} placeholder='{"topic":"x"}' />
          </div>
          <button className="cc-btn cc-btn-primary" type="submit">Create</button>
        </form>
      </div>

      <div className="cc-panel">
        <h2>Active schedules</h2>
        {loading ? (
          <p className="cc-muted">Loading…</p>
        ) : list.length === 0 ? (
          <div className="cc-empty">No schedules.</div>
        ) : (
          <table className="cc-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Workflow</th>
                <th>Cron</th>
                <th>Next run</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.schedule_id}>
                  <td>{s.schedule_id}</td>
                  <td>{s.workflow_name}</td>
                  <td><code>{s.cron}</code></td>
                  <td className="cc-muted">{s.next_run_time || "—"}</td>
                  <td>
                    <button className="cc-btn cc-btn-danger" onClick={() => remove(s.schedule_id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
