package recommendation

import (
	"context"
	"errors"
	"log/slog"
	"testing"
	"time"

	"watchnext/internal/config"
	"watchnext/internal/events"
	"watchnext/internal/experiments"
)

type memStore struct {
	feats *UserFeatures
	err   error
}

func (m memStore) GetUser(ctx context.Context, userID string) (*UserFeatures, error) {
	return m.feats, m.err
}

type memCands struct {
	cands []Candidate
	err   error
}

func (m memCands) Candidates(ctx context.Context, userID, requestID string, k int, exclude []string, genre string, affinities map[string]float64) ([]Candidate, error) {
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	return m.cands, m.err
}

type memRanker struct {
	items []RankedItem
	err   error
	calls int
}

func (m *memRanker) Rank(ctx context.Context, userID, requestID string, cands []Candidate, feats *UserFeatures) ([]RankedItem, string, error) {
	m.calls++
	if m.err != nil {
		return nil, "", m.err
	}
	return m.items, "ranker-v1", nil
}

func testCfg() config.Config {
	return config.Config{
		ExperimentID:      "ranker-vs-retrieval",
		RedisTimeout:      50 * time.Millisecond,
		CandidateTimeout:  50 * time.Millisecond,
		RankerTimeout:     50 * time.Millisecond,
		KafkaTimeout:      50 * time.Millisecond,
		ImpressionsTopic:  "events.impressions",
		InteractionsTopic: "events.interactions",
	}
}

func TestRecommendTreatmentUsesRanker(t *testing.T) {
	// Find a user that hashes into treatment.
	var user string
	for i := 0; i < 500; i++ {
		u := string(rune('A'+(i%26))) + string(rune('0'+i%10)) + string(rune(i%7+'a'))
		v, _ := experiments.Assign("ranker-vs-retrieval", u)
		if v == experiments.VariantTreatment {
			user = u
			break
		}
	}
	if user == "" {
		t.Fatal("no treatment user")
	}
	ranker := &memRanker{items: []RankedItem{{ItemID: "sci", RankerScore: 0.99, RetrievalScore: 0.1, Source: "als"}}}
	pub := &events.BufferPublisher{}
	orch := NewOrchestrator(testCfg(), memStore{feats: &UserFeatures{}}, memCands{cands: []Candidate{{ItemID: "sci", RetrievalScore: 0.1}}}, ranker, pub, slog.Default())
	orch.IDGen = func() string { return "req-1" }
	res, err := orch.Recommend(context.Background(), user, 10, false, "")
	if err != nil {
		t.Fatal(err)
	}
	if res.FallbackUsed {
		t.Fatalf("unexpected fallback: %+v", res)
	}
	if ranker.calls != 1 {
		t.Fatalf("ranker calls %d", ranker.calls)
	}
	if res.Recommendations[0].ItemID != "sci" {
		t.Fatalf("got %+v", res.Recommendations)
	}
}

func TestRankerFailureFallsBack(t *testing.T) {
	var user string
	for i := 0; i < 500; i++ {
		u := string(rune('Z'-(i%26))) + string(rune('0'+i%10))
		v, _ := experiments.Assign("ranker-vs-retrieval", u)
		if v == experiments.VariantTreatment {
			user = u
			break
		}
	}
	ranker := &memRanker{err: errors.New("down")}
	orch := NewOrchestrator(testCfg(), memStore{feats: &UserFeatures{}}, memCands{cands: []Candidate{{ItemID: "p", RetrievalScore: 0.7, Source: "popularity"}}}, ranker, &events.BufferPublisher{}, slog.Default())
	res, err := orch.Recommend(context.Background(), user, 5, false, "")
	if err != nil {
		t.Fatal(err)
	}
	if !res.FallbackUsed || res.FallbackReason != "ranker_unavailable" {
		t.Fatalf("expected ranker fallback, got %+v", res)
	}
	if len(res.Recommendations) != 1 || res.Recommendations[0].ItemID != "p" {
		t.Fatalf("expected retrieval-ordered item, got %+v", res.Recommendations)
	}
}

func TestRedisFailureStillServes(t *testing.T) {
	orch := NewOrchestrator(testCfg(), memStore{err: errors.New("redis")}, memCands{cands: []Candidate{{ItemID: "pop", RetrievalScore: 1}}}, &memRanker{items: []RankedItem{{ItemID: "pop", RankerScore: 1}}}, &events.BufferPublisher{}, slog.Default())
	res, err := orch.Recommend(context.Background(), "cold-user-x", 3, false, "")
	if err != nil {
		t.Fatal(err)
	}
	if !res.FallbackUsed || res.FallbackReason != "redis_unavailable" {
		t.Fatalf("got %+v", res)
	}
}

func TestCandidateFailureUsesPopularityFallback(t *testing.T) {
	orch := NewOrchestrator(testCfg(), memStore{feats: &UserFeatures{}}, memCands{err: errors.New("ml down")}, &memRanker{}, &events.BufferPublisher{}, slog.Default())
	orch.FallbackCandidates = func(ctx context.Context, k int) []Candidate {
		return []Candidate{{ItemID: "cached-pop", RetrievalScore: 1, Source: "popularity_fallback"}}
	}
	res, err := orch.Recommend(context.Background(), "u1", 10, false, "")
	if err != nil {
		t.Fatal(err)
	}
	if !res.FallbackUsed || res.FallbackReason != "candidate_service_unavailable" {
		t.Fatalf("got %+v", res)
	}
	if len(res.Recommendations) != 1 || res.Recommendations[0].ItemID != "cached-pop" {
		t.Fatalf("expected cached popularity, got %+v", res.Recommendations)
	}
}

func TestContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	slow := memCands{cands: []Candidate{{ItemID: "1"}}}
	orch := NewOrchestrator(testCfg(), memStore{feats: &UserFeatures{}}, slow, &memRanker{}, &events.BufferPublisher{}, slog.Default())
	// Store/cands see a derived timeout context, not the already-canceled parent
	// after WithTimeout. Explicit canceled ctx on Recommend should still complete
	// via fallbacks rather than hang.
	res, err := orch.Recommend(ctx, "u", 10, false, "")
	if err != nil {
		t.Fatal(err)
	}
	if res == nil {
		t.Fatal("expected degraded result")
	}
}
