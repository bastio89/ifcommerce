import { PrismaPg } from "@prisma/adapter-pg";
import { attachDatabasePool } from "@vercel/functions";
import { Pool } from "pg";

import { PrismaClient } from "@/generated/prisma/client";
import { env } from "@/lib/env";

/**
 * Prisma Client (Prisma 7, Driver Adapter "pg") über einen modulweiten Pool.
 * Im Dev-Modus wird die Instanz über Hot-Reloads hinweg wiederverwendet.
 */
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

function createClient(): PrismaClient {
  const connectionString = env().DATABASE_URL;
  if (!connectionString) throw new Error("DATABASE_URL ist nicht gesetzt.");
  const pool = new Pool({
    connectionString,
    max: 10,
    idleTimeoutMillis: 5_000,
    connectionTimeoutMillis: 5_000,
  });
  // Vercel Fluid Compute: gibt Leerlauf-Verbindungen frei, bevor eine Instanz pausiert.
  // Außerhalb von Vercel (Docker, lokal) wirkungslos.
  attachDatabasePool(pool);
  return new PrismaClient({ adapter: new PrismaPg(pool) });
}

export function db(): PrismaClient {
  if (!globalForPrisma.prisma) {
    globalForPrisma.prisma = createClient();
  }
  return globalForPrisma.prisma;
}
