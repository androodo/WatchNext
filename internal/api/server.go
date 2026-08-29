package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"

	"pulserank/internal/config"
	"pulserank/internal/events"
	"pulserank/internal/recommendation"
)

type Server struct {
	Cfg    config.Config
	Orch   *recommendation.Orchestrator
	Log    *slog.Logger
	Ready  func(context.Context) error
	Health func() error
}

func NewServer(cfg config.Config, orch *recommendation.Orchestrator, log *slog.Logger) *Server {
	return &Server{Cfg: cfg, Orch: orch, Log: log}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.health)
	mux.HandleFunc("GET /ready", s.ready)
	mux.Handle("GET /metrics", promhttp.Handler())
	mux.HandleFunc("GET /v1/recommendations/{user_id}", s.recommend)
	mux.HandleFunc("GET /v1/recommendations/{user_id}/debug", s.debug)
	mux.HandleFunc("GET /v1/users/{user_id}/features", s.features)
	mux.HandleFunc("POST /v1/events", s.postEvent)
	mux.HandleFunc("OPTIONS /v1/", s.cors)
	mux.HandleFunc("OPTIONS /v1/events", s.cors)
	mux.HandleFunc("OPTIONS /health", s.cors)
	return withRequestID(corsAll(mux))
}

func corsAll(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Request-Id")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *Server) cors(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusNoContent)
}

func withRequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Request-Id")
		if id == "" {
			id = r.URL.Query().Get("request_id")
		}
		w.Header().Set("X-Request-Id", id)
		next.ServeHTTP(w, r)
	})
}

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) ready(w http.ResponseWriter, r *http.Request) {
	if s.Ready != nil {
		ctx, cancel := context.WithTimeout(r.Context(), 300*time.Millisecond)
		defer cancel()
		if err := s.Ready(ctx); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "not_ready", "error": err.Error()})
			return
		}
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) recommend(w http.ResponseWriter, r *http.Request) {
	s.serveRec(w, r, false)
}

func (s *Server) debug(w http.ResponseWriter, r *http.Request) {
	s.serveRec(w, r, true)
}

func (s *Server) serveRec(w http.ResponseWriter, r *http.Request, debug bool) {
	userID := r.PathValue("user_id")
	if userID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "user_id required"})
		return
	}
	limit := 10
	if raw := r.URL.Query().Get("limit"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			limit = n
		}
	}
	ctx, cancel := context.WithTimeout(r.Context(), s.Cfg.RequestTimeout)
	defer cancel()
	res, err := s.Orch.Recommend(ctx, userID, limit, debug)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, res)
}

func (s *Server) features(w http.ResponseWriter, r *http.Request) {
	userID := r.PathValue("user_id")
	ctx, cancel := context.WithTimeout(r.Context(), s.Cfg.RedisTimeout)
	defer cancel()
	feats, err := s.Orch.Store.GetUser(ctx, userID)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "redis_unavailable"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"user_id": userID, "features": feats})
}

type eventBody struct {
	EventID       string         `json:"event_id"`
	SchemaVersion int            `json:"schema_version"`
	UserID        string         `json:"user_id"`
	ItemID        string         `json:"item_id"`
	EventType     string         `json:"event_type"`
	Timestamp     time.Time      `json:"timestamp"`
	Value         *float64       `json:"value"`
	RequestID     string         `json:"request_id"`
	Metadata      map[string]any `json:"metadata"`
}

func (s *Server) postEvent(w http.ResponseWriter, r *http.Request) {
	var body eventBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}
	if body.EventID == "" {
		b := make([]byte, 16)
		_, _ = rand.Read(b)
		body.EventID = hex.EncodeToString(b)
	}
	if body.SchemaVersion == 0 {
		body.SchemaVersion = events.SchemaVersion
	}
	if body.Timestamp.IsZero() {
		body.Timestamp = time.Now().UTC()
	}
	ev := events.Event{
		EventID:       body.EventID,
		SchemaVersion: body.SchemaVersion,
		UserID:        body.UserID,
		ItemID:        body.ItemID,
		EventType:     body.EventType,
		Timestamp:     body.Timestamp,
		Value:         body.Value,
		RequestID:     body.RequestID,
		Metadata:      body.Metadata,
	}
	if err := events.Validate(ev); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), s.Cfg.KafkaTimeout)
	defer cancel()
	if err := s.Orch.PublishEvent(ctx, ev); err != nil {
		s.Log.Error("event_publish_failed", "event_id", ev.EventID, "error_type", "kafka")
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "event_publish_failed"})
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]string{"status": "accepted", "event_id": ev.EventID})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func ReadyRedis(ping func(context.Context) error) func(context.Context) error {
	return func(ctx context.Context) error {
		if ping == nil {
			return errors.New("no redis")
		}
		return ping(ctx)
	}
}
