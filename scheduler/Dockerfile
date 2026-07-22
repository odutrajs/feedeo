# ============================================
# Multi-stage build para imagem mínima (~15MB)
# ============================================

# --- Build stage ---
FROM golang:1.23-alpine AS builder

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

# Copiar código e resolver dependências
COPY . .
RUN go mod tidy && go mod download

# Build (usa TARGETARCH do BuildKit para multi-arch)
ARG TARGETARCH
RUN CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} go build \
    -ldflags="-s -w" \
    -o /scheduler \
    ./cmd/scheduler

# --- Runtime stage ---
FROM scratch

# Certificados TLS e timezone data
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# Binário
COPY --from=builder /scheduler /scheduler

# Porta padrão
EXPOSE 8090

ENTRYPOINT ["/scheduler"]
