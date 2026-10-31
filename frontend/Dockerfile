FROM node:22-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend .
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
RUN npm run build
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S momentum && adduser -S momentum -G momentum
COPY --from=builder --chown=momentum:momentum /app/.next/standalone ./
COPY --from=builder --chown=momentum:momentum /app/.next/static ./.next/static
COPY --from=builder --chown=momentum:momentum /app/public ./public
USER momentum
EXPOSE 3000
CMD ["node", "server.js"]
