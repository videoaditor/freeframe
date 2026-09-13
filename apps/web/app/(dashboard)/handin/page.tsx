"use client";

/**
 * Hand in a video: one route instead of two.
 *
 * Today an editor uploads to FreeFrame and, separately, hands the same file to
 * review.aditor.ai for a craft review. This page does both from one screen and
 * gives back the share link to post.
 *
 * ADDITIVE BY CONSTRUCTION. Nothing here removes or restricts the existing
 * route - an editor who ignores this page uploads exactly as before. It lives
 * under (dashboard), so FreeFrame's own middleware already requires a signed-in
 * editor before the page renders; there is no second login. It renders at all
 * only when NEXT_PUBLIC_REVIEW_GATE_URL is set, so a build that is not Aditor's
 * does not grow a route pointing at Aditor's review service.
 *
 * The share link is created in code with `permission: comment` and
 * `allow_download: true`. Those are not defaults worth leaving to a dialog:
 * without commenting the review cannot be posted at all, and without downloads
 * only the streaming copy exists, which cannot be analysed. An editor should
 * not have to know that.
 *
 * On the one rule that governs the result, see the header of
 * `components/handin/handin-result.tsx`.
 */

import * as React from "react";
import { Check, Film, Loader2, Upload } from "lucide-react";
import { api } from "@/lib/api";
import {
  GATE_BASE,
  fetchReview,
  isHandinConfigured,
  lookUpCard,
  type GateCard,
  type GateReview,
} from "@/lib/handin";
import { HandinResult } from "@/components/handin/handin-result";
import { DeliverButton } from "@/components/handin/deliver-button";
import { UploadZone } from "@/components/upload/upload-zone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUploadStore } from "@/stores/upload-store";
import { useAuthStore } from "@/stores/auth-store";
import { usePageTitle } from "@/hooks/use-page-title";
import type { Project, ShareLink } from "@/types";

/** How often to ask the gate for the review once an asset exists. */
const REVIEW_POLL_MS = 5000;

/** Human file size for the selected-file chip. */
function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Phase = "form" | "working" | "done";

