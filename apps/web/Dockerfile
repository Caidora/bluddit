# The browser bundle is architecture independent. Build it on BuildKit's native
# platform so multi-arch image publishing doesn't run Vite under QEMU per target.
FROM --platform=$BUILDPLATFORM node:24-bookworm-slim AS development
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM development AS build
RUN npm run typecheck && npm run build

FROM nginx:stable-alpine AS production
RUN adduser -D -u 1000 app
COPY apps/web/nginx.conf /etc/nginx/web.conf
COPY --from=build /app/build/client /usr/share/nginx/html
USER app
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 CMD wget -q -O /dev/null http://127.0.0.1:3000/
ARG GIT_SHA=local
LABEL org.opencontainers.image.source="https://github.com/Caidora/bluddit" org.opencontainers.image.revision=$GIT_SHA
ENTRYPOINT ["nginx"]
CMD ["-c", "/etc/nginx/web.conf", "-g", "daemon off;"]
