/**
 * Secret redaction for anything written to the OutputChannel or logs.
 * Inputs/context values whose names look like secrets are masked before output.
 */

const SECRET_KEY_PATTERN = /(token|secret|password|passwd|pwd|api[_-]?key|pat|private[_-]?key|client[_-]?secret)/i;
const MASK = "***REDACTED***";

export function isSecretKey(key: string): boolean {
  return SECRET_KEY_PATTERN.test(key);
}

export function redactValue(value: unknown): string {
  if (typeof value === "string") {
    return value.length > 0 ? MASK : value;
  }
  return MASK;
}

/** Return a copy of a context object with secret-valued entries masked. */
export function redactContext(
  context: Record<string, unknown> | undefined | null
): Record<string, unknown> {
  if (!context) {
    return {};
  }
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(context)) {
    out[key] = isSecretKey(key) ? redactValue(value) : value;
  }
  return out;
}

/** Mask any secret-looking keys inside a line of text. */
export function redactLine(line: string): string {
  return line.replace(/(["']?)([A-Za-z0-9_ .-]*(?:token|secret|password|api[_-]?key|pat)[A-Za-z0-9_ .-]*)(["']?\s*[=:]\s*["']?)([^\s"']+)/gi, (_m, q1, key, sep, val) => `${q1}${key}${sep}${MASK}`);
}
