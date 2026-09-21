# ── CampusShield AI — Frontend ───────────────────────────────────────────────
# Build context: project root  (docker-compose sets context: .)
#
# BACKEND_URL build arg controls where nginx proxies /api/ and /ws/.
#   Local Docker Compose default: http://backend:8000  (Docker internal DNS)
#   Render production:            https://<your-backend>.onrender.com
#
# envsubst substitutes ONLY $BACKEND_URL in nginx.conf.template.
# Nginx's own variables ($host, $http_upgrade, etc.) are left untouched
# because envsubst is called with an explicit variable list '$BACKEND_URL'.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build React app ─────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

# ── Stage 2: nginx runtime ───────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Build argument — default preserves local Docker Compose behaviour exactly.
ARG BACKEND_URL=http://backend:8000

# Copy nginx config template and substitute $BACKEND_URL at build time.
# gettext-base provides envsubst; it is removed after use to keep image lean.
COPY frontend/nginx.conf /etc/nginx/conf.d/nginx.conf.template
RUN apk add --no-cache gettext \
    && envsubst '$BACKEND_URL' \
         < /etc/nginx/conf.d/nginx.conf.template \
         > /etc/nginx/conf.d/default.conf \
    && rm /etc/nginx/conf.d/nginx.conf.template \
    && apk del gettext

# Copy built React assets from Stage 1
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
