import { PrismaPg } from "@prisma/adapter-pg";

import { PrismaClient } from "@/generated/prisma/client";
import { env } from "@/lib/env";

/**
 * Prisma Client (Prisma 7, Driver Adapter "pg").
 * Im Dev-Modus wird die Instanz über Hot-Reloads hinweg wiederverwendet.
 */
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

function createClient(): PrismaClient {
  const connectionString = env().DATABASE_URL;
  if (!connectionString) throw new Error("DATABASE_URL ist nicht gesetzt.");
  const adapter = new PrismaPg({ connectionString, max: 10 });
  return new PrismaClient({ adapter });
}

export function db(): PrismaClient {
  if (!globalForPrisma.prisma) {
    globalForPrisma.prisma = createClient();
  }
  return globalForPrisma.prisma;
}
