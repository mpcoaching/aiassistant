import { useState, useCallback } from "react";
import Workflows from "./components/Workflows.jsx";
import Instances from "./components/Instances.jsx";
import Schedules from "./components/Schedules.jsx";
import Chat from "./components/Chat.jsx";

const TABS = [
  { id: "workflows", label: "Workflows" },
  { id: "instances", label: "Instances" },
  { id: "schedules", label: "Schedules" },
  { id: "chat", label: "Assistant" },
];

export default function App() {
  const [tab, setTab] = useState("workflows");
  const [toasts, setToasts] = useState([]);
  const [pending, setPending] = useState(null);
  const [schedulePrefill, setSchedulePrefill] = useState("");

  const toast = useCallback((msg, isErr) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, msg, isErr }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const handleRunStarted = (summary) => {
    setPending({ summary, key: Date.now() });
    setTab("instances");
  };

  const goSchedule = (name) => {
    setSchedulePrefill(name);
    setTab("schedules");
  };

  return (
    <>
      <header className="cc-header">
        <div className="cc-brand">
          <span className="cc-logo" />
          <h1>Control Center</h1>
          <span className="cc-phase">PHASE 1</span>
        </div>
        <nav className="cc-nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              className={"cc-tab" + (t.id === tab ? " active" : "")}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="cc-main">
        {tab === "workflows" && (
          <Workflows toast={toast} onRunStarted={handleRunStarted} onSchedule={goSchedule} />
        )}
        {tab === "instances" && <Instances toast={toast} pending={pending} />}
        {tab === "schedules" && <Schedules toast={toast} prefill={schedulePrefill} />}
        {tab === "chat" && <Chat toast={toast} />}
      </main>

      <div className="cc-toasts">
        {toasts.map((t) => (
          <div key={t.id} className={"cc-toast" + (t.isErr ? " err" : "")}>
            {t.msg}
          </div>
        ))}
      </div>
    </>
  );
}
