package recommendation

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log/slog"
	"sort"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"

	"watchnext/internal/config"
	"watchnext/internal/events"
	"watchnext/internal/experiments"
	"watchnext/internal/telemetry"
)

type CandidateSource interface {
	Candidates(ctx context.Context, userID, requestID string, k int, exclude []string) ([]Candidate, error)
}

type Ranker interface {
	Rank(ctx context.Context, userID, requestID string, cands []Candidate, feats *UserFeatures) ([]RankedItem, string, error)
}

type UserStore interface {
	GetUser(ctx context.Context, userID string) (*UserFeatures, error)
}

type Orchestrator struct {
	Cfg                config.Config
	Store              UserStore
	Cands              CandidateSource
	Ranker             Ranker
	Pub                events.Publisher
	Log                *slog.Logger
	Now                func() time.Time
	IDGen              func() string
	FallbackCandidates func(ctx context.Context, k int) []Candidate
}

func NewOrchestrator(cfg config.Config, store UserStore, cands CandidateSource, ranker Ranker, pub events.Publisher, log *slog.Logger) *Orchestrator {
	return &Orchestrator{
		Cfg:    cfg,
		Store:  store,
		Cands:  cands,
		Ranker: ranker,
		Pub:    pub,
		Log:    log,
		Now:    func() time.Time { return time.Now().UTC() },
		IDGen:  newRequestID,
	}
}

func newRequestID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func (o *Orchestrator) Recommend(ctx context.Context, userID string, limit int, debug bool) (*Result, error) {
	if limit <= 0 {
		limit = 10
	}
	if limit > 50 {
		limit = 50
	}
	start := time.Now()
	requestID := o.IDGen()
	ctx, span := telemetry.Tracer().Start(ctx, "recommendation.request",
		trace.WithAttributes(
			attribute.String("request_id", requestID),
			attribute.String("user_id", userID),
		),
	)
	defer span.End()

	variant, _ := experiments.Assign(o.Cfg.ExperimentID, userID)
	model := experiments.ModelForVariant(variant)
	result := &Result{
		RequestID:    requestID,
		UserID:       userID,
		ModelVersion: model,
		Experiment:   variant,
		ExperimentID: o.Cfg.ExperimentID,
		GeneratedAt:  o.Now(),
	}

	feats, featErr := o.lookupFeatures(ctx, userID)
	if featErr != nil {
		o.fallback(result, "redis_unavailable")
		feats = &UserFeatures{Affinities: map[string]float64{}}
	}
	result.UserFeatures = feats

	cands, candErr := o.lookupCandidates(ctx, userID, requestID, feats)
	if candErr != nil || len(cands) == 0 {
		o.fallback(result, "candidate_service_unavailable")
		if o.FallbackCandidates != nil {
			cands = o.FallbackCandidates(ctx, 100)
		} else {
			cands = []Candidate{}
		}
	}

	useRanker := variant == experiments.VariantTreatment && !result.FallbackUsed
	ranked := RankedFromCandidates(cands)
	if useRanker && o.Ranker != nil && len(cands) > 0 {
		rctx, cancel := context.WithTimeout(ctx, o.Cfg.RankerTimeout)
		t0 := time.Now()
		_, rspan := telemetry.Tracer().Start(rctx, "rank.predict")
		got, version, err := o.Ranker.Rank(rctx, userID, requestID, cands, feats)
		rspan.End()
		cancel()
		telemetry.RankerLatency.Observe(time.Since(t0).Seconds())
		if err != nil {
			o.fallback(result, "ranker_unavailable")
			useRanker = false
		} else {
			ranked = got
			if version != "" {
				result.ModelVersion = version
			}
		}
	} else if variant == experiments.VariantControl {
		sort.SliceStable(ranked, func(i, j int) bool {
			return ranked[i].RetrievalScore > ranked[j].RetrievalScore
		})
		result.ModelVersion = experiments.ModelForVariant(experiments.VariantControl)
	}

	if o.Cfg.ShadowEnabled && o.Ranker != nil && variant == experiments.VariantControl && len(cands) > 0 {
		go o.shadow(context.WithoutCancel(ctx), userID, requestID, cands, feats, ranked, limit)
	}

	ranked = ApplyAffinityOverlay(ranked, feats, 0.35)

	_, fspan := telemetry.Tracer().Start(ctx, "filter")
	filtered := Filter(ranked, DislikedSet(feats))
	fspan.End()

	result.Recommendations = ToItems(filtered, limit, useRanker && !result.FallbackUsed)
	if debug {
		result.Debug = filtered
	}
	span.SetAttributes(
		attribute.String("model_version", result.ModelVersion),
		attribute.String("experiment", result.Experiment),
		attribute.Bool("fallback_used", result.FallbackUsed),
		attribute.Int("candidate_count", len(cands)),
	)
	o.publishImpression(ctx, result)
	telemetry.RequestLatency.Observe(time.Since(start).Seconds())
	status := "ok"
	fb := "false"
	if result.FallbackUsed {
		fb = "true"
	}
	telemetry.Requests.WithLabelValues(status, fb).Inc()
	o.Log.Info("recommendation",
		"request_id", requestID,
		"user_id", userID,
		"model_version", result.ModelVersion,
		"experiment", result.Experiment,
		"fallback", result.FallbackUsed,
		"latency_ms", time.Since(start).Milliseconds(),
		"n", len(result.Recommendations),
	)
	return result, nil
}

