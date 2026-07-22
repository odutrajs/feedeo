package scheduler

import (
	"container/heap"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/creators-mov/scheduler/internal/config"
	"github.com/creators-mov/scheduler/internal/models"
	"github.com/creators-mov/scheduler/internal/publisher"
	"github.com/creators-mov/scheduler/internal/ws"
	"github.com/redis/go-redis/v9"
)

// Scheduler é o core do serviço: mantém uma priority queue de jobs
// e dispara publicações no horário exato sem polling.
type Scheduler struct {
	cfg    *config.Config
	rdb    *redis.Client
	pub    *publisher.Publisher
	hub    *ws.Hub
	logger *slog.Logger

	mu   sync.Mutex
	pq   *priorityQueue
	jobs map[string]*models.ScheduledJob // id -> job
	wake chan struct{}                   // acordar o runLoop quando a fila muda
	stop chan struct{}
}

func New(cfg *config.Config, rdb *redis.Client, pub *publisher.Publisher, hub *ws.Hub) *Scheduler {
	return &Scheduler{
		cfg:    cfg,
		rdb:    rdb,
		pub:    pub,
		hub:    hub,
		logger: slog.Default().With("component", "scheduler"),
		pq:     newPQ(),
		jobs:   make(map[string]*models.ScheduledJob),
		wake:   make(chan struct{}, 1),
		stop:   make(chan struct{}),
	}
}

// Start inicia o scheduler: carrega jobs pendentes do Redis, escuta Pub/Sub e agenda timers.
func (s *Scheduler) Start(ctx context.Context) error {
	if err := s.loadPending(ctx); err != nil {
		s.logger.Warn("falha ao carregar jobs pendentes", "err", err)
	}

	// Sync imediato com o backend (pega jobs criados enquanto o scheduler estava off)
	s.syncWithBackend(ctx)

	go s.listenPubSub(ctx)
	go s.syncLoop(ctx)
	go s.runLoop(ctx)

	s.logger.Info("scheduler iniciado", "jobs_carregados", len(s.jobs))
	return nil
}

// Schedule adiciona ou atualiza um job.
func (s *Scheduler) Schedule(job *models.ScheduledJob) {
	s.mu.Lock()
	s.jobs[job.ID] = job
	heap.Push(s.pq, &entry{id: job.ID, scheduledAt: job.ScheduledAt})
	s.mu.Unlock()
	s.notify()

	s.logger.Info("job agendado",
		"id", job.ID,
		"publication_id", job.PublicationID,
		"scheduled_at", job.ScheduledAt.Format(time.RFC3339),
	)
}

// Cancel remove um job do agendamento.
func (s *Scheduler) Cancel(jobID string) {
	s.mu.Lock()
	if job, ok := s.jobs[jobID]; ok {
		job.Status = "cancelled"
		delete(s.jobs, jobID)
		s.logger.Info("job cancelado", "id", jobID)
	}
	s.mu.Unlock()
	s.notify()
}

// GetJob retorna o estado de um job.
func (s *Scheduler) GetJob(jobID string) (*models.ScheduledJob, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	job, ok := s.jobs[jobID]
	return job, ok
}

// ListPending retorna todos os jobs pendentes.
func (s *Scheduler) ListPending() []*models.ScheduledJob {
	s.mu.Lock()
	defer s.mu.Unlock()

	result := make([]*models.ScheduledJob, 0, len(s.jobs))
	for _, job := range s.jobs {
		if job.Status == "pending" {
			result = append(result, job)
		}
	}
	return result
}

// notify acorda o runLoop para recalcular o próximo timer.
func (s *Scheduler) notify() {
	select {
	case s.wake <- struct{}{}:
	default:
	}
}

// nextDelay retorna quanto esperar até o próximo job (ou um sleep longo se a fila estiver vazia).
func (s *Scheduler) nextDelay() time.Duration {
	s.mu.Lock()
	defer s.mu.Unlock()

	for {
		next := s.pq.Peek()
		if next == nil {
			return time.Hour
		}
		// Descarta entradas órfãs (canceladas / já processadas)
		job, ok := s.jobs[next.id]
		if !ok || job.Status != "pending" {
			heap.Pop(s.pq)
			continue
		}
		delay := time.Until(next.scheduledAt)
		if delay < 0 {
			return 0
		}
		return delay
	}
}

// runLoop espera o horário do próximo job (ou um wake) e dispara processDue.
func (s *Scheduler) runLoop(ctx context.Context) {
	for {
		delay := s.nextDelay()
		timer := time.NewTimer(delay)

		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-s.wake:
			timer.Stop()
			continue
		case <-timer.C:
			s.processDue(ctx)
		}
	}
}

// processDue executa todos os jobs cujo horário já chegou.
func (s *Scheduler) processDue(ctx context.Context) {
	now := time.Now().UTC()

	for {
		s.mu.Lock()
		next := s.pq.Peek()
		if next == nil || next.scheduledAt.After(now) {
			s.mu.Unlock()
			return
		}

		// Pop o item do heap
		heap.Pop(s.pq)

		job, exists := s.jobs[next.id]
		if !exists || job.Status != "pending" {
			s.mu.Unlock()
			continue
		}

		// Verifica tolerância: se está muito no passado, marca como failed
		if now.Sub(job.ScheduledAt) > s.cfg.PastTolerance {
			job.Status = "failed"
			job.Error = "horário perdido (tolerância excedida)"
			delete(s.jobs, job.ID)
			s.mu.Unlock()
			s.emitStatus(ctx, job)
			continue
		}

		job.Status = "running"
		s.mu.Unlock()

		s.emitStatus(ctx, job)

		// Executa publicação em goroutine dedicada
		go s.executeJob(ctx, job)
	}
}

