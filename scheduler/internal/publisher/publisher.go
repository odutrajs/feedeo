package publisher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/creators-mov/scheduler/internal/config"
	"github.com/creators-mov/scheduler/internal/models"
)

// Publisher se comunica com o backend Python para executar publicações.
type Publisher struct {
	cfg    *config.Config
	client *http.Client
}

func New(cfg *config.Config) *Publisher {
	return &Publisher{
		cfg: cfg,
		client: &http.Client{
			Timeout: 120 * time.Second, // uploads podem demorar
		},
	}
}

// Publish chama o backend para executar a publicação de um item.
func (p *Publisher) Publish(ctx context.Context, publicationID int64) (*models.PublishResponse, error) {
	url := fmt.Sprintf("%s/api/scheduler/execute", p.cfg.BackendURL)

	body, _ := json.Marshal(models.PublishRequest{
		PublicationID: publicationID,
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("criando request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Scheduler-Secret", "internal")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("chamando backend: %w", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("backend retornou %d: %s", resp.StatusCode, string(respBody))
	}

	var result models.PublishResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("decodificando resposta: %w", err)
	}
	return &result, nil
}

// FetchPending busca jobs pendentes do backend (sync fallback).
func (p *Publisher) FetchPending(ctx context.Context) ([]models.ScheduledJob, error) {
	url := fmt.Sprintf("%s/api/scheduler/pending", p.cfg.BackendURL)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Scheduler-Secret", "internal")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("backend retornou %d", resp.StatusCode)
	}

	var jobs []models.ScheduledJob
	if err := json.NewDecoder(resp.Body).Decode(&jobs); err != nil {
		return nil, err
	}
	return jobs, nil
}
