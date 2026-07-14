import { describe, it, expect } from "vitest";
import { esc } from "../src/api.js";

describe("api.esc (HTML escaping)", () => {
  it("escapes angle brackets, quotes and ampersands", () => {
    expect(esc('<script>alert("x")</script>')).toBe(
      "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    );
    expect(esc("a & b")).toBe("a &amp; b");
  });

  it("handles null/undefined safely", () => {
    expect(esc(null)).toBe("");
    expect(esc(undefined)).toBe("");
  });
});
