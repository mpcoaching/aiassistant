import { test } from "node:test";
import assert from "node:assert/strict";
import { isRoleAuthorized } from "../util/authorize";

test("open workflow (no roles) is authorized for anyone", () => {
  assert.equal(isRoleAuthorized([], undefined), true);
  assert.equal(isRoleAuthorized([], []), true);
});

test("role match is case-insensitive", () => {
  assert.equal(isRoleAuthorized(["Developer"], ["developer"]), true);
});

test("admin is always authorized", () => {
  assert.equal(isRoleAuthorized(["admin"], ["cio"]), true);
});

test("non-matching role is denied", () => {
  assert.equal(isRoleAuthorized(["developer"], ["cio", "ea"]), false);
});
