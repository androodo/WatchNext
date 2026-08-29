package events

import (
	"context"
	"time"

	"github.com/segmentio/kafka-go"
)

type Publisher interface {
	Publish(ctx context.Context, topic string, key, value []byte) error
	Close() error
}

type KafkaPublisher struct {
	writer *kafka.Writer
}

func NewKafkaPublisher(brokers []string, timeout time.Duration) *KafkaPublisher {
	return &KafkaPublisher{
		writer: &kafka.Writer{
			Addr:         kafka.TCP(brokers...),
			Balancer:     &kafka.Hash{},
			RequiredAcks: kafka.RequireOne,
			Async:        false,
			BatchTimeout: 10 * time.Millisecond,
			WriteTimeout: timeout,
		},
	}
}

func (p *KafkaPublisher) Publish(ctx context.Context, topic string, key, value []byte) error {
	return p.writer.WriteMessages(ctx, kafka.Message{
		Topic: topic,
		Key:   key,
		Value: value,
	})
}

func (p *KafkaPublisher) Close() error {
	if p.writer == nil {
		return nil
	}
	return p.writer.Close()
}

type BufferPublisher struct {
	Messages []kafka.Message
	Err      error
}

func (p *BufferPublisher) Publish(ctx context.Context, topic string, key, value []byte) error {
	if p.Err != nil {
		return p.Err
	}
	p.Messages = append(p.Messages, kafka.Message{Topic: topic, Key: key, Value: value})
	return nil
}

func (p *BufferPublisher) Close() error { return nil }
