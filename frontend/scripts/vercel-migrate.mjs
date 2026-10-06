// Wird von "vercel-build" vor `next build` ausgeführt (nur auf Vercel).
// Migriert ausschließlich Production-Deployments: Preview-Deployments teilen sonst
// dieselbe DATABASE_URL und würden mit ungemergten Migrationen die Produktions-DB ändern.
// Mit Neon-Preview-Branching (eigene DB je Preview) MIGRATE_PREVIEW=1 setzen.
import { execSync } from "node:child_process";

const target = process.env.VERCEL_ENV;
const enabled =
  process.env.MIGRATE_ON_BUILD !== "0" && (target === "production" || (target === "preview" && process.env.MIGRATE_PREVIEW === "1"));

if (enabled) {
  console.log(`[vercel-migrate] prisma migrate deploy (${target})`);
  execSync("npx prisma migrate deploy", { stdio: "inherit" });
} else {
  console.log(`[vercel-migrate] Migration übersprungen (VERCEL_ENV=${target ?? "unset"})`);
}
