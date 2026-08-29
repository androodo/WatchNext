package events

import (
	"testing"
	"time"
)

func TestValidateRejectsUnknownType(t *testing.T) {
	err := Validate(Event{
		EventID: "1", SchemaVersion: 1, UserID: "u", ItemID: "i",
		EventType: "explode", Timestamp: time.Now().UTC(),
	})
	if err == nil {
		t.Fatal("expected error")
	}
}

func TestValidateOK(t *testing.T) {
	err := Validate(Event{
		EventID: "1", SchemaVersion: 1, UserID: "u", ItemID: "i",
		EventType: "like", Timestamp: time.Now().UTC(),
	})
	if err != nil {
		t.Fatal(err)
	}
}
