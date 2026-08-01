FROM node:20-alpine AS build
WORKDIR /app
# Copy shared packages first
COPY frontend/packages/auth ./frontend/packages/auth
COPY frontend/packages/math ./frontend/packages/math
# Install packages devDependencies so vue-tpc can type-check them
WORKDIR /app/frontend/packages/auth
RUN npm install
WORKDIR /app/frontend/packages/math
RUN npm install
# Copy and install frontend-child app
COPY frontend/apps/child/package*.json /app/frontend/apps/child/
WORKDIR /app/frontend/apps/child
RUN sed -i 's|"@numina/math": "workspace:\*"|"@numina/math": "file:../../packages/math"|g' package.json && \
    sed -i 's|"@numina/auth": "workspace:\*"|"@numina/auth": "file:../../packages/auth"|g' package.json && \
    npm install
COPY frontend/apps/child/ .
ARG VITE_MAIN_APP_URL=""
ENV VITE_MAIN_APP_URL=$VITE_MAIN_APP_URL
RUN npx vite build

FROM nginx:alpine
COPY --from=build /app/frontend/apps/child/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html && \
    sed -i 's|pid.*/run/nginx.pid;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf
COPY frontend/apps/child/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
