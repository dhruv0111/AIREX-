# AIREX Web — Next.js (spec §46, AT-022) — monorepo-aware build.
# The build context is the REPOSITORY ROOT so npm workspaces (@airex/api-client,
# @airex/shared-types, @airex/config) resolve exactly as they do locally.
FROM node:20-alpine AS base
WORKDIR /app

# ---- deps: install the whole workspace (root manifests + lockfile + packages) ----
FROM base AS deps
COPY package.json package-lock.json* ./
COPY packages ./packages
COPY apps/web/package.json ./apps/web/package.json
RUN npm install --no-audit --no-fund

# ---- builder: compile the Next.js app with NEXT_PUBLIC_* baked in ----
FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package-lock.json ./package-lock.json
COPY . .
RUN npm run build -w apps/web

# ---- runner: standalone server (self-contained) ----
# When built via `npm run build -w apps/web`, Next.js 15 emits the standalone
# output with the app's monorepo path preserved (server.js at apps/web/server.js),
# so static/public are placed relative to that location.
FROM base AS runner
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
