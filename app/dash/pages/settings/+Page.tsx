import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAISettings,
  getAutomationRuns,
  queueResearch,
  saveAISettings,
  type AISettings,
} from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { formatDateTime } from "../../src/lib/format";

export default function Page() {
  const { user } = useAuth();
  const client = useQueryClient();
  const config = useQuery({
    queryKey: ["ai-settings"],
    queryFn: getAISettings,
  });
  const runs = useQuery({
    queryKey: ["automation-runs"],
    queryFn: getAutomationRuns,
    refetchInterval: 5000,
  });
  const [draft, setDraft] = useState<AISettings | null>(null);
  const [status, setStatus] = useState("");
  const save = useMutation({
    mutationFn: saveAISettings,
    onSuccess: async () => {
      setDraft(null);
      setStatus("Settings saved. New jobs will use these models.");
      await client.invalidateQueries({ queryKey: ["ai-settings"] });
    },
  });
  const research = useMutation({
    mutationFn: queueResearch,
    onSuccess: async () => {
      setStatus("Research queued. Results will appear below.");
      await client.invalidateQueries({ queryKey: ["automation-runs"] });
    },
  });
  const value = draft ?? config.data;
  const editable = user?.role === "owner";
  const error = config.error ?? runs.error ?? save.error ?? research.error;
  function update(patch: Partial<AISettings>) {
    if (value) setDraft({ ...value, ...patch });
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (value) save.mutate(value);
  }
  return (
    <div className="stack">
      <header className="page-header">
        <span className="eyebrow">Research preferences</span>
        <h1 className="page-title">AI & Automation</h1>
        <p className="page-copy">
          Choose models for portfolio commentary and paper-trade proposals.
          Every proposal requires your approval before a simulated fill.
        </p>
      </header>
      {error && (
        <div className="status error" role="alert">
          {error instanceof Error ? error.message : "Unable to load settings"}
        </div>
      )}
      {status && (
        <div className="status" role="status">
          {status}
        </div>
      )}
      {value ? (
        <form className="panel" onSubmit={submit}>
          <h2 className="panel-title">GPT models</h2>
          <p className="panel-copy">
            {value.api_key_configured
              ? "The server has an API key configured."
              : "An API key must be configured on the server before research can run."}{" "}
            Luna is the default. Sol and Astra have higher usage costs.
          </p>
          <fieldset
            disabled={!editable || save.isPending}
            className="settings-fields"
          >
            <div className="form-grid form-grid-2">
              {(["commentary_model", "proposal_model"] as const).map((key) => (
                <div className="field" key={key}>
                  <label htmlFor={key}>
                    {key === "commentary_model"
                      ? "Commentary model"
                      : "Proposal model"}
                  </label>
                  <select
                    id={key}
                    value={value[key]}
                    onChange={(event) => update({ [key]: event.target.value })}
                  >
                    {value.available_models.map((model) => (
                      <option key={model}>{model}</option>
                    ))}
                  </select>
                </div>
              ))}
              <div className="field">
                <label htmlFor="reasoning">Reasoning effort</label>
                <select
                  id="reasoning"
                  value={value.reasoning_effort}
                  onChange={(event) =>
                    update({
                      reasoning_effort: event.target
                        .value as AISettings["reasoning_effort"],
                    })
                  }
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={value.automation_enabled}
                onChange={(event) =>
                  update({ automation_enabled: event.target.checked })
                }
              />
              Enable hourly monitoring, daily reports, weekly reviews, and
              Monday/Wednesday/Friday scans
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={value.proposals_enabled}
                onChange={(event) =>
                  update({ proposals_enabled: event.target.checked })
                }
              />
              Let scheduled scans create paper proposals while the paper account
              is active
            </label>
            <p className="panel-copy">
              Monitoring follows US exchange sessions and holidays. Daily
              reports run after close; weekly reviews run Sunday evening in
              Warsaw. Scheduled research uses your API credits.
            </p>
            <button className="button" type="submit">
              {save.isPending ? "Saving…" : "Save settings"}
            </button>
          </fieldset>
        </form>
      ) : (
        <div className="status">Loading model settings…</div>
      )}
      <section className="panel">
        <h2 className="panel-title">Run research</h2>
        <p className="panel-copy">
          Use saved settings for these requests. Paper proposals use fresh
          quotes and current research; no-trade decisions are recorded too.
        </p>
        <div className="page-toolbar-inline">
          <button
            className="button"
            disabled={
              !editable ||
              !config.data?.api_key_configured ||
              research.isPending
            }
            onClick={() => research.mutate("commentary")}
          >
            Generate commentary
          </button>
          <button
            className="button secondary"
            disabled={
              !editable ||
              !config.data?.api_key_configured ||
              research.isPending
            }
            onClick={() => research.mutate("proposal")}
          >
            Generate paper proposal
          </button>
          <a className="button secondary" href="/paper">
            Open paper account
          </a>
        </div>
      </section>
      <section className="stack">
        <h2 className="panel-title">Research & job history</h2>
        {runs.data?.length === 0 && <div className="status">No jobs yet.</div>}
        {runs.data?.map((run) => (
          <article className="panel" key={run.id}>
            <div className="panel-head">
              <h3>
                {run.kind} · {formatDateTime(run.created_at)}
              </h3>
              <span className="pill">{run.status}</span>
            </div>
            {run.error && <p className="status error">{run.error}</p>}
            {run.payload?.model && (
              <p className="panel-copy">{run.payload.model}</p>
            )}
            <p className="research-copy">
              {run.payload?.commentary ?? run.payload?.reason}
            </p>
            {run.payload?.warnings?.length ? (
              <ul>
                {run.payload.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
            {run.payload?.proposal_id && (
              <a className="button secondary" href="/paper">
                Review proposal
              </a>
            )}
            {run.payload?.sources?.length ? (
              <ul>
                {run.payload.sources
                  .filter((source) => /^https?:\/\//.test(source.url))
                  .map((source) => (
                    <li key={source.url}>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {source.title}
                      </a>
                    </li>
                  ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
