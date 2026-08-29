package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	"pulserank/internal/api"
	"pulserank/internal/clients"
	"pulserank/internal/config"
	"pulserank/internal/events"
	"pulserank/internal/features"
	"pulserank/internal/recommendation"
	"pulserank/internal/telemetry"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(log)
	cfg := config.Load()

	opt, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		log.Error("redis url", "err", err)
		os.Exit(1)
	}
	rdb := redis.NewClient(opt)
	store := features.NewStore(rdb)
	ml := clients.NewMLClient(cfg.MLBaseURL, 3*time.Second)
	pub := events.NewKafkaPublisher(cfg.KafkaBrokers, cfg.KafkaTimeout)
	defer pub.Close()

	orch := recommendation.NewOrchestrator(cfg, store, ml, ml, pub, telemetry.Logger("recommendation-api"))
	orch.FallbackCandidates = store.FallbackCandidates
	srv := api.NewServer(cfg, orch, log)
	srv.Ready = func(ctx context.Context) error {
		// Process is ready to serve degraded results even if Redis is down.
		// Ready means the HTTP server can accept traffic.
		return nil
	}

	httpSrv := &http.Server{
		Addr:              cfg.Addr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Info("listening", "addr", cfg.Addr)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("http", "err", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = httpSrv.Shutdown(ctx)
	_ = rdb.Close()
}
