package telemetry

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	Requests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "pulserank_requests_total",
		Help: "Recommendation requests",
	}, []string{"status", "fallback"})

	RequestLatency = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "pulserank_request_latency_seconds",
		Help:    "End-to-end recommendation latency",
		Buckets: prometheus.DefBuckets,
	})

	CandidateLatency = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "pulserank_candidate_latency_seconds",
		Help:    "Candidate retrieval latency",
		Buckets: prometheus.DefBuckets,
	})

	RankerLatency = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "pulserank_ranker_latency_seconds",
		Help:    "Ranker latency",
		Buckets: prometheus.DefBuckets,
	})

	FeatureLatency = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "pulserank_feature_lookup_latency_seconds",
		Help:    "Redis feature lookup latency",
		Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25},
	})

	Fallbacks = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "pulserank_fallback_total",
		Help: "Fallback responses",
	}, []string{"reason"})

	EventsPublished = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "pulserank_events_published_total",
		Help: "Events published to Redpanda",
	}, []string{"topic", "status"})

	ShadowOverlap = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "pulserank_shadow_topk_overlap",
		Help:    "Fraction of top-k items shared with shadow ranker",
		Buckets: []float64{0, 0.2, 0.4, 0.6, 0.8, 1},
	})
)