func (o *Orchestrator) lookupFeatures(ctx context.Context, userID string) (*UserFeatures, error) {
	fctx, cancel := context.WithTimeout(ctx, o.Cfg.RedisTimeout)
	defer cancel()
	t0 := time.Now()
	_, span := telemetry.Tracer().Start(fctx, "feature.lookup")
	defer span.End()
	feats, err := o.Store.GetUser(fctx, userID)
	telemetry.FeatureLatency.Observe(time.Since(t0).Seconds())
	return feats, err
}

func (o *Orchestrator) lookupCandidates(ctx context.Context, userID, requestID string, feats *UserFeatures) ([]Candidate, error) {
	cctx, cancel := context.WithTimeout(ctx, o.Cfg.CandidateTimeout)
	defer cancel()
	t0 := time.Now()
	_, span := telemetry.Tracer().Start(cctx, "candidate.retrieve")
	defer span.End()
	exclude := []string{}
	if feats != nil {
		exclude = append(exclude, feats.DislikedItems...)
	}
	cands, err := o.Cands.Candidates(cctx, userID, requestID, 100, exclude)
	telemetry.CandidateLatency.Observe(time.Since(t0).Seconds())
	return cands, err
}

func (o *Orchestrator) fallback(result *Result, reason string) {
	result.FallbackUsed = true
	result.FallbackReason = reason
	telemetry.Fallbacks.WithLabelValues(reason).Inc()
}

func (o *Orchestrator) publishImpression(ctx context.Context, result *Result) {
	if o.Pub == nil {
		return
	}
	items := make([]events.ImpressionItem, 0, len(result.Recommendations))
	for i, rec := range result.Recommendations {
		items = append(items, events.ImpressionItem{ItemID: rec.ItemID, Position: i + 1, Score: rec.Score})
	}
	imp := events.Impression{
		RequestID:    result.RequestID,
		UserID:       result.UserID,
		ModelVersion: result.ModelVersion,
		Experiment:   result.Experiment,
		Items:        items,
		Timestamp:    o.Now(),
	}
	payload, err := json.Marshal(imp)
	if err != nil {
		return
	}
	go func() {
		pctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), o.Cfg.KafkaTimeout)
		defer cancel()
		_, span := telemetry.Tracer().Start(pctx, "impression.publish")
		defer span.End()
		err := o.Pub.Publish(pctx, o.Cfg.ImpressionsTopic, []byte(result.UserID), payload)
		if err != nil {
			telemetry.EventsPublished.WithLabelValues(o.Cfg.ImpressionsTopic, "error").Inc()
			o.Log.Error("impression_publish_failed", "request_id", result.RequestID, "error_type", "kafka")
			return
		}
		telemetry.EventsPublished.WithLabelValues(o.Cfg.ImpressionsTopic, "ok").Inc()
	}()
}

func (o *Orchestrator) shadow(ctx context.Context, userID, requestID string, cands []Candidate, feats *UserFeatures, prod []RankedItem, k int) {
	sctx, cancel := context.WithTimeout(ctx, o.Cfg.RankerTimeout)
	defer cancel()
	got, _, err := o.Ranker.Rank(sctx, userID, requestID, cands, feats)
	if err != nil {
		return
	}
	prodSet := map[string]struct{}{}
	limit := k
	if limit > len(prod) {
		limit = len(prod)
	}
	for i := 0; i < limit; i++ {
		prodSet[prod[i].ItemID] = struct{}{}
	}
	overlap := 0
	n := k
	if n > len(got) {
		n = len(got)
	}
	for i := 0; i < n; i++ {
		if _, ok := prodSet[got[i].ItemID]; ok {
			overlap++
		}
	}
	if k > 0 {
		telemetry.ShadowOverlap.Observe(float64(overlap) / float64(k))
	}
}

func (o *Orchestrator) PublishEvent(ctx context.Context, ev events.Event) error {
	payload, err := events.Marshal(ev)
	if err != nil {
		return err
	}
	pctx, cancel := context.WithTimeout(ctx, o.Cfg.KafkaTimeout)
	defer cancel()
	err = o.Pub.Publish(pctx, o.Cfg.InteractionsTopic, []byte(ev.UserID), payload)
	if err != nil {
		telemetry.EventsPublished.WithLabelValues(o.Cfg.InteractionsTopic, "error").Inc()
		return err
	}
	telemetry.EventsPublished.WithLabelValues(o.Cfg.InteractionsTopic, "ok").Inc()
	return nil
}
