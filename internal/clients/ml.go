package clients

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"watchnext/internal/recommendation"
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
	UserID     string             `json:"user_id"`
	RequestID  string             `json:"request_id"`
	K          int                `json:"k"`
	Exclude    []string           `json:"exclude"`
	Genre      string             `json:"genre,omitempty"`
	Affinities map[string]float64 `json:"affinities,omitempty"`
}

type candResp struct {
	Candidates []recommendation.Candidate `json:"candidates"`
	ColdStart  bool                       `json:"cold_start"`
}

func (c *MLClient) Candidates(ctx context.Context, userID, requestID string, k int, exclude []string, genre string, affinities map[string]float64) ([]recommendation.Candidate, error) {
	body, _ := json.Marshal(candReq{UserID: userID, RequestID: requestID, K: k, Exclude: exclude, Genre: genre, Affinities: affinities})
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

func (c *MLClient) Catalog(ctx context.Context, q, genre, sort string, limit, offset, yearMin, yearMax int) (*recommendation.CatalogPage, error) {
	url := fmt.Sprintf("%s/internal/catalog?q=%s&genre=%s&sort=%s&limit=%d&offset=%d",
		c.base, queryEscape(q), queryEscape(genre), queryEscape(sort), limit, offset)
	if yearMin > 0 {
		url += fmt.Sprintf("&year_min=%d", yearMin)
	}
	if yearMax > 0 {
		url += fmt.Sprintf("&year_max=%d", yearMax)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	res, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return nil, fmt.Errorf("catalog status %d: %s", res.StatusCode, b)
	}
	var out recommendation.CatalogPage
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *MLClient) Item(ctx context.Context, itemID string) (*recommendation.CatalogItem, error) {
	endpoint := c.base + "/internal/items/" + url.PathEscape(itemID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, err
	}
	res, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return nil, fmt.Errorf("item status %d: %s", res.StatusCode, b)
	}
	var out recommendation.CatalogItem
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *MLClient) Genres(ctx context.Context) (*recommendation.GenreCatalog, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.base+"/internal/genres", nil)
	if err != nil {
		return nil, err
	}
	res, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return nil, fmt.Errorf("genres status %d: %s", res.StatusCode, b)
	}
	var out recommendation.GenreCatalog
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *MLClient) RefreshCatalog(ctx context.Context) (*recommendation.GenreCatalog, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.base+"/internal/catalog/refresh", nil)
	if err != nil {
		return nil, err
	}
	client := &http.Client{Timeout: 3 * time.Minute}
	res, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return nil, fmt.Errorf("refresh status %d: %s", res.StatusCode, b)
	}
	var out recommendation.GenreCatalog
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}

func queryEscape(s string) string {
	return strings.ReplaceAll(url.QueryEscape(s), "+", "%20")
}

func (c *MLClient) IngestEvent(ctx context.Context, payload []byte) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.base+"/internal/ingest", bytes.NewReader(payload))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	res, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		b, _ := io.ReadAll(res.Body)
		return fmt.Errorf("ingest status %d: %s", res.StatusCode, b)
	}
	return nil
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
