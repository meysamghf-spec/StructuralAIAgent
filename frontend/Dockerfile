# syntax=docker/dockerfile:1
ARG REGISTRY=
FROM ${REGISTRY}node:20-alpine AS builder
WORKDIR /app
# Optional npm mirror (e.g. https://package-mirror.liara.ir/repository/npm/ or https://mirror-npm.runflare.com)
ARG NPM_REGISTRY=https://registry.npmjs.org/
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT=standalone
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry "$NPM_REGISTRY" && npm ci --no-audit --no-fund
COPY frontend .
RUN npm run build

FROM ${REGISTRY}node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
