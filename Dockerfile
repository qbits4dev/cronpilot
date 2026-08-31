# ---- Build stage ----
FROM node:22-alpine AS builder

WORKDIR /app

# Build tools required to compile better-sqlite3 native bindings
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    python3 \
    python3-dev \
    py3-pip \
    sqlite-dev \
    linux-headers \
    pkgconfig \
    ca-certificates \
    curl \
    && python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && corepack enable && corepack prepare yarn@stable --activate

# Copy manifest first for layer caching
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# Copy source
COPY server/src ./server/src
COPY client/src ./client/src
COPY client/index.html ./client/
COPY vite.config.js ./

RUN yarn build

# Create external dir (no external fetch)
RUN mkdir -p /external

# ---- Production deps stage ----
FROM node:22-alpine AS deps

WORKDIR /app

# Build tools required to compile better-sqlite3 native bindings
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    python3 \
    python3-dev \
    py3-pip \
    sqlite-dev \
    linux-headers \
    pkgconfig \
    ca-certificates \
    && corepack enable && corepack prepare yarn@stable --activate

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --production

# ---- Production stage ----
FROM node:22-alpine

WORKDIR /app

RUN apk add --no-cache \
    curl \
    ca-certificates \
    bash \
    python3 \
    py3-pip \
    && python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && ln -sf /usr/bin/python3 /usr/bin/python

COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/client/dist ./client/dist
COPY --from=builder /external ./external
COPY server/src ./server/src
COPY scripts ./scripts
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
