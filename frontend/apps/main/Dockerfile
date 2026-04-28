FROM node:20-alpine AS build
WORKDIR /app
# Install packages/auth devDependencies so vue-tsc can type-check it
COPY frontend/packages/auth ./frontend/packages/auth
WORKDIR /app/frontend/packages/auth
RUN npm install
# Copy and install frontend app
COPY frontend/apps/main/package*.json /app/frontend/apps/main/
WORKDIR /app/frontend/apps/main
RUN sed -i 's|"workspace:\*"|"file:../../packages/auth"|g' package.json && npm install
COPY frontend/apps/main/ .
RUN npx vite build

FROM nginx:alpine
COPY --from=build /app/frontend/apps/main/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html
COPY frontend/apps/main/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
