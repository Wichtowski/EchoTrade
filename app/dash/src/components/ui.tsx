import type { ReactNode } from "react";

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

export function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  );
}

export function AccordionSection({
  kicker,
  title,
  badge,
  defaultOpen = false,
  children,
}: {
  kicker: string;
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="accordion panel" open={defaultOpen}>
      <summary className="accordion-summary">
        <div>
          <p className="panel-kicker">{kicker}</p>
          <h2 className="panel-title">{title}</h2>
        </div>
        <div className="accordion-summary-meta">
          {badge ? <span className="pill">{badge}</span> : null}
          <span className="accordion-chevron" aria-hidden="true">
            ▾
          </span>
        </div>
      </summary>
      <div className="accordion-body">{children}</div>
    </details>
  );
}

export type ToastTone = "info" | "success" | "error";

export function Spinner({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`spinner${className ? ` ${className}` : ""}`} />;
}

export type ToastItem = {
  id: number;
  message: string;
  tone: ToastTone;
};

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  return (
    <div className="toast-viewport" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div className={`toast toast-${toast.tone}`} key={toast.id} role="status">
          <span>{toast.message}</span>
          <button aria-label="Dismiss notification" onClick={() => onDismiss(toast.id)} type="button">
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

export function Tabs({
  items,
  activeTab,
  onChange,
}: {
  items: Array<{ id: string; label: string }>;
  activeTab: string;
  onChange: (tabId: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => (
        <button
          aria-selected={item.id === activeTab}
          className={`tab-button${item.id === activeTab ? " active" : ""}`}
          key={item.id}
          onClick={() => onChange(item.id)}
          role="tab"
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
