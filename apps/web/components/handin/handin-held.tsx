"use client";

import * as React from "react";
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
  return (
    <section data-testid="handin-held" className="mt-6 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm">
      <p className="font-medium text-text-primary">Not delivered yet.</p>
      <p className="mt-1 text-text-secondary">
        {correction
          ? "Your V2 has to fix every point from V1 - the Must-fix and the Guidance notes. Some are still open."
          : "Something mandatory is still open. Fix it and upload a V2 into the same card."}{" "}
        If a note is wrong, reply to it in FreeFrame and it will be checked and withdrawn. Delivery happens on
        its own once everything is cleared.
      </p>
      {split && !correction && (
        <p data-testid="handin-v2-rule" className="mt-2 font-medium text-text-primary">
          V2 has to fix every point from V1 - the Must-fix and the Guidance below.
        </p>
      )}
      <ul className="mt-3 space-y-4">
        {blockers.map((b, i) => (
          <li key={b.assetId ?? i}>
            {showNames && <p className="truncate text-xs font-medium text-text-tertiary">{b.name}</p>}
            {split ? (
              <>
                <FindingList testId="handin-mustfix" title="Must fix" items={b.mustFix ?? []} />
                <FindingList
                  testId="handin-guidance"
                  title={b.guidanceHolds ? "Guidance from V1 - still open" : "Guidance - optional on this version"}
                  items={b.guidance ?? []}
                />
              </>
            ) : (
              <ul className="mt-1 space-y-1">
                {b.findings.map((f, j) => <li key={j} className="text-text-secondary">{f}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function FindingList({ title, items, testId }: { title: string; items: string[]; testId: string }) {
  if (!items.length) return null;
  return (
    <div data-testid={testId} className="mt-2">
      <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">{title}</p>
      <ul className="mt-1 space-y-1">
        {items.map((f, j) => <li key={j} className="text-text-secondary">{f}</li>)}
      </ul>
    </div>
  );
}
