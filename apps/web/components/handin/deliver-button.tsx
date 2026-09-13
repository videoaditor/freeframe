"use client";

/**
 * "Post delivery comment" - the editor's explicit hand-off to the client.
 *
 * On click it asks the review service (review.aditor.ai) to write the delivery comment on the
 * Trello card, as @aditorteam1, carrying this share link and the editor's name, and to mark the
 * card done. That automates the manual Trello step the editor did by hand before.
 *
 * IT IS NOT A GATE, AND IT DOES NOTHING TO THE LINK. The share link is shown above by
 * ShareLinkPanel the moment it exists, whatever the review says (see handin-result.tsx). This
 * button is a separate, always-enabled action the editor chooses to take; it never withholds,
 * delays or hides the link, and the review verdict never disables it. It only saves the editor a
 * step and guarantees their name is on the delivery for billing.
 *
 * The card move to "Approved!" is deliberately NOT done here - the client owns that step.
 */

import * as React from "react";
import { Check, Loader2, Send } from "lucide-react";
import { GATE_BASE } from "@/lib/handin";
import { Button } from "@/components/ui/button";

/**
 * Do the uploader and the card's assigned editor plausibly disagree?
 *
 * Lenient on purpose: a real mismatch is both names present and NO shared name-token and neither
 * containing the other, so "Katia" vs "Katia Muller" is not a mismatch but "Katia" vs "David" is.
 * A false mismatch would nag the editor for nothing; a missed one only means the confirm does not
 * show, and the comment still carries the true uploader's name.
 */
export function editorMismatch(uploader?: string | null, onCard?: string | null): boolean {
  const a = (uploader || "").trim().toLowerCase();
  const b = (onCard || "").trim().toLowerCase();
  if (!a || !b || a === b) return false;
  if (a.includes(b) || b.includes(a)) return false;
  const at = a.split(/\s+/).filter((t) => t.length > 1);
  const bt = new Set(b.split(/\s+/).filter((t) => t.length > 1));
  return !at.some((t) => bt.has(t));
}

type Phase = "idle" | "confirm" | "sending" | "done" | "error";

export function DeliverButton({
  shareToken,
  editorName,
  editorOnCard,
}: {
  shareToken: string;
  editorName?: string | null;
  editorOnCard?: string | null;
}) {
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [message, setMessage] = React.useState("");

  async function send() {
    setPhase("sending");
    try {
      const res = await fetch(`${GATE_BASE}/api/gate/deliver`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ share_token: shareToken, editor_name: (editorName || "").trim() }),
      });
      const data = (await res.json().catch(() => ({}))) as { posted?: boolean; reason?: string; error?: string; detail?: string };
      if (!res.ok) {
        setMessage(data.detail || data.error || "Could not post the delivery comment. You can still post the link on the card by hand.");
        setPhase("error");
        return;
      }
      setMessage(
        data.reason === "already-delivered"
          ? "Already delivered - the comment is on the card."
          : "Delivery comment posted to the Trello card.",
      );
      setPhase("done");
    } catch {
      setMessage("Could not reach the review service. Try again, or post the link on the card by hand.");
      setPhase("error");
    }
  }

  function onClick() {
    if (editorMismatch(editorName, editorOnCard)) {
      setPhase("confirm");
      return;
    }
    void send();
  }

  if (phase === "done") {
    return (
      <section
        data-testid="handin-deliver"
        className="mt-6 flex items-center gap-2 rounded-lg border border-border bg-bg-secondary p-4 text-sm text-text-primary"
      >
        <Check className="h-4 w-4 text-green-500" />
        {message}
      </section>
    );
  }

  return (
    <section data-testid="handin-deliver" className="mt-6 rounded-lg border border-border bg-bg-secondary p-4">
      <h2 className="text-sm font-medium text-text-primary">Deliver to the client</h2>
      <p className="mt-1 text-xs text-text-tertiary">
        Posts this link to the Trello card as the delivery, with your name, and marks the card done.
      </p>

      {phase === "confirm" ? (
        <div className="mt-3">
          <p className="text-sm text-text-primary">
            This card is assigned to <strong>{editorOnCard}</strong>, but you are{" "}
            <strong>{editorName || "unnamed"}</strong>. Post the delivery under your name anyway?
          </p>
          <div className="mt-3 flex items-center gap-2">
            <Button type="button" onClick={() => void send()}>
              <Send className="h-4 w-4" />
              Post as me
            </Button>
            <Button type="button" variant="secondary" onClick={() => setPhase("idle")}>
              I&apos;ll fix the card
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <Button type="button" onClick={onClick} disabled={phase === "sending"}>
            {phase === "sending" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {phase === "sending" ? "Posting" : "Post delivery comment"}
          </Button>
          {phase === "error" && <p role="alert" className="mt-2 text-sm text-red-500">{message}</p>}
        </div>
      )}
    </section>
  );
}
