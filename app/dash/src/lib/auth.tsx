import type { FormEvent, ReactNode } from "react";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  acceptInvite,
  getAuthStatus,
  getCurrentUser,
  login,
  logout,
  type AuthStatus,
  type AuthUser,
} from "./api";

type AuthContextValue = {
  error: string | null;
  loading: boolean;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  logoutCurrentUser: () => Promise<void>;
  refresh: () => Promise<void>;
  status: AuthStatus | null;
  acceptInviteAccount: (
    token: string,
    email: string,
    password: string,
    displayName: string
  ) => Promise<void>;
  user: AuthUser | null;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function sanitizeAuthErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) {
    return fallback;
  }
  const message = error.message.trim();
  if (!message) {
    return fallback;
  }
  if (message.includes("NetworkError") || message.includes("Failed to fetch")) {
    return "Private workspace is temporarily unavailable. Please try again in a moment."
  }
  return message;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const nextStatus = await getAuthStatus();
      setStatus(nextStatus);
      if (nextStatus.authenticated) {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } else {
        setUser(null);
      }
    } catch (err) {
      setStatus(null);
      setError(sanitizeAuthErrorMessage(err, "Private workspace is temporarily unavailable. Please try again in a moment."));
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      error,
      loading,
      status,
      user,
      refresh,
      loginWithPassword: async (email, password) => {
        setLoading(true);
        setError(null);
        try {
          const currentUser = await login({ email, password });
          setUser(currentUser);
          const nextStatus = await getAuthStatus();
          setStatus(nextStatus);
        } catch (err) {
          setError(sanitizeAuthErrorMessage(err, "Sign in failed"));
          throw err;
        } finally {
          setLoading(false);
        }
      },
      logoutCurrentUser: async () => {
        setLoading(true);
        setError(null);
        try {
          await logout();
          setUser(null);
          const nextStatus = await getAuthStatus();
          setStatus(nextStatus);
        } catch (err) {
          setError(sanitizeAuthErrorMessage(err, "Sign out failed"));
          throw err;
        } finally {
          setLoading(false);
        }
      },
      acceptInviteAccount: async (token, email, password, displayName) => {
        setLoading(true);
        setError(null);
        try {
          const currentUser = await acceptInvite({
            token,
            email,
            password,
            display_name: displayName || null,
          });
          setUser(currentUser);
          const nextStatus = await getAuthStatus();
          setStatus(nextStatus);
        } catch (err) {
          setError(sanitizeAuthErrorMessage(err, "Invite acceptance failed"));
          throw err;
        } finally {
          setLoading(false);
        }
      },
    }),
    [error, loading, status, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { error, loading, status, user, loginWithPassword, acceptInviteAccount } = useAuth();
  const inviteToken = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("invite") : null;

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [invitePassword, setInvitePassword] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [submitting, setSubmitting] = useState<"login" | "invite" | null>(null);

  if (loading && !status && !user) {
    return <div className="page"><div className="status">Loading private workspace…</div></div>;
  }

  if (user) {
    return <>{children}</>;
  }

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting("login");
    try {
      await loginWithPassword(loginEmail, loginPassword);
    } finally {
      setSubmitting(null);
    }
  };

  const handleAcceptInvite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!inviteToken) {
      return;
    }
    setSubmitting("invite");
    try {
      await acceptInviteAccount(inviteToken, inviteEmail, invitePassword, inviteDisplayName);
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <main className="page auth-page">
      <div className="auth-shell">
        <section className="auth-hero">
          <span className="eyebrow">EchoTrade</span>
          <h1 className="page-title">Trading portfolio workspace</h1>
        </section>

        {error ? <div className="status error">{error}</div> : null}

        {inviteToken ? (
          <section className="panel auth-panel">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Invitation</p>
                <h2 className="panel-title">Accept invite</h2>
              </div>
            </div>
            <form className="form" onSubmit={handleAcceptInvite}>
              <div className="form-grid form-grid-2">
                <div className="field">
                  <label htmlFor="invite-email">Email</label>
                  <input id="invite-email" onChange={(event) => setInviteEmail(event.target.value)} required type="email" value={inviteEmail} />
                </div>
                <div className="field">
                  <label htmlFor="invite-display-name">Display name</label>
                  <input id="invite-display-name" onChange={(event) => setInviteDisplayName(event.target.value)} value={inviteDisplayName} />
                </div>
                <div className="field">
                  <label htmlFor="invite-password">Password</label>
                  <input id="invite-password" minLength={12} onChange={(event) => setInvitePassword(event.target.value)} required type="password" value={invitePassword} />
                </div>
              </div>
              <button className="button" disabled={submitting === "invite"} type="submit">
                {submitting === "invite" ? "Accepting…" : "Accept invite"}
              </button>
            </form>
          </section>
        ) : null}

        {status?.has_users ? (
          <section className="panel auth-panel">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Sign in</p>
                <h2 className="panel-title">Owner or invited account</h2>
              </div>
            </div>
            <form className="form" onSubmit={handleLogin}>
              <div className="form-grid form-grid-2">
                <div className="field">
                  <label htmlFor="login-email">Email</label>
                  <input id="login-email" onChange={(event) => setLoginEmail(event.target.value)} required type="email" value={loginEmail} />
                </div>
                <div className="field">
                  <label htmlFor="login-password">Password</label>
                  <input id="login-password" onChange={(event) => setLoginPassword(event.target.value)} required type="password" value={loginPassword} />
                </div>
              </div>
              <button className="button" disabled={submitting === "login"} type="submit">
                {submitting === "login" ? "Signing in…" : "Sign in"}
              </button>
            </form>
          </section>
        ) : null}

        {!status?.has_users && !error ? (
          <div className="status error">
            This private workspace is not ready for sign-in yet.
          </div>
        ) : null}
      </div>
    </main>
  );
}
