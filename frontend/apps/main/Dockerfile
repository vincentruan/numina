# syntax=docker/dockerfile:1
# Build stage — includes vite-plugin-svg-icons-ng for SVG sprite generation
FROM node:22-alpine AS build
WORKDIR /app
# Copy shared packages first
COPY frontend/packages/auth ./frontend/packages/auth
COPY frontend/packages/math ./frontend/packages/math
COPY frontend/packages/assets ./frontend/packages/assets
# Install packages devDependencies so vue-tsc can type-check them
WORKDIR /app/frontend/packages/auth
RUN npm install
WORKDIR /app/frontend/packages/math
RUN npm install
WORKDIR /app/frontend/packages/assets
RUN npm install
# Copy and install frontend app
COPY frontend/apps/main/package*.json /app/frontend/apps/main/
WORKDIR /app/frontend/apps/main
# Cache bust: unique value per build prevents stale npm install layers
ARG CACHE_BUST=default
RUN sed -i 's|"@numina/math": "workspace:\*"|"@numina/math": "file:../../packages/math"|g' package.json && \
    sed -i 's|"@numina/auth": "workspace:\*"|"@numina/auth": "file:../../packages/auth"|g' package.json && \
    sed -i 's|"@numina/assets": "workspace:\*"|"@numina/assets": "file:../../packages/assets"|g' package.json && \
    npm install
# Generate 256×256 WebP thumbnails BEFORE copying full app source.
# This layer only re-runs when packages/assets icons or the script change —
# not when app code changes. BuildKit cache mount further speeds up the case
# where icons do change by persisting previously generated thumbnails.
COPY frontend/apps/main/scripts/generate-icon-thumbnails.ts ./scripts/
RUN mkdir -p public/icons/3d && \
    for cat in animals art-culture buildings clothing-accessories electronics \
               entertainment furniture healthcare instruments kitchenware \
               office-stationery plants science-tech sports tools vehicles; do \
      ln -sf /app/frontend/packages/assets/src/icons/3d-things/$cat public/icons/3d/$cat; \
    done
# Generate thumbnails with BuildKit cache mount — persists across builds so
# the script's stat() check can skip already-generated files. The generated
# files are copied into public/ within the same RUN (cache mount is ephemeral).
RUN --mount=type=cache,target=/tmp/icon-thumbs \
    THUMB_OUTPUT_DIR=/tmp/icon-thumbs npx tsx scripts/generate-icon-thumbnails.ts && \
    cp -r /tmp/icon-thumbs public/icons/3d-thumbs
# Copy full app source (3d-thumbs excluded via .dockerignore to preserve cache)
COPY frontend/apps/main/ .
RUN npx vite build

FROM nginx:1.27-alpine

LABEL org.opencontainers.image.source="https://github.com/vincentruan/numina"
COPY --from=build /app/frontend/apps/main/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html
COPY frontend/apps/main/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
