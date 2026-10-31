FROM node:24-bookworm-slim AS development
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM development AS build
RUN npm run typecheck && npm run build

FROM node:24-bookworm-slim AS production
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/build ./build
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
ARG GIT_SHA=local
LABEL org.opencontainers.image.source="https://github.com/Caidora/bluddit" org.opencontainers.image.revision=$GIT_SHA
CMD ["npm", "run", "start"]
