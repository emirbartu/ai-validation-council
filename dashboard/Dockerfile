FROM oven/bun:1-alpine

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

ENV NEXT_PUBLIC_API_URL=http://backend:8000

RUN bun run build

EXPOSE 3000
CMD ["bun", "run", "start"]
