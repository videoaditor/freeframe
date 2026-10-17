import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HandinHeld } from "../handin-held";

// Alan, 2026-10-17: only a Must-fix holds a V1; after one, V2 must clear every V1 point, Guidance included.
describe("HandinHeld", () => {
  it("V1: lists Must-fix and optional Guidance apart, and says V2 must clear both", () => {
    render(<HandinHeld showNames={false} blockers={[{ name: "Hook 1.mp4", findings: ["Must fix — CTA missing."],
      mustFix: ["Must fix — CTA missing."], guidance: ["Captions a touch small."], guidanceHolds: false, version: 1 }]} />);
    expect(screen.getByTestId("handin-mustfix").textContent).toContain("CTA missing");
    expect(screen.getByTestId("handin-mustfix").textContent).not.toContain("Must fix —");
    expect(screen.getByTestId("handin-guidance").textContent).toMatch(/optional/i);
    expect(screen.getByTestId("handin-guidance").textContent).toContain("Captions a touch small.");
    expect(screen.getByTestId("handin-v2-rule").textContent).toMatch(/V2 has to fix every point below, Guidance included/);
  });

  it("V2+: the still-open V1 Guidance is shown as holding, without a Must-fix block", () => {
    render(<HandinHeld showNames={false} blockers={[{ name: "Hook 1.mp4", findings: ["Captions a touch small."],
      mustFix: [], guidance: ["Captions a touch small."], guidanceHolds: true, version: 2 }]} />);
    expect(screen.queryByTestId("handin-mustfix")).toBeNull();
    expect(screen.getByTestId("handin-guidance").textContent).toMatch(/Guidance from V1 · still open/);
    expect(screen.getByTestId("handin-v2-rule").textContent).toMatch(/Your V2 has to fix every point from V1/);
  });

  it("an older worker without the split still shows every finding as one list", () => {
    render(<HandinHeld showNames blockers={[{ name: "Hook 2.mp4", findings: ["Must fix: captions"] }]} />);
    expect(screen.getByText("Hook 2.mp4")).toBeTruthy();
    expect(screen.getByText("Must fix: captions")).toBeTruthy();
    expect(screen.queryByTestId("handin-mustfix")).toBeNull();
  });

  it("two-pass: while Guidance is still coming, says so quietly and points at the Must-fix", () => {
    render(<HandinHeld showNames={false} blockers={[{ name: "Hook 1.mp4", findings: ["Must fix — Logo missing."],
      mustFix: ["Must fix — Logo missing."], guidance: [], guidanceHolds: false, version: 1, guidancePending: true }]} />);
    expect(screen.getByTestId("handin-mustfix").textContent).toContain("Logo missing");
    expect(screen.getByTestId("handin-guidance-pending").textContent).toMatch(/More guidance is coming. Start on the Must-fix./);
  });

  it("no pending line once pass 2 is done (or from a worker without two-pass)", () => {
    render(<HandinHeld showNames={false} blockers={[{ name: "Hook 1.mp4", findings: ["Must fix — Logo missing."],
      mustFix: ["Must fix — Logo missing."], guidance: ["Pacing. Slow at 0:04."], guidanceHolds: false, version: 1 }]} />);
    expect(screen.queryByTestId("handin-guidance-pending")).toBeNull();
  });
});
