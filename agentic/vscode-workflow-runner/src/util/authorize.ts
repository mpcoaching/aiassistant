/**
 * Role-based authorization helper.
 *
 * The Workflow Engine is the source of truth for authorization; this client
 * side check only disables the Run action in the UI before a request is made,
 * giving fast feedback. The server always re-validates against the Agent
 * Registry.
 */
export function isRoleAuthorized(
  userRoles: string[],
  allowedRoles?: string[]
): boolean {
  if (!allowedRoles || allowedRoles.length === 0) {
    return true; // open workflow — anyone may run
  }
  const set = new Set(userRoles.map((r) => r.toLowerCase()));
  if (set.has("admin")) {
    return true;
  }
  return allowedRoles.some((r) => set.has(r.toLowerCase()));
}
