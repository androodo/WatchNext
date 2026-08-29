package events

import (
	"encoding/json"
	"fmt"
	"time"
)

const SchemaVersion = 1

var allowedTypes = map[string]struct{}{
	"impression": {},
	"view":       {},
	"like":       {},
	"skip":       {},
	"watch":      {},
	"dislike":    {},
	"rating":     {},
}

type Event struct {
	EventID       string         `json:"event_id"`
	SchemaVersion int            `json:"schema_version"`
	UserID        string         `json:"user_id"`
	ItemID        string         `json:"item_id"`
	EventType     string         `json:"event_type"`
	Timestamp     time.Time      `json:"timestamp"`
	Value         *float64       `json:"value,omitempty"`
	RequestID     string         `json:"request_id,omitempty"`
	Metadata      map[string]any `json:"metadata,omitempty"`
}

func Validate(e Event) error {
	if e.EventID == "" || e.UserID == "" || e.ItemID == "" {
		return fmt.Errorf("event_id, user_id, and item_id are required")
	}
	if e.SchemaVersion != SchemaVersion {
		return fmt.Errorf("unsupported schema_version %d", e.SchemaVersion)
	}
	if _, ok := allowedTypes[e.EventType]; !ok {
		return fmt.Errorf("unsupported event_type %q", e.EventType)
	}
	if e.Timestamp.IsZero() {
		return fmt.Errorf("timestamp is required")
	}
	return nil
}

func Marshal(e Event) ([]byte, error) {
	if err := Validate(e); err != nil {
		return nil, err
	}
	return json.Marshal(e)
}

type ImpressionItem struct {
	ItemID   string  `json:"item_id"`
	Position int     `json:"position"`
	Score    float64 `json:"score"`
}

type Impression struct {
	RequestID    string           `json:"request_id"`
	UserID       string           `json:"user_id"`
	ModelVersion string           `json:"model_version"`
	Experiment   string           `json:"experiment"`
	Items        []ImpressionItem `json:"items"`
	Timestamp    time.Time        `json:"timestamp"`
}
