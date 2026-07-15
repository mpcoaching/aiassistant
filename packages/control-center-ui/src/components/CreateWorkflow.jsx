import { useState } from "react";
import { createWorkflow } from "../api.js";

function StepRow({ index, step, onChange, onRemove }) {
  return (
    <div className="cc-steprow">
      <select value={step.type} onChange={(e) => onChange(index, { ...step, type: e.target.value })}>
        <option value="skill">skill</option>
        <option value="tool">tool</option>
        <option value="workflow">workflow</option>
      </select>
      <input
        className="cc-st-name"
        placeholder="step name"
        value={step.name}
        onChange={(e) => onChange(index, { ...step, name: e.target.value })}
      />
      <input
        className="cc-st-uses"
        placeholder="uses: skill/tool name"
        value={step.uses}
        onChange={(e) => onChange(index, { ...step, uses: e.target.value })}
      />
      <input
        className="cc-st-with"
        placeholder='with: {} (opt)'
        value={step.with}
        onChange={(e) => onChange(index, { ...step, with: e.target.value })}
      />
      <button type="button" className="cc-btn cc-btn-danger" onClick={() => onRemove(index)}>×</button>
    </div>
  );
}

export default function CreateWorkflow({ toast, onCreated }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [roles, setRoles] = useState("");
  const [steps, setSteps] = useState([{ type: "skill", name: "", uses: "", with: "" }]);

  const updateStep = (i, step) => setSteps((s) => s.map((x, j) => (j === i ? step : x)));
  const removeStep = (i) => setSteps((s) => s.filter((_, j) => j !== i));
  const addStep = () => setSteps((s) => [...s, { type: "skill", name: "", uses: "", with: "" }]);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      toast("Name is required", true);
      return;
    }
    const built = [];
    for (const s of steps) {
      if (!s.name.trim() || !s.uses.trim()) continue;
      const step = { type: s.type, name: s.name.trim(), uses: s.uses.trim() };
      if (s.with.trim()) {
        try {
          step.with = JSON.parse(s.with);
        } catch (err) {
          toast("Invalid 'with' JSON in a step", true);
          return;
        }
      }
      built.push(step);
    }
    if (!built.length) {
      toast("Add at least one step", true);
      return;
    }
    const body = {
      name: name.trim(),
      description: desc.trim() || null,
      role: roles.trim() ? roles.split(",").map((r) => r.trim()) : null,
      steps: built,
    };
    try {
      await createWorkflow(body);
      toast("Workflow '" + name.trim() + "' created");
      setName("");
      setDesc("");
      setRoles("");
      setSteps([{ type: "skill", name: "", uses: "", with: "" }]);
      onCreated();
    } catch (err) {
      toast(err.message, true);
    }
  };

  return (
    <div className="cc-panel">
      <h2>Create workflow</h2>
      <form onSubmit={submit}>
        <div className="cc-field">
          <label>Name (unique, e.g. <code>my.team.workflow</code>)</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my.team.workflow" />
        </div>
        <div className="cc-field">
          <label>Description</label>
          <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="What this workflow does" />
        </div>
        <div className="cc-field">
          <label>Roles (comma separated, optional)</label>
          <input value={roles} onChange={(e) => setRoles(e.target.value)} placeholder="developer, designer" />
        </div>
        <div className="cc-field">
          <label>Steps</label>
          <div className="cc-steps">
            {steps.map((s, i) => (
              <StepRow key={i} index={i} step={s} onChange={updateStep} onRemove={removeStep} />
            ))}
          </div>
          <button type="button" className="cc-btn cc-btn-ghost" onClick={addStep}>+ Add step</button>
        </div>
        <div className="cc-row-actions">
          <button className="cc-btn cc-btn-primary" type="submit">Save workflow</button>
        </div>
      </form>
    </div>
  );
}
