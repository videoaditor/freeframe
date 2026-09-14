import os
from pathlib import Path
from urllib.parse import urlparse
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default S3 endpoint (local MinIO). Shared between the field default and the
# consistency validator so the two can't drift.
DEFAULT_S3_ENDPOINT = "http://minio:9000"


def _is_aws_endpoint(url: str) -> bool:
    """True if `url`'s host is an AWS S3 endpoint (an ``*.amazonaws.com`` host)."""
    host = (urlparse(url).hostname or "").lower()
    return host == "amazonaws.com" or host.endswith(".amazonaws.com")

# Find .env file - check current dir, then project root
# __file__ = apps/api/config.py, so parent.parent = project root
def _find_env_file() -> str:
    project_root = Path(__file__).parent.parent.parent  # freeframe/
    candidates = [
        Path(".env"),
        Path(".env.local"),
        project_root / ".env",
        project_root / ".env.local",
    ]
    for p in candidates:
        if p.exists():
            return str(p.resolve())
    return ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra env vars not in model
    )

    database_url: str
    redis_url: str
    s3_storage: str = "minio"  # "s3" for AWS S3, "minio" for local MinIO
    s3_bucket: str = "freeframe"
    s3_endpoint: str = DEFAULT_S3_ENDPOINT
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_public_endpoint: str | None = None  # External URL for presigned URLs (e.g. http://localhost:9000 when S3_ENDPOINT is http://minio:9000)
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    # Two different questions. The access token is the credential on the wire:
    # it rides in Authorization headers and, for EventSource, in a query string
    # that lands in the reverse proxy's access log, so its lifetime is how long
    # a leaked copy keeps working. `token_version` is only checked when
    # refreshing, so this is also the whole revocation window for a live
    # session. Keep it short. The refresh token is the session: it goes to one
    # endpoint, rotates on every use, and is version-checked, so it can be long
    # without the same exposure. Editors staying signed in for a quarter is a
    # question for the second number, never the first.
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 90
    frontend_url: str = "http://localhost:3000"

    # A standing share link for an automation, created with every new project and POSTed to this
    # URL. Empty (the default) means no link is created and nothing is sent.
    #
    # Why: an automation that comments as a guest can only see projects explicitly shared with it,
    # so every project needed a link made by hand. One got one; the rest were simply unwatched -
    # not broken, which is the harder failure to notice.
    automation_share_webhook_url: str = ""
    automation_share_webhook_secret: str = ""
    # Extra browser origins allowed by CORS, comma-separated (in addition to the
    # frontend + localhost defaults). Set to "*" to allow any origin — handy for
    # testing on a LAN via a machine's IP; do not use "*" in production.
    cors_allow_origins: str = ""
    transcoder_engine: str = "ffmpeg"

    # Require every project's description to carry something - typically a link to the brief in
    # whatever tool the team plans in (Trello, Notion, Asana, a ticket).
    #
    # A regex, matched against the description on create and update. Empty (the default) is off
    # and nothing changes. The hint is what the user is told when it does not match: say what to
    # paste, because "description is invalid" sends people looking for a formatting rule.
    #
    #   REQUIRE_PROJECT_DESCRIPTION_PATTERN=trello\.com/c/
    #   REQUIRE_PROJECT_DESCRIPTION_HINT=Paste the Trello card link for this project.
    #
    # Why an instance would want this: anything reading projects over the API - an automation, a
    # reporting job, a review bot - has no way back to the brief a project was made from unless
    # somebody wrote it down, and asking after the fact never works.
    require_project_description_pattern: str = ""
    require_project_description_hint: str = ""
    # The same rule one level down, for instances that file each hand-in as a FOLDER inside a
    # per-brand project rather than as a project of its own.
    require_folder_description_pattern: str = ""
    require_folder_description_hint: str = ""

    # Guest identities allowed to DELETE their own comments through a share link, comma-separated
    # emails. Empty (the default) means nobody can, which is exactly today's behaviour.
    #
    # Why this exists: an automation that comments through a share link has no account, so it can
    # never clean up after itself - a wrong or superseded run stays on a client-facing timeline
    # until a project owner happens to remove it by hand. That is not a tenable position for a tool
    # that comments automatically.
    #
    # It is deliberately narrow. It permits deleting ONLY comments whose guest author is one of
    # these exact addresses, and only through a share link that already allows commenting. No human
    # comment is reachable through it, and neither is any guest not named here.
    share_comment_deletable_guest_emails: str = ""

    # Comma-separated guest emails that belong to automation, not people - today, the automated
    # craft reviewer that comments through a share link (review@aditor.ai). Empty (the default)
    # means no guest is treated as automation, which is exactly stock behaviour.
    #
    # A comment posted by one of these guests is stored with visibility="internal", so the existing
    # share filter (which already drops internal comments from every public share view) hides it
    # from clients, while members still see it in the app. The reviewer's findings are internal
    # craft notes for the editor who handed the video in, not something a client should read on the
    # cut delivered to them - and this reuses the one internal-visibility mechanism rather than
    # adding a second hiding rule. Identity-scoped: no human guest is ever affected.
    automation_guest_emails: str = ""

    # Maximum size (bytes) for a single uploaded file. 0 = unlimited (no per-file cap).
    # Note: S3 multipart still caps effective size at ~10,000 parts x chunk size.
    max_upload_bytes: int = 0

    # Reaper: uploads stuck in `uploading`/`failed` longer than this are reclaimed. Hours.
    stale_upload_timeout_hours: int = 24

    # Retention GC: rows soft-deleted (deleted_at) longer than this are hard-deleted and their
    # S3 objects reclaimed. Days. 0 (or negative) DISABLES the sweep (matches the reaper convention).
    soft_delete_retention_days: int = 30

    # Orphan S3 sweeper (issue #65 follow-up): reclaim bucket keys under raw/ + processed/ that no
    # MediaFile row owns. 0 = disabled. When > 0, only keys whose S3 LastModified is older than this
    # many hours are considered, so in-flight / just-committed uploads are never mistaken for orphans.
    orphan_sweep_grace_hours: int = 0
    # Report-only by default: when False the sweeper only LOGS what it would delete; set True to delete.
    orphan_sweep_delete: bool = False

    # Worker concurrency settings
    transcoding_concurrency: int = 2  # Number of concurrent video transcoding jobs
    email_concurrency: int = 2  # Number of concurrent email sending jobs
    
    # Email settings - supports AWS SES or any SMTP server
    # If mail_provider is "ses", uses AWS SES with aws_mail_* credentials
    # If mail_provider is "smtp", uses standard SMTP with smtp_* settings
    mail_provider: str = "ses"  # "ses" or "smtp"
    mail_from_address: str = "noreply@example.com"
    mail_from_name: str = "FreeFrame"

    # Product name shown inside email subjects and bodies. Self-hosters put their
    # own brand in front of clients, who never need to know what runs underneath.
    brand_name: str = "FreeFrame"

    # Password sign-in. Instances that authenticate purely by magic code turn
    # this off, which hides the password UI *and* closes /auth/login and
    # /auth/set-password — hiding the form alone would leave the method live.
    password_login_enabled: bool = True

    # Instance-wide project access. On, every account holds `editor` on every
    # project and superadmins hold `owner`, without a membership row existing.
    # It is for the single-team instance where everyone is expected to work on
    # everything and per-project membership is bookkeeping rather than a boundary;
    # it also gives superadmins a way to administer projects a colleague created,
    # which project ownership otherwise makes impossible.
    #
    # Guests who arrive through a share link are unaffected - they are GuestUser
    # rows and never carry a role - so this widens what account holders see and
    # nothing else. Leave it off on any instance where outsiders hold accounts.
    #
    # Off (the default) changes no behaviour.
    instance_wide_project_access: bool = False

    # Machine access. A caller presenting SERVICE_API_KEY in X-API-Key is treated
    # as the user named by SERVICE_API_KEY_EMAIL, so every existing per-project
    # permission check still applies - the key is an alternative credential for a
    # real account, not a bypass. Restricted to GET, so it can never write.
    # Unset (the default) disables the mechanism entirely.
    service_api_key: str | None = None
    service_api_key_email: str | None = None

    # Directory-backed sign-in. With DIRECTORY_LOOKUP_URL set, /auth/send-magic-code
    # checks the address against an external roster: someone listed there gets an
    # account provisioned on first sign-in, and someone the roster no longer lists
    # as active is refused. Instances whose people already live in another system
    # stop keeping a second copy of them, and nobody is invited by hand.
    #
    # The URL carries an {email} placeholder (URL-encoded on substitution) and must
    # answer with a JSON record, or a list whose first entry is one. Addresses the
    # directory says nothing about are left entirely alone, so operator and service
    # accounts are unaffected by it.
    #
    # Unset (the default) disables the lookup and changes no behaviour.
    # DIRECTORY_ALLOWED_STATUSES is a comma-separated set, not a single value: a
    # roster usually distinguishes "not working right now" from "gone", and only
    # the second should cost someone their sign-in. Getting this wrong locks out
    # people who are merely between assignments.
    directory_lookup_url: str | None = None
    directory_token: str | None = None
    directory_name_field: str = "name"
    directory_status_field: str = "status"
    directory_allowed_statuses: str = "active"
    directory_timeout_seconds: float = 5.0

    # AWS SES settings
    aws_mail_access_key_id: str | None = None
    aws_mail_secret_access_key: str | None = None
    aws_mail_region: str = "ap-south-1"
    
    # SMTP settings (for non-SES providers like SendGrid, Mailgun, self-hosted)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True

    @model_validator(mode="after")
    def _check_s3_endpoint_consistency(self):
        """Fail loud on `S3_STORAGE=s3` + a real custom (non-AWS) `S3_ENDPOINT`.

        In `s3` mode the client talks to native AWS and S3_ENDPOINT is ignored,
        so pairing it with an R2/B2/MinIO URL would silently route to AWS. An
        untouched default and any `*.amazonaws.com` endpoint are harmless and
        allowed; a custom non-AWS endpoint is a misconfiguration.
        """
        if self.s3_storage.lower() == "s3":
            endpoint = (self.s3_endpoint or "").strip()
            if endpoint and endpoint != DEFAULT_S3_ENDPOINT and not _is_aws_endpoint(endpoint):
                raise ValueError(
                    f"S3_STORAGE=s3 selects native AWS S3 and ignores S3_ENDPOINT, but "
                    f"S3_ENDPOINT is set to a non-AWS URL ({endpoint!r}). To use a custom "
                    f"S3-compatible endpoint (MinIO, Cloudflare R2, Backblaze B2, "
                    f"DigitalOcean Spaces), set S3_STORAGE=minio. To use native AWS S3, "
                    f"leave S3_ENDPOINT unset."
                )
        return self

settings = Settings()
