const API = "/api";

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(API + path, opts);
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const detail = (data && (data.detail || data.error)) || ("HTTP " + res.status);
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export const getWorkflows = () => api("GET", "/workflows");
export const createWorkflow = (body) => api("POST", "/workflows", body);
export const runWorkflow = (name, body) =>
  api("POST", `/workflows/${encodeURIComponent(name)}/run`, body);
export const getStatus = (id) =>
  api("GET", `/workflows/${encodeURIComponent(id)}/status?workflow_path=`);
export const controlInstance = (id, action) =>
  api("POST", `/workflows/${encodeURIComponent(id)}/${action}?workflow_path=`);
export const getSchedules = () => api("GET", "/schedules");
export const createSchedule = (body) => api("POST", "/schedules", body);
export const deleteSchedule = (id) =>
  api("DELETE", `/schedules/${encodeURIComponent(id)}`);

export const chat = (body) => api("POST", "/assistant/chat", body);
export const chatResume = (sessionId, body) =>
  api("POST", `/assistant/chat/${encodeURIComponent(sessionId)}/resume`, body);

export function esc(s) {
  if (s == null) return "";
  return String(s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}
