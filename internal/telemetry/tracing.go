package telemetry

import (
	"context"
	"log/slog"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/trace"
)

func Tracer() trace.Tracer {
	return otel.Tracer("watchnext")
}

func Logger(service string) *slog.Logger {
	return slog.Default().With("service", service)
}

func AttrRequest(ctx context.Context, requestID, userID string) []any {
	return []any{"request_id", requestID, "user_id", userID}
}
