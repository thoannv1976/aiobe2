FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app ./
# Cloud Run cấp cổng qua $PORT (mặc định 8080); next start đọc -p.
EXPOSE 8080
CMD ["sh", "-c", "npm run start -- -p ${PORT:-3000}"]
