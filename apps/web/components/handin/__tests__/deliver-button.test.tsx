import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DeliverButton, editorMismatch } from "../deliver-button";

afterEach(() => vi.unstubAllGlobals());

describe("editorMismatch", () => {
  it("no mismatch when a name-token is shared or one contains the other", () => {
    expect(editorMismatch("Katia", "Katia Muller")).toBe(false);
    expect(editorMismatch("Katia Muller", "katia")).toBe(false);
    expect(editorMismatch("Denis Gellert", "Denis")).toBe(false);
    expect(editorMismatch("Sam", "Sam")).toBe(false);
  });
  it("mismatch when the names clearly differ", () => {
    expect(editorMismatch("Katia", "David")).toBe(true);
    expect(editorMismatch("Alfredo", "Luk Friske")).toBe(true);
  });
  it("no mismatch when either side is missing (nothing to compare)", () => {
    expect(editorMismatch("", "David")).toBe(false);
    expect(editorMismatch("Sam", "")).toBe(false);
    expect(editorMismatch(null, null)).toBe(false);
  });
});

function stubFetch(res: { ok: boolean; body: unknown }) {
  const calls: Array<{ url: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), body: JSON.parse(String(init?.body || "{}")) });
    return { ok: res.ok, json: async () => res.body } as unknown as Response;
  }));
  return calls;
}

describe("DeliverButton", () => {
  it("no mismatch: click posts with share_token + editor_name and confirms", async () => {
    const calls = stubFetch({ ok: true, body: { posted: true } });
    render(<DeliverButton shareToken="tok1" editorName="Katia" editorOnCard="Katia Muller" />);
    fireEvent.click(screen.getByRole("button", { name: /post delivery comment/i }));
    await waitFor(() => expect(screen.getByText(/delivery comment posted/i)).toBeTruthy());
    expect(calls[0].url).toContain("/api/gate/deliver");
    expect(calls[0].body).toMatchObject({ share_token: "tok1", editor_name: "Katia" });
  });

  it("mismatch: shows the confirm first, then 'Post as me' sends under the uploader's name", async () => {
    const calls = stubFetch({ ok: true, body: { posted: true } });
    render(<DeliverButton shareToken="tok2" editorName="David" editorOnCard="Katia" />);
    fireEvent.click(screen.getByRole("button", { name: /post delivery comment/i }));
    // Confirm appears, nothing sent yet.
    await waitFor(() => expect(screen.getByText(/assigned to/i)).toBeTruthy());
    expect(calls.length).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: /post as me/i }));
    await waitFor(() => expect(screen.getByText(/delivery comment posted/i)).toBeTruthy());
    expect(calls[0].body).toMatchObject({ share_token: "tok2", editor_name: "David" });
  });

  it("already-delivered comes back as a calm confirmed state, not an error", async () => {
    stubFetch({ ok: true, body: { posted: false, reason: "already-delivered" } });
    render(<DeliverButton shareToken="tok3" editorName="Sam" editorOnCard="Sam" />);
    fireEvent.click(screen.getByRole("button", { name: /post delivery comment/i }));
    await waitFor(() => expect(screen.getByText(/already delivered/i)).toBeTruthy());
  });

  it("a failed post surfaces an error and points to posting by hand", async () => {
    stubFetch({ ok: false, body: { error: "comment-failed" } });
    render(<DeliverButton shareToken="tok4" editorName="Sam" editorOnCard="Sam" />);
    fireEvent.click(screen.getByRole("button", { name: /post delivery comment/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });
});