export default function HandinPage() {
  usePageTitle("Hand in");

  const [cardUrl, setCardUrl] = React.useState("");
  const [card, setCard] = React.useState<GateCard | null>(null);
  const [lookingUp, setLookingUp] = React.useState(false);
  const [file, setFile] = React.useState<File | null>(null);
  const [phase, setPhase] = React.useState<Phase>("form");
  const [step, setStep] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const [shareUrl, setShareUrl] = React.useState<string | null>(null);
  const [shareToken, setShareToken] = React.useState<string | null>(null);
  const [delivered, setDelivered] = React.useState(false);
  const [assetId, setAssetId] = React.useState<string | null>(null);
  const [review, setReview] = React.useState<GateReview | null>(null);

  const startUpload = useUploadStore((s) => s.startUpload);
  // Who is delivering, so the delivery comment carries their name. FreeFrame already knows the
  // signed-in editor; the editor never types it.
  const user = useAuthStore((s) => s.user);

  // Look the card up on blur or paste. The editor types neither name nor brand;
  // both come back from the card so the project cannot be misfiled by a typo.
  const runLookup = React.useCallback(async (url: string) => {
    const trimmed = url.trim();
    if (!trimmed) {
      setCard(null);
      return;
    }
    setLookingUp(true);
    try {
      setCard(await lookUpCard(trimmed));
    } finally {
      setLookingUp(false);
    }
  }, []);

  /**
   * Poll the gate for the review.
   *
   * This effect owns the review and nothing else. It never touches `shareUrl`,
   * so no answer it receives - pending, ready, or a total failure to parse -
   * can affect whether the link is on screen.
   */
  React.useEffect(() => {
    if (!assetId) return;
    let cancelled = false;

    async function tick() {
      const next = await fetchReview(assetId as string);
      if (cancelled) return;
      setReview(next);
      return next.state === "ready";
    }

    let timer: ReturnType<typeof setInterval> | undefined;
    void tick().then((ready) => {
      if (cancelled || ready) return;
      timer = setInterval(async () => {
        const done = await tick();
        if (done && timer) clearInterval(timer);
      }, REVIEW_POLL_MS);
    });

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [assetId]);

  /**
   * Wait for the bytes to land, then hand back the asset id.
   *
   * The store records `assetId` as soon as the upload is initiated, but a link
   * to a half-uploaded file is a promise we cannot keep - so this waits for the
   * upload itself to finish (processing may still be running, which is fine:
   * the link works and the review is what waits on the transcode).
   */
  function waitForUpload(fileId: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const check = (state: ReturnType<typeof useUploadStore.getState>) => {
        const entry = state.files.find((f) => f.id === fileId);
        if (!entry) return;
        if (entry.status === "failed") {
          unsubscribe();
          reject(new Error(entry.error ?? "Upload failed"));
        } else if (entry.status === "cancelled") {
          unsubscribe();
          reject(new Error("Upload cancelled"));
        } else if (
          (entry.status === "processing" || entry.status === "complete") &&
          entry.assetId
        ) {
          unsubscribe();
          resolve(entry.assetId);
        }
      };
      const unsubscribe = useUploadStore.subscribe(check);
      check(useUploadStore.getState());
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setPhase("working");
    setError(null);

    try {
      // The project is named after the card, and the card's URL goes in the
      // description. That description is how the brand is resolved downstream -
      // the review finds the card from it - so it is load-bearing, not a note.
      setStep("Creating the project");
      const projectName = (card?.name ?? "").trim() || file.name;
      const project = await api.post<Project>("/projects", {
        name: projectName,
        description: cardUrl.trim() || null,
        // Aditor is one team working across every brand, so a hand-in belongs
        // to the team rather than to the editor who happened to upload it.
        project_type: "team",
      });

      setStep("Uploading");
      const uploadId = startUpload(file, project.id, file.name, project.name);
      const newAssetId = await waitForUpload(uploadId);

      // ONE LINK, NOT TWO.
      //
      // Creating a project already mints a standing share link for Auto Review
      // (services/automation_share.py, live on this instance). Minting a second
      // one here would hand the editor a choice between two links that look
      // alike and behave differently - the surest way to have the wrong one
      // posted to a client.
      //
      // The standing link is also the BETTER link to send: it is project-scoped,
      // so a card with three hooks is one link showing all three, while an
      // asset-level link shows one file. And it carries the two settings the
      // review cannot work without - permission: comment and allow_download -
      // because it is created in code rather than through a dialog.
      //
      // Only if there is no standing link (an instance with the webhook
      // unconfigured) does this create one, with the same two settings, so the
      // editor never has to find them.
      setStep("Getting the share link");
      const existing = await api
        .get<{ token: string; permission: string; share_type: string }[]>(
          `/projects/${project.id}/share-links`,
        )
        .catch(() => []);
      const standing = (existing ?? []).find(
        (l) => l.share_type === "project" && l.permission === "comment",
      );

      let token: string;
      if (standing) {
        token = standing.token;
      } else {
        const res = await api.post<{ share_link: ShareLink & { url?: string } }>(
          `/projects/${project.id}/share`,
          { permission: "comment", allow_download: true },
        );
        token = res.share_link.token;
      }
      const url = `${window.location.origin}/share/${token}`;

      // TELL THE REVIEWER THIS ONE WAS ASKED FOR.
      //
      // Every project registers itself and lands DISARMED - reviewing an upload nobody asked about
      // puts a comment in front of somebody's client. A hand-in is the exception: the editor came
      // to this page, pasted their card and is waiting for feedback. Without this call the review
      // panel below would say "The review will appear here" and mean it for ever.
      //
      // Best effort. A failure here costs the review, not the hand-in: the link is already on
      // screen and the upload is already done.
      // Registering the hand-in (via=gate) arms the review AND, when the card is on one of our
      // boards, posts the delivery comment on the Trello card and marks it done - automatically,
      // because hitting "Hand in" IS the editor's decision to deliver. `editor_name` is what the
      // delivery comment is signed with. Best effort: a failure here costs the auto-delivery, not
      // the hand-in - the link is already on screen and the manual "Post delivery comment" button
      // below is the fallback.
      try {
        const regRes = await fetch(`${GATE_BASE}/api/freeframe/project-registered`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            share_token: token,
            project_name: project.name,
            // The Trello URL is how the brand is resolved on the other side.
            description: cardUrl.trim() || "",
            via: "gate",
            editor_name: user?.name || "",
          }),
        });
        const reg = (await regRes.json().catch(() => ({}))) as { delivered?: boolean };
        setDelivered(!!reg.delivered);
      } catch {
        /* auto-delivery is best effort; the manual button below covers a failure */
      }

      // The link goes on screen here, before a single word of the review has
      // been asked for, let alone read.
      setShareUrl(url);
      setShareToken(token);
      setAssetId(newAssetId);
      setPhase("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setPhase("form");
    }
  }

  if (!isHandinConfigured()) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <h1 className="text-lg font-medium text-text-primary">Hand in</h1>
        <p className="mt-2 text-sm text-text-tertiary">
          This build has no review service configured, so hand-in is off. Set
          NEXT_PUBLIC_REVIEW_GATE_URL to turn it on.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-lg font-medium text-text-primary">Hand in</h1>
      <p className="mt-1 text-sm text-text-tertiary">
        Upload once. It&apos;s delivered to your Trello card automatically - the link is posted
        there with your name and the card is marked done - and you get a craft review here.
      </p>

      {phase === "done" && shareUrl ? (
        <div className="mt-6">
          {/* Link first, review second. See handin-result.tsx. */}
          <HandinResult shareUrl={shareUrl} review={review} />
          {/* Handing in delivers to the Trello card automatically. Show that it happened; only if
              the auto-delivery did not go through do we fall back to the manual button. The link
              itself is shown above regardless - delivery never gates it. */}
          {delivered ? (
            <section
              data-testid="handin-delivered"
              className="mt-6 flex items-center gap-2 rounded-lg border border-border bg-bg-secondary p-4 text-sm text-text-primary"
            >
              <Check className="h-4 w-4 text-green-500" />
              Delivered to the Trello card, with your name.
            </section>
          ) : (
            shareToken && (
              <DeliverButton
                shareToken={shareToken}
                editorName={user?.name}
                editorOnCard={card?.editorOnCard}
              />
            )
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 space-y-5 rounded-xl border border-border bg-bg-secondary p-6">
          <div>
            <label
              htmlFor="card-url"
              className="text-sm font-medium text-text-primary"
            >
              Trello card link
            </label>
            <Input
              id="card-url"
              value={cardUrl}
              placeholder="https://trello.com/c/..."
              onChange={(e) => setCardUrl(e.target.value)}
              onBlur={(e) => void runLookup(e.target.value)}
              onPaste={(e) =>
                void runLookup(e.clipboardData.getData("text") || cardUrl)
              }
              className="mt-1.5"
            />

            {lookingUp && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-text-tertiary">
                <Loader2 className="h-3 w-3 animate-spin" />
                Looking up the card
              </p>
            )}

            {/* Confirmation, so the editor can see the right card was found.
                Name and brand are shown, never typed. */}
            {!lookingUp && card && (card.name || card.brand) && (
              <div
                data-testid="card-confirmation"
                className="mt-2 rounded-md border border-border bg-bg-tertiary px-3 py-2"
              >
                {card.name && (
                  <p className="text-sm text-text-primary">{card.name}</p>
                )}
                {card.brand && (
                  <p className="text-xs text-text-tertiary">{card.brand}</p>
                )}
                {card.hasBriefing === false && (
                  <p className="mt-1 text-xs text-text-tertiary">
                    No briefing found on this card. You can still upload - the
                    review will say what it could not check.
                  </p>
                )}
              </div>
            )}

            {!lookingUp && card?.note && (
              <p className="mt-2 text-xs text-text-tertiary">{card.note}</p>
            )}
          </div>

          <div>
            <label className="text-sm font-medium text-text-primary">Video file</label>
            {file ? (
              <div className="mt-1.5 flex items-center justify-between rounded-lg border border-border bg-bg-tertiary px-3 py-2.5">
                <span className="mr-2 flex min-w-0 items-center gap-2 text-sm text-text-primary">
                  <Film className="h-4 w-4 shrink-0 text-text-tertiary" />
                  <span className="truncate">{file.name}</span>
                </span>
                <span className="flex shrink-0 items-center gap-3">
                  <span className="text-xs text-text-tertiary">{formatSize(file.size)}</span>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-xs text-text-tertiary transition-colors hover:text-text-primary"
                  >
                    Change
                  </button>
                </span>
              </div>
            ) : (
              <UploadZone
                className="mt-1.5"
                onFilesSelected={(files) => setFile(files[0] ?? null)}
              />
            )}
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-500">
              {error}
            </p>
          )}

          <Button type="submit" disabled={!file || phase === "working"}>
            {phase === "working" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {step}
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Hand in
              </>
            )}
          </Button>
        </form>
      )}
    </div>
  );
}
