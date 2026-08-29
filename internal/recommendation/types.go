package recommendation

import "time"

type UserFeatures struct {
	Views24h         int                `json:"views_24h"`
	Likes24h         int                `json:"likes_24h"`
	Skips24h         int                `json:"skips_24h"`
	Watches24h       int                `json:"watches_24h"`
	Views7d          int                `json:"views_7d"`
	Likes7d          int                `json:"likes_7d"`
	Skips7d          int                `json:"skips_7d"`
	Watches7d        int                `json:"watches_7d"`
	InteractionCount int                `json:"interaction_count"`
	AvgEngagement    float64            `json:"avg_engagement"`
	Affinities       map[string]float64 `json:"affinities"`
	LastActivityTS   *float64           `json:"last_activity_ts"`
	FeatureUpdatedAt *float64           `json:"feature_updated_at"`
	DislikedItems    []string           `json:"disliked_items"`
	LikedItems       []string           `json:"liked_items"`
	InteractedItems  []string           `json:"interacted_items"`
	RecentActions    []RecentAction     `json:"recent_actions"`
}

type RecentAction struct {
	EventType string  `json:"event_type"`
	ItemID    string  `json:"item_id"`
	Title     string  `json:"title,omitempty"`
	Timestamp float64 `json:"timestamp"`
}

type Candidate struct {
	ItemID         string   `json:"item_id"`
	Source         string   `json:"source"`
	RetrievalScore float64  `json:"retrieval_score"`
	SourceRank     int      `json:"source_rank"`
	Title          string   `json:"title,omitempty"`
	Categories     []string `json:"categories,omitempty"`
}

type RankedItem struct {
	ItemID         string   `json:"item_id"`
	Source         string   `json:"source"`
	RetrievalScore float64  `json:"retrieval_score"`
	SourceRank     int      `json:"source_rank"`
	RankerScore    float64  `json:"ranker_score"`
	Title          string   `json:"title,omitempty"`
	Categories     []string `json:"categories,omitempty"`
}

type Item struct {
	ItemID         string   `json:"item_id"`
	Score          float64  `json:"score"`
	Title          string   `json:"title,omitempty"`
	Categories     []string `json:"categories,omitempty"`
	Source         string   `json:"source,omitempty"`
	RetrievalScore float64  `json:"retrieval_score,omitempty"`
	RankerScore    *float64 `json:"ranker_score,omitempty"`
	SourceRank     int      `json:"source_rank,omitempty"`
}

type Result struct {
	RequestID       string        `json:"request_id"`
	UserID          string        `json:"user_id"`
	ModelVersion    string        `json:"model_version"`
	Experiment      string        `json:"experiment"`
	ExperimentID    string        `json:"experiment_id"`
	FallbackUsed    bool          `json:"fallback_used"`
	FallbackReason  string        `json:"fallback_reason,omitempty"`
	Recommendations []Item        `json:"recommendations"`
	UserFeatures    *UserFeatures `json:"user_features,omitempty"`
	Debug           []RankedItem  `json:"debug,omitempty"`
	GeneratedAt     time.Time     `json:"generated_at"`
}
