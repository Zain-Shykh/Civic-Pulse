# syntax=docker/dockerfile:1

FROM node:22-alpine AS builder
WORKDIR /build

# Deps copied and installed before source, so this layer only invalidates
# when package.json/package-lock.json change, not on every source edit.
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine AS runtime

# nginx:alpine already runs its master process as root but worker
# processes as the unprivileged "nginx" user by default; we still pin
# ownership of the served files to that user explicitly.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# Made correct by construction rather than assumed: the base image's
# built-in "nginx" user needs write access to these paths to run as
# master (not just worker) with no root step in between. Set explicitly
# here, while still root, instead of trusting the base image's own
# defaults for a non-standard (fully non-root) startup.
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--spider", "http://127.0.0.1:8080/"]

CMD ["nginx", "-g", "daemon off;"]
