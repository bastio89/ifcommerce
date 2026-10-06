// Prisma-CLI-Konfiguration (Prisma 7). Das Schema liegt zentral in /prisma,
// weil es von Frontend (Prisma Client) und Backend (asyncpg) geteilt wird.
import "dotenv/config";
import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "../prisma/schema.prisma",
  migrations: {
    path: "../prisma/migrations",
  },
  datasource: {
    // Die CLI (Migrationen) braucht eine DIREKTE Verbindung – nie einen PgBouncer-Pooler.
    // Neon/Vercel liefern sie als DATABASE_URL_UNPOOLED; lokal/Docker reicht DATABASE_URL.
    // Für `prisma generate` wird keine echte Verbindung benötigt.
    url:
      process.env.DATABASE_URL_UNPOOLED ??
      process.env.DIRECT_URL ??
      process.env.DATABASE_URL ??
      "postgresql://placeholder:placeholder@localhost:5432/placeholder",
  },
});
