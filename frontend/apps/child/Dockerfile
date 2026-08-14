# Build stage — includes vite-plugin-svg-icons-ng for SVG sprite generation
FROM node:22-alpine AS build
WORKDIR /app
# Copy shared packages first
COPY frontend/packages/auth ./frontend/packages/auth
COPY frontend/packages/math ./frontend/packages/math
COPY frontend/packages/assets ./frontend/packages/assets
# Install packages devDependencies so vue-tsc can type-check them
# Cache mount persists npm cache across builds for faster installs
WORKDIR /app/frontend/packages/auth
RUN --mount=type=cache,target=/root/.npm npm install
WORKDIR /app/frontend/packages/math
RUN --mount=type=cache,target=/root/.npm npm install
WORKDIR /app/frontend/packages/assets
RUN --mount=type=cache,target=/root/.npm npm install
# Copy and install frontend-child app
COPY frontend/apps/child/package*.json /app/frontend/apps/child/
WORKDIR /app/frontend/apps/child
RUN sed -i 's|"@numina/math": "workspace:\*"|"@numina/math": "file:../../packages/math"|g' package.json && \
    sed -i 's|"@numina/auth": "workspace:\*"|"@numina/auth": "file:../../packages/auth"|g' package.json && \
    sed -i 's|"@numina/assets": "workspace:\*"|"@numina/assets": "file:../../packages/assets"|g' package.json && \
    npm install --cache /root/.npm
COPY frontend/apps/child/ .
ARG VITE_MAIN_APP_URL=""
ENV VITE_MAIN_APP_URL=$VITE_MAIN_APP_URL
# Cache mount for vite cache speeds up incremental builds
RUN --mount=type=cache,target=/app/frontend/apps/child/node_modules/.vite \
    npx vite build

FROM nginx:1.27-alpine

LABEL org.opencontainers.image.source="https://github.com/vincentruan/numina"
COPY --from=build /app/frontend/apps/child/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html
COPY frontend/apps/child/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
