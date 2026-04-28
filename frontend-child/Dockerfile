FROM node:20-alpine AS build
WORKDIR /app
# Install packages/auth devDependencies so vue-tsc can type-check it
COPY packages/auth ./packages/auth
WORKDIR /app/packages/auth
RUN npm install
# Copy and install frontend-child app
COPY frontend-child/package*.json /app/frontend-child/
WORKDIR /app/frontend-child
RUN sed -i 's|"workspace:\*"|"file:../packages/auth"|g' package.json && npm install
COPY frontend-child/ .
RUN npx vite build

FROM nginx:alpine
COPY --from=build /app/frontend-child/dist /usr/share/nginx/html
RUN chmod -R a+rX /usr/share/nginx/html
COPY frontend-child/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
