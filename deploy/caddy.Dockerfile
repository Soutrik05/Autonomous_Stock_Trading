# Builds the React dashboard, then serves it with Caddy, which also proxies /api/* to the FastAPI container
# and gets a free HTTPS certificate automatically when SITE_ADDRESS is a real domain.
FROM node:22-alpine AS dashboard
WORKDIR /dash
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ .
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=dashboard /dash/dist /srv
