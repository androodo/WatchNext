package api

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"watchnext/internal/config"
	"watchnext/internal/events"
	"watchnext/internal/recommendation"
)

type stubStore struct{}

func (stubStore) GetUser(ctx context.Context, userID string) (*recommendation.UserFeatures, error) {
	return &recommendation.UserFeatures{Affinities: map[string]float64{"sci_fi": 0.2}}, nil
}

type stubCands struct{}

func (stubCands) Candidates(ctx context.Context, userID, requestID string, k int, exclude []string) ([]recommendation.Candidate, error) {
	return []recommendation.Candidate{{ItemID: "1", RetrievalScore: 0.5, Source: "popularity"}}, nil
}

type stubRanker struct{}

func (stubRanker) Rank(ctx context.Context, userID, requestID string, cands []recommendation.Candidate, feats *recommendation.UserFeatures) ([]recommendation.RankedItem, string, error) {
	return []recommendation.RankedItem{{ItemID: "1", RankerScore: 0.9, RetrievalScore: 0.5}}, "ranker-v1", nil
}

func testServer(pub events.Publisher) *Server {
	cfg := config.Config{
		RequestTimeout:    time.Second,
		RedisTimeout:      50 * time.Millisecond,
		CandidateTimeout:  50 * time.Millisecond,
		RankerTimeout:     50 * time.Millisecond,
		KafkaTimeout:      50 * time.Millisecond,
		ExperimentID:      "ranker-vs-retrieval",
		InteractionsTopic: "events.interactions",
		ImpressionsTopic:  "events.impressions",
	}
	orch := recommendation.NewOrchestrator(cfg, stubStore{}, stubCands{}, stubRanker{}, pub, slog.Default())
	return NewServer(cfg, orch, slog.Default())
}

func TestHealthAndReady(t *testing.T) {
	s := testServer(&events.BufferPublisher{})
	h := s.Handler()
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/health", nil))
	if rr.Code != 200 {
		t.Fatalf("health %d", rr.Code)
	}
	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/ready", nil))
	if rr.Code != 200 {
		t.Fatalf("ready %d", rr.Code)
	}
}

func TestRecommendationsShape(t *testing.T) {
	s := testServer(&events.BufferPublisher{})
	rr := httptest.NewRecorder()
	s.Handler().ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/v1/recommendations/42?limit=5", nil))
	if rr.Code != 200 {
		t.Fatalf("status %d body %s", rr.Code, rr.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"request_id", "user_id", "model_version", "experiment", "fallback_used", "recommendations"} {
		if _, ok := body[key]; !ok {
			t.Fatalf("missing %s", key)
		}
	}
}

func TestEventPublishFailureIsNotSuccess(t *testing.T) {
	s := testServer(&events.BufferPublisher{Err: context.DeadlineExceeded})
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/events", strings.NewReader(`{
		"event_id":"e1","schema_version":1,"user_id":"42","item_id":"1","event_type":"like","timestamp":"2024-01-01T00:00:00Z"
	}`))
	s.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d %s", rr.Code, rr.Body.String())
	}
}

func TestEventValidation(t *testing.T) {
	s := testServer(&events.BufferPublisher{})
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/events", strings.NewReader(`{"event_id":"e1","user_id":"42"}`))
	s.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rr.Code)
	}
}
