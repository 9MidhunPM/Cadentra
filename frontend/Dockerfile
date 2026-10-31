# Keep the verified Node baseline and lockfile; no runtime API URL is baked in.
FROM node:26.12.1-bookworm-slim@sha256:88e480776c6149ff1d098cd304f44bf18057fb5d284a3329b78162d29821e28c AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# NGINX-maintained non-root image; its PID/temp paths already use /tmp.
FROM nginx/nginx-unprivileged:1.30.6-alpine@sha256:2daef144b574804198caccc4041819fa1801ecd5df2252a39646bfa2b1ff3bea
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
