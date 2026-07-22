package models

import "time"

// ScheduledJob representa um agendamento de publicação.
type ScheduledJob struct {
	ID            string    `json:"id"`
	PublicationID int64     `json:"publication_id"`
	ProjectID     *int64    `json:"project_id,omitempty"`
	SocialPostID  *int64    `json:"social_post_id,omitempty"`
	AccountID     int64     `json:"account_id"`
	Platform      string    `json:"platform"`
	ScheduledAt   time.Time `json:"scheduled_at"`
	Status        string    `json:"status"` // pending / running / published / failed / cancelled
	Error         string    `json:"error,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
}

// JobEvent é publicado via Redis Pub/Sub quando um job é criado/cancelado.
type JobEvent struct {
	Action string       `json:"action"` // schedule / cancel / update
	Job    ScheduledJob `json:"job"`
}

// StatusEvent é publicado via Redis Pub/Sub e WebSocket quando o status muda.
type StatusEvent struct {
	PublicationID int64  `json:"publication_id"`
	Status        string `json:"status"`
	Error         string `json:"error,omitempty"`
	Timestamp     int64  `json:"timestamp"`
}

// PublishRequest enviado ao backend para executar a publicação.
type PublishRequest struct {
	PublicationID int64 `json:"publication_id"`
}

// PublishResponse retornada pelo backend.
type PublishResponse struct {
	Success    bool   `json:"success"`
	ExternalID string `json:"external_id,omitempty"`
	Error      string `json:"error,omitempty"`
}