// executeJob chama o backend para realizar a publicação.
func (s *Scheduler) executeJob(ctx context.Context, job *models.ScheduledJob) {
	s.logger.Info("executando publicação",
		"id", job.ID,
		"publication_id", job.PublicationID,
	)

	result, err := s.pub.Publish(ctx, job.PublicationID)
	s.mu.Lock()
	if err != nil {
		job.Status = "failed"
		job.Error = err.Error()
	} else if !result.Success {
		job.Status = "failed"
		job.Error = result.Error
	} else {
		job.Status = "published"
	}
	delete(s.jobs, job.ID)
	s.mu.Unlock()

	s.emitStatus(ctx, job)

	s.logger.Info("publicação concluída",
		"id", job.ID,
		"status", job.Status,
		"error", job.Error,
	)
}

// emitStatus publica mudança de status via Redis e WebSocket.
func (s *Scheduler) emitStatus(ctx context.Context, job *models.ScheduledJob) {
	evt := models.StatusEvent{
		PublicationID: job.PublicationID,
		Status:        job.Status,
		Error:         job.Error,
		Timestamp:     time.Now().Unix(),
	}

	// WebSocket broadcast
	s.hub.Broadcast(evt)

	// Redis pub/sub para outros consumidores
	data, _ := json.Marshal(evt)
	s.rdb.Publish(ctx, s.cfg.StatusChannel, string(data))
}

// listenPubSub escuta novos agendamentos vindos do backend.
func (s *Scheduler) listenPubSub(ctx context.Context) {
	sub := s.rdb.Subscribe(ctx, s.cfg.ScheduleChannel)
	defer sub.Close()

	ch := sub.Channel()
	for {
		select {
		case <-ctx.Done():
			return
		case msg, ok := <-ch:
			if !ok {
				return
			}
			s.handleEvent(msg.Payload)
		}
	}
}

func (s *Scheduler) handleEvent(payload string) {
	var evt models.JobEvent
	if err := json.Unmarshal([]byte(payload), &evt); err != nil {
		s.logger.Error("evento inválido", "err", err, "payload", payload)
		return
	}

	switch evt.Action {
	case "schedule":
		s.Schedule(&evt.Job)
		s.persistJob(context.Background(), &evt.Job)
	case "cancel":
		s.Cancel(evt.Job.ID)
		s.removePersistedJob(context.Background(), evt.Job.ID)
	case "update":
		s.Cancel(evt.Job.ID)
		s.Schedule(&evt.Job)
		s.persistJob(context.Background(), &evt.Job)
	}
}

// persistJob salva o job no Redis sorted set para recuperação após restart.
func (s *Scheduler) persistJob(ctx context.Context, job *models.ScheduledJob) {
	data, _ := json.Marshal(job)
	s.rdb.ZAdd(ctx, "scheduler:jobs", redis.Z{
		Score:  float64(job.ScheduledAt.Unix()),
		Member: string(data),
	})
}

func (s *Scheduler) removePersistedJob(ctx context.Context, jobID string) {
	// Remove por scan — não é ideal mas jobs são poucos
	members, _ := s.rdb.ZRange(ctx, "scheduler:jobs", 0, -1).Result()
	for _, m := range members {
		var job models.ScheduledJob
		if json.Unmarshal([]byte(m), &job) == nil && job.ID == jobID {
			s.rdb.ZRem(ctx, "scheduler:jobs", m)
			break
		}
	}
}

// loadPending carrega jobs do Redis sorted set ao iniciar.
func (s *Scheduler) loadPending(ctx context.Context) error {
	members, err := s.rdb.ZRangeByScore(ctx, "scheduler:jobs", &redis.ZRangeBy{
		Min: "-inf",
		Max: "+inf",
	}).Result()
	if err != nil {
		return fmt.Errorf("redis zrangebyscore: %w", err)
	}

	now := time.Now().UTC()
	for _, m := range members {
		var job models.ScheduledJob
		if err := json.Unmarshal([]byte(m), &job); err != nil {
			continue
		}
		// Ignora jobs muito antigos
		if now.Sub(job.ScheduledAt) > s.cfg.PastTolerance {
			s.rdb.ZRem(ctx, "scheduler:jobs", m)
			continue
		}
		if job.Status == "pending" {
			s.Schedule(&job)
		}
	}
	return nil
}

// syncLoop faz sync periódico com o backend como fallback (caso perca msg pub/sub).
func (s *Scheduler) syncLoop(ctx context.Context) {
	ticker := time.NewTicker(s.cfg.SyncInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.syncWithBackend(ctx)
		}
	}
}

func (s *Scheduler) syncWithBackend(ctx context.Context) {
	jobs, err := s.pub.FetchPending(ctx)
	if err != nil {
		s.logger.Warn("sync com backend falhou", "err", err)
		return
	}

	added := 0
	s.mu.Lock()
	for _, job := range jobs {
		if _, exists := s.jobs[job.ID]; !exists {
			j := job // cópia local
			s.jobs[j.ID] = &j
			heap.Push(s.pq, &entry{id: j.ID, scheduledAt: j.ScheduledAt})
			added++
		}
	}
	s.mu.Unlock()

	if added > 0 {
		s.notify()
		s.logger.Info("sync concluído", "novos_jobs", added)
	}
}
