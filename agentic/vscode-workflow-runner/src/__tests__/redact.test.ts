import { test } from "node:test";
import assert from "node:assert/strict";
import { isSecretKey, redactContext, redactLine, redactValue } from "../util/redact";

test("detects secret keys", () => {
  assert.equal(isSecretKey("api_key"), true);
  assert.equal(isSecretKey("GITHUB_PAT"), true);
  assert.equal(isSecretKey("db_password"), true);
  assert.equal(isSecretKey("business-vision"), false);
});

test("redactValue masks non-empty strings", () => {
  assert.equal(redactValue("s3cr3t"), "***REDACTED***");
  assert.equal(redactValue(""), "");
});

test("redactContext masks only secret-valued entries", () => {
  const out = redactContext({ "api-key": "x", vision: "build a portal" });
  assert.equal(out["api-key"], "***REDACTED***");
  assert.equal(out["vision"], "build a portal");
});

test("redactLine masks secret assignments", () => {
  const line = 'GITHUB_PAT="ghp_12345" and business-vision=ok';
  const masked = redactLine(line);
  assert.ok(masked.includes("***REDACTED***"));
  assert.ok(!masked.includes("ghp_12345"));
  assert.ok(masked.includes("business-vision=ok"));
});
