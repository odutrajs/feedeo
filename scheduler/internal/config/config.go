package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	// Endereço HTTP do scheduler
	HTTPAddr string

	// Redis
	RedisAddr     string
	RedisPassword string
	RedisDB       int

	// Backend API (Python FastAPI)
	BackendURL string

	// Canais Redis
	ScheduleChannel string
	StatusChannel   string

	// Tolerância: jobs com scheduled_at no passado dentro dessa janela ainda são executados
	PastTolerance time.Duration

	// Intervalo de sincronização com backend (fallback caso perca mensagem pub/sub)
	SyncInterval time.Duration
}

func Load() *Config {
	return &Config{
		HTTPAddr:        envOr("HTTP_ADDR", ":8090"),
		RedisAddr:       envOr("REDIS_ADDR", "localhost:6379"),
		RedisPassword:   envOr("REDIS_PASSWORD", ""),
		RedisDB:         envOrInt("REDIS_DB", 0),
		BackendURL:      envOr("BACKEND_URL", "http://localhost:8005"),
		ScheduleChannel: envOr("SCHEDULE_CHANNEL", "scheduler:new"),
		StatusChannel:   envOr("STATUS_CHANNEL", "scheduler:status"),
		PastTolerance:   30 * time.Minute,
		SyncInterval:    30 * time.Second,
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envOrInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		n, err := strconv.Atoi(v)
		if err == nil {
			return n
		}
	}
	return fallback
}
