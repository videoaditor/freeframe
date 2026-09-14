import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WorkspacePicker } from "../workspace-picker";

const PROJECTS = [
  { id: "p1", name: "Levide - Workspace" },
  { id: "p2", name: "Forward Health - Workspace" },
  { id: "p3", name: "AgelessRX - Workspace" },
];

describe("WorkspacePicker", () => {
  it("opens, searches, and selects an existing workspace", async () => {
    const onChange = vi.fn();
    render(<WorkspacePicker projects={PROJECTS} value={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /select or create a workspace/i }));
    const search = await screen.findByLabelText("Search workspaces");
    fireEvent.change(search, { target: { value: "forward" } });
    // Only the matching workspace is shown, and picking it reports an existing choice.
    expect(screen.queryByText("Levide - Workspace")).toBeNull();
    fireEvent.click(screen.getByText("Forward Health - Workspace"));
    expect(onChange).toHaveBeenCalledWith({ kind: "existing", id: "p2", name: "Forward Health - Workspace" });
  });

  it("offers to create a workspace when the search has no exact match (admin)", async () => {
    const onChange = vi.fn();
    render(<WorkspacePicker projects={PROJECTS} value={null} onChange={onChange} allowCreate />);
    fireEvent.click(screen.getByRole("button", { name: /select or create a workspace/i }));
    const search = await screen.findByLabelText("Search workspaces");
    fireEvent.change(search, { target: { value: "Bawldy - Workspace" } });
    const create = await screen.findByText(/Create workspace/i);
    fireEvent.click(create);
    expect(onChange).toHaveBeenCalledWith({ kind: "create", name: "Bawldy - Workspace" });
  });

  it("does NOT offer to create a workspace for an editor (allowCreate off)", async () => {
    // A per-card 'workspace' typed by an editor is exactly what left share links pointing at
    // nothing. Without create rights, an unknown name offers no create - only 'ask an admin'.
    render(<WorkspacePicker projects={PROJECTS} value={null} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /select or create a workspace/i }));
    const search = await screen.findByLabelText("Search workspaces");
    fireEvent.change(search, { target: { value: "Do not buy the levide knee - Week 6" } });
    expect(await screen.findByText(/Ask an admin to add this brand/i)).toBeTruthy();
    expect(screen.queryByText(/Create workspace/i)).toBeNull();
  });

  it("shows the selected workspace name on the trigger", () => {
    render(<WorkspacePicker projects={PROJECTS} value={{ kind: "existing", id: "p1", name: "Levide - Workspace" }} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Levide - Workspace/ })).toBeTruthy();
  });

  it("does not offer create when the query exactly matches an existing workspace", async () => {
    render(<WorkspacePicker projects={PROJECTS} value={null} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /select or create a workspace/i }));
    const search = await screen.findByLabelText("Search workspaces");
    fireEvent.change(search, { target: { value: "Levide - Workspace" } });
    await waitFor(() => expect(screen.getByText("Levide - Workspace")).toBeTruthy());
    expect(screen.queryByText(/Create workspace/i)).toBeNull();
  });
});
