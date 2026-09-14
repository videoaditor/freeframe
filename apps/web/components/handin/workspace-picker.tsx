"use client";

/**
 * Pick the brand workspace a hand-in belongs to - or create a new one.
 *
 * A searchable dropdown, because there are many projects and a plain <select> of 100+ is unusable,
 * and because the card's brand can't be mapped to a project automatically (projects carry no brand,
 * and names don't derive from the brand - e.g. "BROX" is the project "Vital Growth - Workspace").
 * So the editor confirms the destination, pre-filled when we can guess it. Typing a name that is
 * not in the list offers "Create workspace" - a new brand comes online without anyone wiring a map.
 */

import * as React from "react";
import { Check, ChevronDown, Plus, Search } from "lucide-react";

export type WorkspaceChoice =
  | { kind: "existing"; id: string; name: string }
  | { kind: "create"; name: string };

export function WorkspacePicker({
  projects,
  value,
  onChange,
  allowCreate = false,
}: {
  projects: { id: string; name: string }[];
  value: WorkspaceChoice | null;
  onChange: (choice: WorkspaceChoice) => void;
  /**
   * Whether this user may create a new workspace. Only admins can - a new brand comes online
   * through onboarding or an admin, never an editor. Editors typing an unknown name were how
   * per-card "workspaces" got made, so for them the create option is simply not offered.
   */
  allowCreate?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = projects.filter((p) => p.name.toLowerCase().includes(q)).slice(0, 50);
  const exact = projects.some((p) => p.name.trim().toLowerCase() === q);
  const label = value ? (value.kind === "create" ? `Create "${value.name}"` : value.name) : "";

  return (
    <div className="relative mt-1.5" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-md border border-border bg-bg-primary px-3 py-2 text-left text-sm text-text-primary transition-colors hover:border-border-focus"
      >
        <span className={label ? "truncate text-text-primary" : "text-text-tertiary"}>
          {label || "Select or create a workspace"}
        </span>
        <ChevronDown className="ml-2 h-4 w-4 shrink-0 text-text-tertiary" />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-border bg-bg-secondary shadow-xl">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search workspaces"
              aria-label="Search workspaces"
              className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary"
            />
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.map((p) => {
              const selected = value?.kind === "existing" && value.id === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => { onChange({ kind: "existing", id: p.id, name: p.name }); setOpen(false); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-text-primary hover:bg-bg-hover"
                >
                  <Check className={`h-3.5 w-3.5 shrink-0 ${selected ? "opacity-100 text-accent" : "opacity-0"}`} />
                  <span className="truncate">{p.name}</span>
                </button>
              );
            })}

            {allowCreate && q && !exact && (
              <button
                type="button"
                onClick={() => { onChange({ kind: "create", name: query.trim() }); setOpen(false); }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-accent hover:bg-bg-hover"
              >
                <Plus className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">Create workspace &ldquo;{query.trim()}&rdquo;</span>
              </button>
            )}

            {!filtered.length && !q && (
              <p className="px-3 py-2 text-xs text-text-tertiary">
                {allowCreate ? "Type to search, or to name a new workspace." : "Type to search your brand workspace."}
              </p>
            )}
            {!filtered.length && q && !allowCreate && (
              <p className="px-3 py-2 text-xs text-text-tertiary">
                No workspace found. Ask an admin to add this brand.
              </p>
            )}
            {!filtered.length && q && allowCreate && exact && (
              <p className="px-3 py-2 text-xs text-text-tertiary">No other match.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
