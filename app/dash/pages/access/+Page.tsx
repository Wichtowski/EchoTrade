import { useEffect, useRef, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createInvite,
  getInvites,
  revokeInvite,
  type Invite,
} from "../../src/lib/api";
import { formatDateTime } from "../../src/lib/format";
import { useAuth } from "../../src/lib/auth";
import { queryKeys } from "../../src/lib/query";
import { Spinner, ToastViewport, type ToastItem, type ToastTone } from "../../src/components/ui";

const INVITE_EXPIRY_OPTIONS = [
  { label: "24 hours", value: 24 },
  { label: "3 days", value: 72 },
  { label: "7 days", value: 168 },
  { label: "14 days", value: 336 },
];

export default function Page() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [expiresInHours, setExpiresInHours] = useState("168");
  const [latestInvite, setLatestInvite] = useState<Invite | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastCounter = useRef(0);
  const lastInviteErrorRef = useRef<string | null>(null);

  function pushToast(message: string, tone: ToastTone = "info") {
    const id = ++toastCounter.current;
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 6000);
  }

  function dismissToast(id: number) {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }

  const invitesQuery = useQuery({
    queryKey: queryKeys.invites,
    queryFn: getInvites,
    enabled: user?.role === "owner",
  });

  const createInviteMutation = useMutation({
    mutationFn: () =>
      createInvite({
        email: email.trim() || null,
        expires_in_hours: Number(expiresInHours) || 168,
      }),
    onSuccess: async (invite) => {
      setLatestInvite(invite);
      setEmail("");
      pushToast(
        buildInviteSuccessMessage(invite),
        invite.delivery_state === "failed" ? "error" : "success"
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.invites });
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to create invite", "error");
    },
  });

  const revokeInviteMutation = useMutation({
    mutationFn: revokeInvite,
    onSuccess: async (_invite, inviteId) => {
      const previousInvite = (invitesQuery.data ?? []).find((invite) => invite.id === inviteId);
      pushToast(
        previousInvite?.accepted_at
          ? "Access removed and invited user data deleted."
          : "Invite revoked.",
        "success"
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.invites });
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to revoke invite", "error");
    },
  });

  const activeInvites = useMemo(
    () => (invitesQuery.data ?? []).filter((invite) => !invite.revoked_at && !invite.accepted_at),
    [invitesQuery.data]
  );
  const closedInvites = useMemo(
    () => (invitesQuery.data ?? []).filter((invite) => invite.revoked_at || invite.accepted_at),
    [invitesQuery.data]
  );

  useEffect(() => {
    if (!invitesQuery.error) {
      lastInviteErrorRef.current = null;
      return;
    }
    const message =
      invitesQuery.error instanceof Error ? invitesQuery.error.message : "Failed to load invites";
    if (lastInviteErrorRef.current === message) {
      return;
    }
    lastInviteErrorRef.current = message;
    pushToast(message, "error");
  }, [invitesQuery.error]);

  if (user?.role !== "owner") {
    return (
      <div className="stack">
        <header className="page-header">
          <span className="eyebrow">Access</span>
          <h1 className="page-title">Workspace access</h1>
          <p className="page-copy">
            Access management is limited to the workspace owner.
          </p>
        </header>
      </div>
    );
  }

  return (
    <div className="stack">
      <header className="page-header">
        <span className="eyebrow">Access</span>
        <h1 className="page-title">Private workspace access</h1>
        <p className="page-copy">
          Invite trusted people into their own isolated workspace. Market data stays shared, but portfolio records remain private per account.
        </p>
      </header>

      <section className="stack">
        <div className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">New invite</p>
              <h2 className="panel-title">Invite a friend</h2>
              <p className="panel-copy">If SMTP is configured, the invite is emailed automatically. Otherwise you can copy the link manually.</p>
            </div>
          </div>
          <form
            className="form"
            onSubmit={(event) => {
              event.preventDefault();
              void createInviteMutation.mutate();
            }}
          >
            <div className="form-grid form-grid-2">
              <div className="field">
                <label htmlFor="invite-email">Email</label>
                <input
                  id="invite-email"
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="friend@example.com"
                  type="email"
                  value={email}
                />
              </div>
              <div className="field">
                <label htmlFor="invite-expiry">Invite expiry</label>
                <select
                  id="invite-expiry"
                  onChange={(event) => setExpiresInHours(event.target.value)}
                  value={expiresInHours}
                >
                  {INVITE_EXPIRY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="page-toolbar-inline">
              <button className="button" disabled={createInviteMutation.isPending} type="submit">
                {createInviteMutation.isPending ? <Spinner /> : null}
                Create invite
              </button>
            </div>
          </form>

          {latestInvite?.invite_url ? (
            <div className="status access-code-block">
              <strong>Latest invite link</strong>
              <code>{latestInvite.invite_url}</code>
              <div className="page-toolbar-inline">
                <button
                  className="button secondary"
                  onClick={() =>
                    void copyToClipboard(
                      latestInvite.invite_url ?? "",
                      pushToast,
                      "Invite link copied."
                    )
                  }
                  type="button"
                >
                  Copy invite link
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Active</p>
              <h2 className="panel-title">Pending invites</h2>
            </div>
            <span className="pill">{String(activeInvites.length)}</span>
          </div>
          <div className="list">
            {activeInvites.map((invite) => (
              <InviteRow
                invite={invite}
                key={invite.id}
                onCopy={() =>
                  void copyToClipboard(invite.invite_url ?? "", pushToast, "Invite link copied.")
                }
                onRevoke={() => revokeInviteMutation.mutate(invite.id)}
                revoking={revokeInviteMutation.isPending && revokeInviteMutation.variables === invite.id}
              />
            ))}
            {!activeInvites.length ? (
              <div className="warning empty">No pending invites right now.</div>
            ) : null}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">History</p>
              <h2 className="panel-title">Accepted or revoked</h2>
            </div>
            <span className="pill">{String(closedInvites.length)}</span>
          </div>
          <div className="list">
            {closedInvites.map((invite) => (
              <ClosedInviteRow
                invite={invite}
                key={invite.id}
                onRemoveAccess={() => revokeInviteMutation.mutate(invite.id)}
                removing={revokeInviteMutation.isPending && revokeInviteMutation.variables === invite.id}
              />
            ))}
            {!closedInvites.length ? (
              <div className="warning empty">Invite history will appear here.</div>
            ) : null}
          </div>
        </div>
      </section>

      <ToastViewport onDismiss={dismissToast} toasts={toasts} />
    </div>
  );
}

function ClosedInviteRow({
  invite,
  onRemoveAccess,
  removing,
}: {
  invite: Invite;
  onRemoveAccess: () => void;
  removing: boolean;
}) {
  return (
    <div className="list-row access-row">
      <div>
        <strong>{invite.email || "Link-only invite"}</strong>
        <span className="list-meta">
          Created {formatDateTime(invite.created_at)}
        </span>
      </div>
      <div className="actions-inline">
        <span className="pill">
          {invite.accepted_at && !invite.revoked_at ? "Accepted" : "Revoked"}
        </span>
        {invite.accepted_at && !invite.revoked_at ? (
          <button className="button secondary button-small" disabled={removing} onClick={onRemoveAccess} type="button">
            {removing ? <Spinner /> : null}
            Remove access
          </button>
        ) : null}
      </div>
    </div>
  );
}

function InviteRow({
  invite,
  onCopy,
  onRevoke,
  revoking,
}: {
  invite: Invite;
  onCopy: () => void;
  onRevoke: () => void;
  revoking: boolean;
}) {
  return (
    <div className="list-row access-row">
      <div>
        <strong>{invite.email || "Link-only invite"}</strong>
        <span className="list-meta">
          Expires {formatDateTime(invite.expires_at)}
        </span>
        <span className="list-meta">
          Delivery: {formatDeliveryState(invite)}
        </span>
      </div>
      <div className="actions-inline">
        {invite.invite_url ? (
          <button className="button secondary button-small" onClick={onCopy} type="button">
            Copy link
          </button>
        ) : null}
        <button className="button secondary button-small" disabled={revoking} onClick={onRevoke} type="button">
          {revoking ? <Spinner /> : null}
          Revoke
        </button>
      </div>
    </div>
  );
}

function buildInviteSuccessMessage(invite: Invite): string {
  if (invite.delivery_state === "sent") {
    return `Invite created and emailed to ${invite.email}.`;
  }
  if (invite.delivery_state === "failed") {
    return invite.delivery_error
      ? `Invite created, but email delivery failed: ${invite.delivery_error}`
      : "Invite created, but email delivery failed.";
  }
  return "Invite created. Copy the link and share it manually.";
}

function formatDeliveryState(invite: Invite): string {
  if (invite.accepted_at) {
    return "accepted";
  }
  if (invite.revoked_at) {
    return "revoked";
  }
  if (invite.delivery_state === "sent") {
    return "emailed";
  }
  if (invite.delivery_state === "failed") {
    return invite.delivery_error ? `email failed - ${invite.delivery_error}` : "email failed";
  }
  return "manual link";
}

async function copyToClipboard(
  value: string,
  pushToast: (message: string, tone?: ToastTone) => void,
  successMessage: string
) {
  try {
    await navigator.clipboard.writeText(value);
    pushToast(successMessage, "success");
  } catch {
    pushToast("Clipboard copy failed.", "error");
  }
}
