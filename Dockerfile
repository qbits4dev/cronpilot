# ---- Build stage ----
FROM node:22-slim AS builder

WORKDIR /app

# Build tools required to compile better-sqlite3 native bindings
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ git \
    && rm -rf /var/lib/apt/lists/*

# Copy manifest first for layer caching
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# Copy source
COPY server/src ./server/src
COPY client/src ./client/src
COPY client/index.html ./client/
COPY vite.config.js ./

RUN yarn build

# ---- Production deps stage ----
FROM node:22-slim AS deps

WORKDIR /app

# Build tools required to compile better-sqlite3 native bindings
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ git \
    && rm -rf /var/lib/apt/lists/*

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --production

# ---- Production stage ----
FROM node:22-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/client/dist ./client/dist
COPY server/src ./server/src
COPY package.json ./

RUN mkdir -p /data

ENV NODE_ENV=production \
    PORT=80 \
    HOST=0.0.0.0 \
    DB_PATH=/data/cronpilot.db

EXPOSE 80
VOLUME /data

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

CMD ["node", "server/src/index.js"]
