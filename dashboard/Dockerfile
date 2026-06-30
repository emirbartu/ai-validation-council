# syntax=docker/dockerfile:1.7
# Council dashboard (Next.js + Bun).
#
# Single-stage: project isn't configured for `output: standalone` so we keep
# the full image and rely on Bun's lightweight alpine base.
#
# Build:  DOCKER_BUILDKIT=1 docker build -t council-dashboard .
# Override API:  docker build --build-arg NEXT_PUBLIC_API_URL=http://api.example.com .

ARG BUN_VERSION=1.3.14

FROM oven/bun:${BUN_VERSION}-alpine

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -S -g 1001 appuser && adduser -S -u 1001 -G appuser appuser

COPY --chown=appuser:appuser package.json bun.lock* ./
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile || bun install

COPY --chown=appuser:appuser . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN bun run build

USER appuser
EXPOSE 3000

CMD ["bun", "run", "start"]
