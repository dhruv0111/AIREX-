# AIREX Web — Next.js production image (spec §46, §62; AT-022; Phase 12).
FROM node:20-alpine AS base
WORKDIR /app

# ---- deps: install the whole workspace ----
FROM base AS deps
COPY package.json package-lock.json* ./
COPY packages ./packages
COPY apps/web/package.json ./apps/web/package.json
RUN npm install --no-audit --no-fund

# ---- builder: compile the Next.js app ----
FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package-lock.json ./package-lock.json
COPY . .
RUN npm run build -w apps/web

# ---- runner: standalone server (non-root hardened) ----
FROM base AS runner
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000

RUN addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 nextjs

COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -q -O - http://localhost:3000/ || exit 1

CMD ["node", "apps/web/server.js"]
