package features

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"

	"pulserank/internal/recommendation"
)

type Store struct {
	rdb *redis.Client
}

func NewStore(rdb *redis.Client) *Store {
	return &Store{rdb: rdb}
}

func (s *Store) GetUser(ctx context.Context, userID string) (*recommendation.UserFeatures, error) {
	raw, err := s.rdb.Get(ctx, fmt.Sprintf("user:%s:features", userID)).Bytes()
	if err == redis.Nil {
		return &recommendation.UserFeatures{Affinities: map[string]float64{}}, nil
	}
	if err != nil {
		return nil, err
	}
	var feats recommendation.UserFeatures
	if err := json.Unmarshal(raw, &feats); err != nil {
		return nil, err
	}
	if feats.Affinities == nil {
		feats.Affinities = map[string]float64{}
	}
	return &feats, nil
}

func (s *Store) FallbackCandidates(ctx context.Context, k int) []recommendation.Candidate {
	raw, err := s.rdb.Get(ctx, "fallback:popularity").Bytes()
	if err != nil {
		return nil
	}
	var ids []string
	if err := json.Unmarshal(raw, &ids); err != nil {
		return nil
	}
	if k > len(ids) {
		k = len(ids)
	}
	out := make([]recommendation.Candidate, 0, k)
	n := len(ids)
	if n == 0 {
		return nil
	}
	for i, id := range ids[:k] {
		score := float64(n-i) / float64(n)
		out = append(out, recommendation.Candidate{
			ItemID:         id,
			Source:         "popularity_fallback",
			RetrievalScore: score,
			SourceRank:     i + 1,
		})
	}
	return out
}

func (s *Store) Ping(ctx context.Context) error {
	return s.rdb.Ping(ctx).Err()
}
