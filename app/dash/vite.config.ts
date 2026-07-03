import vike from "vike/plugin";
import { cloudflare } from "@cloudflare/vite-plugin";
import type { UserConfig } from "vite";

export default {
  plugins: [
    cloudflare({
      viteEnvironment: { name: "ssr" },
    }),
    vike(),
  ],
} satisfies UserConfig;
