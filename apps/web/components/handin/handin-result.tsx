"use client";

/**
 * What the editor sees after their file is up: the share link, and underneath
 * it the craft review.
 *
 * THE RULE THIS FILE EXISTS TO ENFORCE
 * ------------------------------------
 * The link appears the moment it exists, whatever the review says, and never
 * below the findings.
 *
 * That is not a styling preference. This tool advises; it has never blocked a
 * delivery and is not going to start. A review that is pending, that failed
 * outright, or that is 10/100 with everything broken leaves the link exactly
 * where it was.
 *
 * It is enforced by SHAPE rather than by discipline, because discipline is what
 * a later edit quietly drops:
 *
 *   - `ShareLinkPanel` takes `{ url }`. It has no review prop, so no score, no
 *     severity and no finding count is in scope where the link is rendered. A
 *     future gate could not be written here without first widening the props,
 *     which is a visible act in review rather than a one-word condition.
 *   - `HandinResult` renders the link before the review, unconditionally, with
 *     no branch between them. Making somebody scroll past criticism to reach
 *     their link is withholding it by layout, so the order is part of the rule.
 *   - `ReviewPanel` renders findings and knows nothing about the link.
 */

import * as React from "react";
import { Check, Copy, ExternalLink } from "lucide-react";
import type { GateReview } from "@/lib/handin";

/**
 * The link, and only the link.
 *
 * Do not add a review, score, findings or status prop to this component. The
 * absence is the safeguard: what is not passed in cannot be branched on.
 */
export function ShareLinkPanel({ url }: { url: string }) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be refused (insecure origin, denied permission). The URL
      // is on screen and selectable either way, so this is not worth an error.
    }
  }

  return (
    <section
      data-testid="handin-share-link"
      className="rounded-lg border border-border bg-bg-secondary p-4"
    >
      <h2 className="text-sm font-medium text-text-primary">
        Your share link
      </h2>
      <p className="mt-1 text-xs text-text-tertiary">
        This is the link you post. It allows comments and downloads already.
      </p>

      <div className="mt-3 flex items-center gap-2">
        <input
          readOnly
          value={url}
          aria-label="Share link"
          onFocus={(e) => e.currentTarget.select()}
          className="flex-1 rounded-md border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
        />
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm text-text-primary hover:bg-bg-hover"
        >
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? "Copied" : "Copy"}
        </button>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm text-text-primary hover:bg-bg-hover"
        >
          <ExternalLink className="h-4 w-4" />
          Open
        </a>
      </div>
    </section>
  );
}

function FindingList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-4">
      {/* These two headings are the ones the existing review page uses. An
          editor reads both surfaces for the same video; different words for the
          same group would read as a different judgement. */}
      <h3 className="text-sm font-medium text-text-primary">{title}</h3>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-text-secondary">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The findings. Renders whatever the review says, including nothing.
 *
 * This component never returns null for a bad review and never reorders itself
 * around one - it sits below the link and stays there.
 *
 * `label` is the video's file name, shown when a hand-in has more than one video
 * so the editor can tell which review belongs to which cut. A single-video
 * hand-in passes no label and reads exactly as before.
 */
export function ReviewPanel({ review, label }: { review: GateReview | null; label?: string }) {
  return (
    <section
      data-testid="handin-review"
      className="mt-6 rounded-lg border border-border bg-bg-secondary p-4"
    >
      <h2 className="text-sm font-medium text-text-primary">Craft review</h2>
      {label && <p className="mt-0.5 truncate text-xs text-text-tertiary">{label}</p>}

      {review === null || review.state === "pending" ? (
        <p className="mt-2 text-sm text-text-tertiary">
          {(review?.note ?? "").trim() ||
            "The review will appear here when it is ready."}
        </p>
      ) : (
        <>
          <p className="mt-1 text-xs text-text-tertiary">
            Advice, not a gate. You decide what to act on before you deliver.
          </p>
          <FindingList title="Worth fixing" items={review.worthFixing ?? []} />
          <FindingList title="Nice to have" items={review.niceToHave ?? []} />
          {(review.worthFixing ?? []).length === 0 &&
            (review.niceToHave ?? []).length === 0 && (
              <p className="mt-2 text-sm text-text-tertiary">
                The review came back with nothing to flag.
              </p>
            )}
        </>
      )}
    </section>
  );
}

/** One video's review, with the file name to label it when a hand-in has several. */
export interface HandinReviewItem {
  review: GateReview | null;
  label?: string;
}

/**
 * Link first, reviews second. No condition between them.
 *
 * A hand-in is one share link (folder-scoped) covering every video that was
 * handed in, and one review per video. `reviews` is not consulted to decide
 * anything about the link - the link is rendered from `shareUrl` alone, above
 * the reviews, unconditionally. Each item is handed straight to `ReviewPanel`
 * and read nowhere else here, so no score, count or severity is ever in scope
 * where the link is rendered.
 */
export function HandinResult({
  shareUrl,
  reviews,
}: {
  shareUrl: string;
  reviews: HandinReviewItem[];
}) {
  return (
    <div data-testid="handin-result">
      <ShareLinkPanel url={shareUrl} />
      {reviews.map((item, i) => (
        <ReviewPanel key={i} review={item.review} label={item.label} />
      ))}
    </div>
  );
}
