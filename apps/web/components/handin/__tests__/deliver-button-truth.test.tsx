import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeliverButton } from "../deliver-button";

afterEach(() => vi.unstubAllGlobals());

function click(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => body }) as unknown as Response));
  render(<DeliverButton shareToken="t" editorName="Tim" editorOnCard="Tim" />);
  fireEvent.click(screen.getByRole("button", { name: /post delivery comment/i }));
}

describe("DeliverButton never claims a comment that was not posted", () => {
  it.each([{ posted: false, reason: "held" }, { posted: false, reason: "reviewing" }, { posted: false }])(
    "%j is not shown as posted", async (body) => {
      click(body);
      await waitFor(() => expect(screen.getByText(/not delivered/i)).toBeTruthy());
      expect(screen.queryByText(/delivery comment posted/i)).toBeNull();
    });
});
