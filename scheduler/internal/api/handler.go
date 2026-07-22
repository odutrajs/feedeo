package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/creators-mov/scheduler/internal/config"
	"github.com/creators-mov/scheduler/internal/models"
	"github.com/creators-mov/scheduler/internal/scheduler"
	"github.com/redis/go-redis/v9"
)

// Handler expõe endpoints REST para gerenciar agendamentos.
type Handler struct {
	sched *scheduler.Scheduler
	rdb   *redis.Client
	cfg   *config.Config
}

func NewHandler(sched *scheduler.Scheduler, rdb *redis.Client, cfg *config.Config) *Handler {
	return &Handler{sched: sched, rdb: rdb, cfg: cfg}
}

// ScheduleRequest é o body para agendar uma publicação.
type ScheduleRequest struct {
	PublicationID int64  `json:"publication_id"`
	ProjectID     *int64 `json:"project_id,omitempty"`
	SocialPostID  *int64 `json:"social_post_id,omitempty"`
	AccountID     int64  `json:"account_id"`
	Platform      string `json:"platform"`
	ScheduledAt   string `json:"scheduled_at"` // ISO 8601 (RFC3339)
}

// HandleSchedule agenda uma nova publicação.
func (h *Handler) HandleSchedule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "método não permitido", http.StatusMethodNotAllowed)
		return
	}

	var req ScheduleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonError(w, "body inválido", http.StatusBadRequest)
		return
	}

	scheduledAt, err := time.Parse(time.RFC3339, req.ScheduledAt)
	if err != nil {
		jsonError(w, "scheduled_at deve ser RFC3339 (ex: 2025-01-15T10:30:00Z)", http.StatusBadRequest)
		return
	}

	if scheduledAt.Before(time.Now().UTC().Add(-1 * time.Minute)) {
		jsonError(w, "scheduled_at deve ser no futuro", http.StatusBadRequest)
		return
	}

	job := &models.ScheduledJob{
		ID:            fmt.Sprintf("pub_%d_%d", req.PublicationID, time.Now().UnixNano()),
		PublicationID: req.PublicationID,
		ProjectID:     req.ProjectID,
		SocialPostID:  req.SocialPostID,
		AccountID:     req.AccountID,
		Platform:      req.Platform,
		ScheduledAt:   scheduledAt.UTC(),
		Status:        "pending",
		CreatedAt:     time.Now().UTC(),
	}

	h.sched.Schedule(job)

	// Persistir no Redis para sobreviver a restarts
	data, _ := json.Marshal(job)
	h.rdb.ZAdd(context.Background(), "scheduler:jobs", redis.Z{
		Score:  float64(job.ScheduledAt.Unix()),
		Member: string(data),
	})

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(job)
}

// HandleCancel cancela um agendamento.
func (h *Handler) HandleCancel(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "método não permitido", http.StatusMethodNotAllowed)
		return
	}

	var body struct {
		JobID string `json:"job_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.JobID == "" {
		jsonError(w, "job_id é obrigatório", http.StatusBadRequest)
		return
	}

	h.sched.Cancel(body.JobID)

	// Remover do Redis
	members, _ := h.rdb.ZRange(context.Background(), "scheduler:jobs", 0, -1).Result()
	for _, m := range members {
		var j models.ScheduledJob
		if json.Unmarshal([]byte(m), &j) == nil && j.ID == body.JobID {
			h.rdb.ZRem(context.Background(), "scheduler:jobs", m)
			break
		}
	}

	jsonOK(w, map[string]any{"ok": true, "job_id": body.JobID})
}

// HandleList retorna todos os jobs pendentes.
func (h *Handler) HandleList(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "método não permitido", http.StatusMethodNotAllowed)
		return
	}

	jobs := h.sched.ListPending()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(jobs)
}

// HandleHealth retorna status do serviço.
func (h *Handler) HandleHealth(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{
		"status":       "ok",
		"service":      "scheduler",
		"pending_jobs": len(h.sched.ListPending()),
		"timestamp":    time.Now().UTC().Format(time.RFC3339),
	})
}

func jsonError(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func jsonOK(w http.ResponseWriter, data any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}
