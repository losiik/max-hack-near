FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
# development — чтобы в обычном браузере был экран входа тестовыми пользователями, как при vite dev.
# import.meta.env.DEV зависит от NODE_ENV, одного --mode для этого мало
ARG VITE_BUILD_MODE=production

RUN NODE_ENV=${VITE_BUILD_MODE} npm run build -- --mode ${VITE_BUILD_MODE}

FROM nginx:1.27-alpine

COPY deploy/nginx/frontend-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
