import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTradeProposal,
  decideTradeProposal,
  evaluateTradeProposal,
  executePaperTrade,
  getPaperAccount,
  getTradeProposals,
  queueResearch,
  setPaperStatus,
} from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { formatDateTime, formatMoney } from "../../src/lib/format";
import { Metric } from "../../src/components/ui";

export default function Page() {
  const client = useQueryClient();
  const { user } = useAuth();
  const editable = user?.role === "owner";
  const account = useQuery({
    queryKey: ["paper-account"],
    queryFn: getPaperAccount,
    refetchInterval: 10000,
  });
  const proposals = useQuery({
    queryKey: ["trade-proposals"],
    queryFn: getTradeProposals,
    refetchInterval: 10000,
  });
  const [message, setMessage] = useState("");
  const [ticker, setTicker] = useState("AMD");
  const [action, setAction] = useState("BUY");
  const [amount, setAmount] = useState("50");
  const [thesis, setThesis] = useState("");
  const [risk, setRisk] = useState("");
  const [invalidation, setInvalidation] = useState("");
  const [source, setSource] = useState("");
  const [reviewDate, setReviewDate] = useState("");
  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["paper-account"] }),
      client.invalidateQueries({ queryKey: ["trade-proposals"] }),
    ]);
  }
  const control = useMutation({
    mutationFn: setPaperStatus,
    onSuccess: refresh,
  });
  const research = useMutation({
    mutationFn: () => queueResearch("proposal"),
    onSuccess: () =>
      setMessage(
        "Proposal research queued. Follow its progress in AI & Automation.",
      ),
  });
  const create = useMutation({
    mutationFn: createTradeProposal,
    onSuccess: async () => {
      setMessage("Proposal saved. Evaluate its risk before approval.");
      await refresh();
    },
  });
  const decision = useMutation({
    mutationFn: ({
      id,
      kind,
    }: {
      id: string;
      kind: "evaluate" | "approve" | "reject" | "execute";
    }) => {
      if (kind === "evaluate")
        return evaluateTradeProposal(id).then((result) => {
          setMessage(result.evaluator_summary);
        });
      if (kind === "execute")
        return executePaperTrade(id).then(() => {
          setMessage("Paper fill recorded.");
        });
      return decideTradeProposal(id, kind).then(() => {
        setMessage(`Proposal ${kind === "approve" ? "approved" : "rejected"}.`);
      });
    },
    onSuccess: refresh,
  });
  const error =
    account.error ??
    proposals.error ??
    control.error ??
    research.error ??
    create.error ??
    decision.error;
  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      ticker: ticker.trim().toUpperCase(),
      account_type: "experimental",
      action,
      amount: Number(amount),
      currency: "USD",
      order_type: "MARKET",
      reason: thesis,
      thesis,
      risks: [risk],
      invalidated_if: invalidation,
      time_horizon: "medium_term",
      expected_holding_period: "1–8 weeks",
      review_date: new Date(`${reviewDate}T12:00:00Z`).toISOString(),
      sources: [{ title: "Supporting research", url: source }],
    });
  }
  const money = (value: number | null | undefined) =>
    value == null ? "Unavailable" : formatMoney(value, "USD");
  const busy = decision.isPending || control.isPending;
  return (
    <div className="stack">
      <header className="page-header">
        <span className="eyebrow">Experimental account</span>
        <h1 className="page-title">Paper trading</h1>
        <p className="page-copy">
          An isolated USD account for testing decisions. Approve each proposal
          manually; all fills are simulated market orders.
        </p>
      </header>
      {error && (
        <div className="status error" role="alert">
          {error instanceof Error
            ? error.message
            : "Unable to load paper account"}
        </div>
      )}
      {message && (
        <div className="status" role="status">
          {message}
        </div>
      )}
      {account.data ? (
        <>
          <div className="page-toolbar-inline">
            <span className="pill">{account.data.status}</span>
            <button
              className="button secondary"
              disabled={!editable || busy}
              onClick={() =>
                control.mutate(
                  account.data!.status === "active" ? "paused" : "active",
                )
              }
            >
              {account.data.status === "active"
                ? "Pause paper trading"
                : "Activate paper trading"}
            </button>
            <button
              className="button"
              disabled={!editable || research.isPending}
              onClick={() => research.mutate()}
            >
              Generate AI proposal
            </button>
            <a className="button secondary" href="/settings">
              Models & job history
            </a>
          </div>
          <div className="grid grid-3">
            <Metric label="Cash" value={money(account.data.cash)} />
            <Metric label="Equity" value={money(account.data.equity)} />
            <Metric
              label="Realized P/L"
              value={money(account.data.realized_pnl)}
            />
          </div>
          <p className="panel-copy">
            Starting cash: {money(account.data.initial_cash)}. Fills use fresh
            stored quotes with fractional quantities and zero fees. They do not
            model spreads, slippage, or broker execution.
          </p>
          {account.data.warnings.map((warning) => (
            <div className="status error" key={warning}>
              {warning}
            </div>
          ))}
          <section className="panel">
            <h2 className="panel-title">Paper positions</h2>
            {account.data.positions.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Quantity</th>
                      <th>Average price</th>
                      <th>Value</th>
                      <th>Unrealized P/L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {account.data.positions.map((position) => (
                      <tr key={position.ticker}>
                        <td>{position.ticker}</td>
                        <td>{position.quantity.toFixed(6)}</td>
                        <td>{money(position.average_price)}</td>
                        <td>{money(position.market_value)}</td>
                        <td>{money(position.unrealized_pnl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="panel-copy">No paper holdings yet.</p>
            )}
          </section>
        </>
      ) : (
        <div className="status">Loading paper account…</div>
      )}
      <section className="stack">
        <h2 className="panel-title">Trade proposals</h2>
        {proposals.data?.length === 0 && (
          <div className="status">No proposals yet.</div>
        )}
        {proposals.data?.map((proposal) => (
          <article className="panel" key={proposal.id}>
            <div className="panel-head">
              <h3>
                {proposal.action} {proposal.ticker} ·{" "}
                {formatMoney(proposal.amount, proposal.currency)}
              </h3>
              <span className="pill">{proposal.status}</span>
            </div>
            <p>{proposal.thesis ?? proposal.reason}</p>
            <p className="panel-copy">
              Risks: {(proposal.risks ?? []).join("; ")}
              <br />
              Invalidated if: {proposal.invalidated_if}
              <br />
              Review:{" "}
              {proposal.review_date
                ? formatDateTime(proposal.review_date)
                : "Missing"}
            </p>
            {proposal.sources
              ?.filter((item) => /^https?:\/\//.test(item.url))
              .map((item) => (
                <p key={item.url}>
                  <a href={item.url} target="_blank" rel="noopener noreferrer">
                    {item.title}
                  </a>
                </p>
              ))}
            <div className="page-toolbar-inline">
              {proposal.status === "pending" && (
                <>
                  <button
                    className="button secondary"
                    disabled={!editable || busy}
                    onClick={() =>
                      decision.mutate({ id: proposal.id, kind: "evaluate" })
                    }
                  >
                    Evaluate risk
                  </button>
                  <button
                    className="button"
                    disabled={
                      !editable || busy || account.data?.status !== "active"
                    }
                    onClick={() =>
                      decision.mutate({ id: proposal.id, kind: "approve" })
                    }
                  >
                    Approve
                  </button>
                </>
              )}
              {proposal.status === "approved" && (
                <button
                  className="button"
                  disabled={
                    !editable || busy || account.data?.status !== "active"
                  }
                  onClick={() =>
                    decision.mutate({ id: proposal.id, kind: "execute" })
                  }
                >
                  Execute paper trade
                </button>
              )}
              {["pending", "approved"].includes(proposal.status) && (
                <button
                  className="button secondary"
                  disabled={!editable || busy}
                  onClick={() =>
                    decision.mutate({ id: proposal.id, kind: "reject" })
                  }
                >
                  Reject
                </button>
              )}
            </div>
          </article>
        ))}
      </section>
      <details className="panel">
        <summary>Create a manual paper proposal</summary>
        <form className="stack" onSubmit={submit}>
          <fieldset
            disabled={!editable || create.isPending}
            className="settings-fields"
          >
            <div className="form-grid form-grid-2">
              <div className="field">
                <label htmlFor="paper-ticker">Ticker</label>
                <input
                  id="paper-ticker"
                  required
                  value={ticker}
                  onChange={(event) => setTicker(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="paper-action">Action</label>
                <select
                  id="paper-action"
                  value={action}
                  onChange={(event) => setAction(event.target.value)}
                >
                  <option>BUY</option>
                  <option>SELL</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="paper-amount">Notional amount (USD)</label>
                <input
                  id="paper-amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="paper-review">Review date</label>
                <input
                  id="paper-review"
                  type="date"
                  required
                  min={new Date(Date.now() + 86400000)
                    .toISOString()
                    .slice(0, 10)}
                  value={reviewDate}
                  onChange={(event) => setReviewDate(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="paper-thesis">Thesis</label>
                <textarea
                  id="paper-thesis"
                  required
                  value={thesis}
                  onChange={(event) => setThesis(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="paper-risk">Risk</label>
                <textarea
                  id="paper-risk"
                  required
                  value={risk}
                  onChange={(event) => setRisk(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="paper-invalidation">
                  Invalidation condition
                </label>
                <input
                  id="paper-invalidation"
                  required
                  value={invalidation}
                  onChange={(event) => setInvalidation(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="paper-source">Research source URL</label>
                <input
                  id="paper-source"
                  type="url"
                  required
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                />
              </div>
            </div>
            <button className="button" type="submit">
              {create.isPending ? "Saving…" : "Save proposal"}
            </button>
          </fieldset>
        </form>
      </details>
      <section className="panel">
        <h2 className="panel-title">Paper fills</h2>
        {account.data?.trades.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Ticker</th>
                  <th>Action</th>
                  <th>Quantity</th>
                  <th>Price</th>
                </tr>
              </thead>
              <tbody>
                {account.data.trades.map((trade) => (
                  <tr key={trade.id}>
                    <td>{formatDateTime(trade.executed_at)}</td>
                    <td>{trade.ticker}</td>
                    <td>{trade.action}</td>
                    <td>{trade.quantity.toFixed(6)}</td>
                    <td>{money(trade.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="panel-copy">No fills in this paper account.</p>
        )}
      </section>
    </div>
  );
}
