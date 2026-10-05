import { describe as suite, expect, it } from "vitest";
import { describe } from "./coaching";

suite("coaching descriptions", () => {
  it("maps coaching codes to readable directions", () => {
    const result = describe({ status: "coaching", coaching: ["step_back"] });
    expect(result.text).toContain("Move back");
    expect(result.tone).toBe("warn");
  });
  it("shows calibration progress", () => {
    expect(describe({ status: "calibrating", progress: 0.5 }).text).toContain("50%");
  });
  it("provides a connection state before the first message", () => {
    expect(describe(null).tone).toBe("info");
  });
});
