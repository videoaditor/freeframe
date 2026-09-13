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
import useSWR from "swr";
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
import { WorkspacePicker, type WorkspaceChoice } from "@/components/handin/workspace-picker";
import { UploadZone } from "@/components/upload/upload-zone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUploadStore } from "@/stores/upload-store";
import { useAuthStore } from "@/stores/auth-store";
import { usePageTitle } from "@/hooks/use-page-title";
import type { Project, ShareLink } from "@/types";

/** Loosely normalize a name for matching a card's brand to a workspace project. */
function norm(s: string): string {
  return s.toLowerCase().replace(/\bgmbh\b|\bug\b|\bco\b|\bkg\b|\bb\.?v\.?\b|\bltd\b|\binc\b/g, "").replace(/[^a-z0-9]/g, "");
}

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
  const [workspace, setWorkspace] = React.useState<WorkspaceChoice | null>(null);
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

  // The workspaces the editor can file this hand-in into. The card can't be mapped to a project
  // automatically (projects carry no brand), so the editor picks - pre-filled when we can guess.
  const { data: projects } = useSWR<Project[]>("/projects", (k: string) => api.get<Project[]>(k));
  const workspaceOptions = React.useMemo(
    () => (projects ?? []).map((p) => ({ id: p.id, name: p.name })).sort((a, b) => a.name.localeCompare(b.name)),
    [projects],
  );

  // Best-effort pre-select: match the card's brand/name to a "- Workspace" project. The editor
  // still sees and can change it, so a wrong guess is visible, never silent.
  React.useEffect(() => {
    if (workspace || !projects?.length || !card) return;
    const hint = norm(String(card.brand || "") + String(card.name || ""));
    if (!hint) return;
    const workspaces = projects.filter((p) => / - workspace$/i.test(p.name));
    const hit = workspaces.find((p) => {
      const n = norm(p.name.replace(/ - workspace$/i, ""));
      return n.length > 2 && (hint.includes(n) || n.includes(norm(String(card.brand || ""))));
    });
    if (hit) setWorkspace({ kind: "existing", id: hit.id, name: hit.name });
  }, [projects, card, workspace]);

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
    if (!file || !workspace) return;

    setPhase("working");
    setError(null);

    try {
      // 1. The workspace project: an existing brand workspace, or a new one the editor named.
      //    Aditor is one team across every brand, so a hand-in belongs to the team (project_type
      //    "team"), not to whoever uploaded it.
      setStep(workspace.kind === "create" ? "Creating the workspace" : "Opening the workspace");
      let projectId: string;
      let projectName: string;
      if (workspace.kind === "create") {
        const p = await api.post<Project>("/projects", { name: workspace.name, project_type: "team" });
        projectId = p.id;
        projectName = p.name;
      } else {
        projectId = workspace.id;
        projectName = workspace.name;
      }

      // 2. File the hand-in as a FOLDER in that workspace, with the card link in its description.
      //    That description is load-bearing: it is how the review resolves the brand and briefing,
      //    and creating the folder is what registers it with Auto Review (a standing folder link
      //    and arming happen server-side here). One folder per hand-in, one brand per workspace.
      setStep("Filing the hand-in");
      const folderName = (card?.name ?? "").trim() || file.name;
      const folder = await api.post<{ id: string }>(`/projects/${projectId}/folders`, {
        name: folderName,
        parent_id: null,
        description: cardUrl.trim(),
      });

      // 3. The video goes INTO that folder.
      setStep("Uploading");
      const uploadId = startUpload(file, projectId, file.name, projectName, folder.id);
      const newAssetId = await waitForUpload(uploadId);

      // 4. The link to post. Creating the folder minted the standing "Auto Review" folder link;
      //    reuse it - it is folder-scoped (this hand-in only) and already carries the two settings
      //    the review needs. Only if it is somehow absent do we mint one, with those same settings.
      setStep("Getting the share link");
      const shares = await api
        .get<{ token: string; title?: string; permission: string; is_enabled?: boolean }[]>(`/folders/${folder.id}/shares`)
        .catch(() => []);
      const standing = (shares ?? []).find(
        (s) => s.title === "Auto Review" && s.permission === "comment" && s.is_enabled !== false,
      );
      let token: string;
      if (standing) {
        token = standing.token;
      } else {
        const res = await api.post<ShareLink>(`/folders/${folder.id}/share`, {
          permission: "comment",
          allow_download: true,
        });
        token = res.token;
      }
      const url = `${window.location.origin}/share/${token}`;

      // 5. Deliver to the Trello card automatically - the folder token is already watched from
      //    step 2, so this posts the @aditorteam1 comment (with the editor's name) and marks the
      //    card done. Best effort: if it does not go through, the manual button below is the
      //    fallback, and the link is already on screen regardless.
      try {
        const dr = await fetch(`${GATE_BASE}/api/gate/deliver`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ share_token: token, editor_name: user?.name || "" }),
        });
        const dj = (await dr.json().catch(() => ({}))) as { posted?: boolean; reason?: string };
        setDelivered(dr.ok && (!!dj.posted || dj.reason === "already-delivered"));
      } catch {
        /* auto-delivery is best effort; the manual button below covers a failure */
      }

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
            <label className="text-sm font-medium text-text-primary">Workspace</label>
            <p className="mt-0.5 text-xs text-text-tertiary">
              The brand this hand-in belongs to. It&apos;s filed as a folder inside it - search, or
              type a new name to create one.
            </p>
            <WorkspacePicker
              projects={workspaceOptions}
              value={workspace}
              onChange={setWorkspace}
            />
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

          <Button type="submit" disabled={!file || !workspace || !cardUrl.trim() || phase === "working"}>
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
