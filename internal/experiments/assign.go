package experiments

import (
	"crypto/sha256"
	"encoding/binary"
)

const (
	VariantControl   = "control"
	VariantTreatment = "treatment"
)

// Assign maps (experimentID, userID) to a stable bucket.
// Same inputs always produce the same variant. Not process-randomized.
func Assign(experimentID, userID string) (variant string, bucket uint64) {
	sum := sha256.Sum256([]byte(experimentID + ":" + userID))
	bucket = binary.BigEndian.Uint64(sum[:8]) % 100
	if bucket < 50 {
		return VariantControl, bucket
	}
	return VariantTreatment, bucket
}

func ModelForVariant(variant string) string {
	if variant == VariantTreatment {
		return "ranker-v1"
	}
	return "als-retrieval"
}
