# Build stage — używamy pnpm zamiast npm dla szybszej, deterministycznej instalacji
FROM node:20-alpine AS builder

WORKDIR /app

# Włącz corepack (od node 16+) — zarządza pnpm/yarn zgodnie z polem packageManager
RUN corepack enable

# Najpierw manifest + lockfile (cache layer dla zależności)
COPY package.json pnpm-lock.yaml* ./

# --frozen-lockfile gdy lock istnieje, fallback gdy go nie ma (pierwszy build)
RUN if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; else pnpm install; fi

# Reszta kodu i build
COPY . .
RUN pnpm run build

# Production stage — nginx serwuje tylko statiki
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
