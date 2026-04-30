FROM node:20-alpine AS build
WORKDIR /app
# Install packages/auth devDependencies so vue-tsc can type-check it
COPY frontend/packages/auth ./frontend/packages/auth
WORKDIR /app/frontend/packages/auth
RUN npm install
# Copy and install frontend-child app
COPY frontend/apps/child/package*.json /app/frontend/apps/child/
WORKDIR /app/frontend/apps/child
RUN sed -i 's|"workspace:\*"|"file:../../packages/auth"|g' package.json && npm install
COPY frontend/apps/child/ .
RUN npx vite build

FROM nginx:alpine
COPY --from=build /app/frontend/apps/child/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html
COPY frontend/apps/child/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
