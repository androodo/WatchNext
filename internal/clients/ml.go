package clients

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"pulserank/internal/recommendation"
)

type MLClient struct {
	base   string
	client *http.Client
}

func NewMLClient(base string, timeout time.Duration) *MLClient {
	return &MLClient{
		base:   base,
		client: &http.Client{Timeout: timeout},
	}
}

type candReq struct {
	UserID    string   `json:"user_id"`
	RequestID string   `json:"request_id"`
	K         int      `json:"k"`
	Exclude   []string `json:"exclude"`
}

type candResp struct {
	Candidates []recommendation.Candidate `json:"candidates"`
	ColdStart  bool                       `json:"cold_start"`
}

func (c *MLClient) Candidates(ctx context.Context, userID, requestID string, k int, exclude []string) ([]recommendation.Candidate, error) {
	body, _ := json.Marshal(candReq{UserID: userID, RequestID: requestID, K: k, Exclude: exclude})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.base+"/internal/candidates", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-Id", requestID)
	res, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return nil, fmt.Errorf("candidates status %d: %s", res.StatusCode, b)
	}
	var out candResp
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil {
		return nil, err
	}
	return out.Candidates, nil
}

type rankReq struct {
	UserID       string                       `json:"user_id"`
	RequestID    string                       `json:"request_id"`
	Candidates   []recommendation.Candidate   `json:"candidates"`
	UserFeatures *recommendation.UserFeatures `json:"user_features"`
}

type rankResp struct {
	Ranked       []recommendation.RankedItem `json:"ranked"`
	ModelVersion string                      `json:"model_version"`
}

func (c *MLClient) Rank(ctx context.Context, userID, requestID string, cands []recommendation.Candidate, feats *recommendation.UserFeatures) ([]recommendation.RankedItem, string, error) {
	body, _ := json.Marshal(rankReq{UserID: userID, RequestID: requestID, Candidates: cands, UserFeatures: feats})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.base+"/internal/rank", bytes.NewReader(body))
	if err != nil {
		return nil, "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-Id", requestID)
	res, err := c.client.Do(req)
	if err != nil {
		return nil, "", err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return nil, "", fmt.Errorf("rank status %d: %s", res.StatusCode, b)
	}
	var out rankResp
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil {
		return nil, "", err
	}
	return out.Ranked, out.ModelVersion, nil
}

func (c *MLClient) Ready(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.base+"/ready", nil)
	if err != nil {
		return err
	}
	res, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		return fmt.Errorf("ml not ready: %d", res.StatusCode)
	}
	return nil
}
