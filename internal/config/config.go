package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Addr              string
	RedisURL          string
	KafkaBrokers      []string
	MLBaseURL         string
	InteractionsTopic string
	ImpressionsTopic  string
	DLQTopic          string
	ExperimentID      string
	ShadowEnabled     bool
	RedisTimeout      time.Duration
	CandidateTimeout  time.Duration
	RankerTimeout     time.Duration
	KafkaTimeout      time.Duration
	RequestTimeout    time.Duration
	InlineFeatures    bool
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func Load() Config {
	ms := func(key string, def int) time.Duration {
		raw := getenv(key, strconv.Itoa(def))
		n, err := strconv.Atoi(raw)
		if err != nil {
			n = def
		}
		return time.Duration(n) * time.Millisecond
	}
	addr := getenv("HTTP_ADDR", "")
	if addr == "" {
		addr = ":" + getenv("PORT", "8080")
	}
	brokers := strings.Split(getenv("KAFKA_BROKERS", "localhost:19092"), ",")
	return Config{
		Addr:              addr,
		RedisURL:          getenv("REDIS_URL", "redis://localhost:6379/0"),
		KafkaBrokers:      brokers,
		MLBaseURL:         getenv("ML_BASE_URL", "http://localhost:8090"),
		InteractionsTopic: getenv("INTERACTIONS_TOPIC", "events.interactions"),
		ImpressionsTopic:  getenv("IMPRESSIONS_TOPIC", "events.impressions"),
		DLQTopic:          getenv("DLQ_TOPIC", "events.dead-letter"),
		ExperimentID:      getenv("EXPERIMENT_ID", "ranker-vs-retrieval"),
		ShadowEnabled:     getenv("SHADOW_ENABLED", "false") == "true",
		RedisTimeout:      ms("REDIS_TIMEOUT_MS", 80),
		CandidateTimeout:  ms("CANDIDATE_TIMEOUT_MS", 800),
		RankerTimeout:     ms("RANKER_TIMEOUT_MS", 1500),
		KafkaTimeout:      ms("KAFKA_TIMEOUT_MS", 400),
		RequestTimeout:    ms("REQUEST_TIMEOUT_MS", 2500),
		InlineFeatures:    getenv("INLINE_FEATURES", "false") == "true",
	}
}
