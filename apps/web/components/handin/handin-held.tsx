"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import type { OpenBlocker } from "@/lib/handin";

/**
 * The "Not delivered yet" panel. Must-fix and Guidance are listed apart, because only one of them holds
 * on a first version (Alan, 2026-10-17):
 *   - V1: only the Must-fix holds. Guidance is optional - but if a Must-fix sends the cut back, the V2
 *     has to clear every point from V1, Guidance included. Said up front, so it is not a surprise on V2.
 *   - V2+ of a held V1: the V1 Guidance that is still there holds too.
 * A worker that predates the split sends only `findings`; those render as one list, as before.
 */
export function HandinHeld({ blockers, showNames }: { blockers: OpenBlocker[]; showNames: boolean }) {
  const split = blockers.some((b) => Array.isArray(b.mustFix));
  const correction = blockers.some((b) => b.guidanceHolds);
  // What to do comes first, the lists second, the way out of a wrong note last and quiet.
  return (
    <section data-testid="handin-held" className="mt-6 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm">
      <p className="font-medium text-text-primary">Not delivered yet.</p>
      <p data-testid="handin-v2-rule" className="mt-1 text-text-secondary">
        {!split
          ? "Something mandatory is still open. Fix it and upload a V2 into the same card."
          : correction
            ? "Your V2 has to fix every point from V1, Guidance included. These are still open."
            : "Fix the Must-fix and upload a V2 into the same card. Your V2 has to fix every point below, Guidance included."}
      </p>
      <ul className="mt-3 space-y-4">
        {blockers.map((b, i) => (
          <li key={b.assetId ?? i}>
            {showNames && <p className="truncate text-xs font-medium text-text-tertiary">{b.name}</p>}
            {split ? (
              <>
                <FindingList testId="handin-mustfix" title="Must fix" items={(b.mustFix ?? []).map(stripMust)} holds />
                <FindingList
                  testId="handin-guidance"
                  title={b.guidanceHolds ? "Guidance from V1 · still open" : "Guidance · optional on this version"}
                  items={b.guidance ?? []}
                  holds={!!b.guidanceHolds}
                />
                {b.guidancePending && <GuidanceComing />}
              </>
            ) : (
              <ul className="mt-1 space-y-1">
                {b.findings.map((f, j) => <li key={j} className="text-text-secondary">{f}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-text-tertiary">
        A note is wrong? Reply to it in FreeFrame and it gets checked and withdrawn. Delivery to the Trello card
        happens on its own once everything is cleared.
      </p>
    </section>
  );
}

/** Two-pass: the hold is decided, the taste read is not. Quiet, below the lists - it must never
 *  compete with the Must-fix, and it tells the editor not to wait for it. */
function GuidanceComing() {
  return (
    <p data-testid="handin-guidance-pending" role="status" className="mt-3 flex items-center gap-1.5 text-xs text-text-tertiary">
      <Loader2 aria-hidden className="h-3 w-3 motion-safe:animate-spin" />
      More guidance is coming. Start on the Must-fix.
    </p>
  );
}

/** The heading already says "Must fix", so the worker's "Must fix — " prefix on each note is noise here. */
const stripMust = (t: string) => t.replace(/^Must fix\s*[—:-]\s*/i, "");

/** What holds reads in full contrast; optional advice steps back. Same look = same behaviour. */
function FindingList({ title, items, testId, holds }: { title: string; items: string[]; testId: string; holds: boolean }) {
  if (!items.length) return null;
  return (
    <div data-testid={testId} className="mt-3">
      <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">{title}</p>
      <ul className="mt-1 space-y-1">
        {items.map((f, j) => <li key={j} className={holds ? "text-text-primary" : "text-text-secondary"}>{f}</li>)}
      </ul>
    </div>
  );
}
