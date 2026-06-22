import { FiAlertCircle, FiClock, FiLayers } from "react-icons/fi";
import { ImDownload } from "react-icons/im";

import { Spinner } from "../ui";
import type { BrowserCaptureTask } from "../../lib/api";

export type ChartActionKind = "idle" | "queued" | "running" | "failed" | "bulk";

export function ChartActionIcon({
  kind,
  title,
}: {
  kind: ChartActionKind;
  title: string;
}) {
  if (kind === "running") {
    return <Spinner className="spinner-subtle" />;
  }
  if (kind === "queued") {
    return <FiClock aria-label={title} title={title} />;
  }
  if (kind === "failed") {
    return <FiAlertCircle aria-label={title} title={title} />;
  }
  if (kind === "bulk") {
    return <FiLayers aria-label={title} title={title} />;
  }
  return <ImDownload aria-label={title} title={title} />;
}

export function resolveChartActionState(task: BrowserCaptureTask | null | undefined, isBusy: boolean) {
  if (isBusy) {
    return {
      kind: "running" as const,
      title: "Queueing history ingest",
      isBlocked: true,
    };
  }
  if (task?.status === "running") {
    return {
      kind: "running" as const,
      title: "History ingest running",
      isBlocked: true,
    };
  }
  if (task?.status === "queued") {
    return {
      kind: "queued" as const,
      title: "History ingest queued",
      isBlocked: true,
    };
  }
  if (task?.status === "failed") {
    return {
      kind: "failed" as const,
      title: "History ingest failed",
      isBlocked: false,
    };
  }
  return {
    kind: "idle" as const,
    title: "Ingest history",
    isBlocked: false,
  };
}
