import { Tabs } from "../ui";

export { RecurringInvestingSection } from "./PlanSections";
export {
  PositionsSection,
  QuoteRefreshSection,
  SnapshotsSection,
  TradeEntrySection,
  TradesSection,
} from "./WorkspaceTables";

export type PositionsWorkspaceTab = "plans" | "positions" | "trades";

export function PortfolioToolbar({
  busyAction,
  onCreateSnapshot,
}: {
  busyAction: string | null;
  onCreateSnapshot: () => void;
}) {
  return (
    <div className="toolbar">
      <button className="button secondary" disabled={busyAction === "snapshot"} onClick={onCreateSnapshot}>
        {busyAction === "snapshot" ? "Creating snapshot…" : "Create snapshot now"}
      </button>
    </div>
  );
}

export function PositionsWorkspaceTabs({
  activeTab,
  onChange,
}: {
  activeTab: PositionsWorkspaceTab;
  onChange: (tab: PositionsWorkspaceTab) => void;
}) {
  return (
    <Tabs
      activeTab={activeTab}
      items={[
        { id: "plans", label: "Plans" },
        { id: "positions", label: "Positions" },
        { id: "trades", label: "Manual Trade" },
      ]}
      onChange={(tabId) => onChange(tabId as PositionsWorkspaceTab)}
    />
  );
}

export function JournalSyncNotice({
  isChecking,
  isSyncing,
  hasMismatch,
}: {
  isChecking: boolean;
  isSyncing: boolean;
  hasMismatch: boolean;
}) {
  if (isChecking) {
    return <div className="status">Checking whether positions still match the trade journal…</div>;
  }
  if (isSyncing) {
    return <div className="status">Trade journal and positions drifted. Resyncing positions automatically…</div>;
  }
  if (hasMismatch) {
    return <div className="status">Trade journal and positions are being reconciled automatically.</div>;
  }
  return <div className="status">Positions are derived from the trade journal and stay in sync automatically.</div>;
}
