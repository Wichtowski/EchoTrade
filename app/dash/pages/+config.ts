import type { Config } from "vike/types";
import vikeReact from "vike-react/config";

const appVersion =
  "process" in globalThis
    ? ((globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
        ?.VITE_APP_VERSION ?? "dev")
    : "dev";

export default {
  extends: [vikeReact],
  clientRouting: true,
  server: true,
  htmlAttributes: {
    version: appVersion,
  },
  title: "EchoDash",
} satisfies Config;
