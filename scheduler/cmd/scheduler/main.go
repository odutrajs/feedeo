package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/creators-mov/scheduler/internal/api"
	"github.com/creators-mov/scheduler/internal/config"
	"github.com/creators-mov/scheduler/internal/publisher"
	"github.com/creators-mov/scheduler/internal/scheduler"
	"github.com/creators-mov/scheduler/internal/ws"
	"github.com/redis/go-redis/v9"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})))
	logger := slog.Default()

	cfg := config.Load()

	// Redis
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.RedisAddr,
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	if err := rdb.Ping(ctx).Err(); err != nil {
		logger.Error("não conseguiu conectar ao Redis", "addr", cfg.RedisAddr, "err", err)
		os.Exit(1)
	}
	cancel()
	logger.Info("conectado ao Redis", "addr", cfg.RedisAddr)

	// Componentes
	hub := ws.NewHub()
	pub := publisher.New(cfg)
	sched := scheduler.New(cfg, rdb, pub, hub)
	handler := api.NewHandler(sched, rdb, cfg)

	// Iniciar scheduler
	ctx, cancel = context.WithCancel(context.Background())
	defer cancel()

	if err := sched.Start(ctx); err != nil {
		logger.Error("falha ao iniciar scheduler", "err", err)
		os.Exit(1)
	}

	// HTTP server
	mux := http.NewServeMux()

	// API endpoints
	mux.HandleFunc("/api/schedule", handler.HandleSchedule)
	mux.HandleFunc("/api/cancel", handler.HandleCancel)
	mux.HandleFunc("/api/jobs", handler.HandleList)
	mux.HandleFunc("/health", handler.HandleHealth)

	// WebSocket
	mux.HandleFunc("/ws", hub.HandleWS)

	// CORS middleware
	corsHandler := corsMiddleware(mux)

	server := &http.Server{
		Addr:         cfg.HTTPAddr,
		Handler:      corsHandler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 120 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown
	go func() {
		logger.Info("HTTP server iniciado", "addr", cfg.HTTPAddr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("HTTP server falhou", "err", err)
			os.Exit(1)
		}
	}()

	// Espera sinal de shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("desligando...")
	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	server.Shutdown(shutdownCtx)

	logger.Info("scheduler encerrado")
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Scheduler-Secret")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}
