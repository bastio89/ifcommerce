# syntax=docker/dockerfile:1.7
# =============================================================================
# DecideCommerce Frontend (Next.js) – Multi-Stage-Build
# Build-Kontext ist das Repo-Root, weil das Prisma-Schema unter /prisma liegt.
#   deps     : npm ci + prisma generate
#   builder  : next build (standalone output)
#   migrator : einmaliger Job "prisma migrate deploy" (docker compose: service "migrate")
#   runner   : minimales Runtime-Image, Non-Root
# =============================================================================
ARG NODE_VERSION=22-alpine

FROM node:${NODE_VERSION} AS base
ENV NEXT_TELEMETRY_DISABLED=1
# Gleiche Verzeichnisstruktur wie im Repo, damit ../prisma aus prisma.config.ts auflöst.
WORKDIR /repo/frontend

FROM base AS deps
COPY prisma /repo/prisma
COPY frontend/package.json frontend/package-lock.json frontend/prisma.config.ts ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

FROM deps AS builder
ENV NEXT_OUTPUT_STANDALONE=1
COPY frontend/ ./
RUN npm run build

FROM deps AS migrator
CMD ["npx", "prisma", "migrate", "deploy"]

FROM node:${NODE_VERSION} AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs
COPY --from=builder --chown=nextjs:nodejs /repo/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/frontend/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /repo/frontend/public ./public
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1
CMD ["node", "server.js"]
