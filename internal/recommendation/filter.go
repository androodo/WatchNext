package recommendation

import (
	"sort"
	"strings"
)

func NormalizeGenre(raw string) string {
	s := strings.ToLower(strings.TrimSpace(raw))
	s = strings.ReplaceAll(s, " ", "_")
	s = strings.ReplaceAll(s, "-", "_")
	s = strings.ReplaceAll(s, "'", "")
	return s
}

func HasGenre(cats []string, genre string) bool {
	want := NormalizeGenre(genre)
	if want == "" {
		return true
	}
	for _, c := range cats {
		if NormalizeGenre(c) == want {
			return true
		}
	}
	return false
}

func FilterByGenre(items []RankedItem, genre string) []RankedItem {
	if NormalizeGenre(genre) == "" {
		return items
	}
	out := make([]RankedItem, 0, len(items))
	for _, it := range items {
		if HasGenre(it.Categories, genre) {
			out = append(out, it)
		}
	}
	return out
}

func Filter(items []RankedItem, disliked map[string]struct{}) []RankedItem {
	seen := make(map[string]struct{}, len(items))
	out := make([]RankedItem, 0, len(items))
	for _, it := range items {
		if it.ItemID == "" {
			continue
		}
		if _, ok := seen[it.ItemID]; ok {
			continue
		}
		if _, ok := disliked[it.ItemID]; ok {
			continue
		}
		seen[it.ItemID] = struct{}{}
		out = append(out, it)
	}
	return out
}

func RankedFromCandidates(cands []Candidate) []RankedItem {
	out := make([]RankedItem, 0, len(cands))
	for _, c := range cands {
		out = append(out, RankedItem{
			ItemID:         c.ItemID,
			Source:         c.Source,
			RetrievalScore: c.RetrievalScore,
			SourceRank:     c.SourceRank,
			RankerScore:    c.RetrievalScore,
			Title:          c.Title,
			Categories:     c.Categories,
			Year:           c.Year,
			Popularity:     c.Popularity,
		})
	}
	return out
}

// ApplyAffinityOverlay mixes the current online category affinities into the
// ranking score. Streaming feature updates can then move the feed without a
// model retrain. Weight is a serving choice, documented in docs/FEATURES.md.
func ApplyAffinityOverlay(items []RankedItem, feats *UserFeatures, weight float64) []RankedItem {
	if feats == nil || feats.Affinities == nil || weight == 0 || len(items) == 0 {
		return items
	}
	out := append([]RankedItem(nil), items...)
	for i := range out {
		cats := out[i].Categories
		if len(cats) == 0 {
			continue
		}
		sum := 0.0
		for _, c := range cats {
			sum += feats.Affinities[c]
		}
		out[i].RankerScore += weight * (sum / float64(len(cats)))
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].RankerScore > out[j].RankerScore })
	return out
}

func DislikedSet(feats *UserFeatures) map[string]struct{} {
	out := map[string]struct{}{}
	if feats == nil {
		return out
	}
	for _, id := range feats.DislikedItems {
		out[id] = struct{}{}
	}
	return out
}

func ExcludeSet(feats *UserFeatures) map[string]struct{} {
	out := DislikedSet(feats)
	if feats == nil {
		return out
	}
	for _, id := range feats.LikedItems {
		out[id] = struct{}{}
	}
	return out
}

func ToItems(ranked []RankedItem, limit int, useRanker bool) []Item {
	if limit <= 0 || limit > len(ranked) {
		if limit <= 0 {
			limit = 10
		}
		if limit > len(ranked) {
			limit = len(ranked)
		}
	}
	out := make([]Item, 0, limit)
	for i := 0; i < limit; i++ {
		r := ranked[i]
		item := Item{
			ItemID:         r.ItemID,
			Score:          r.RetrievalScore,
			Title:          r.Title,
			Categories:     r.Categories,
			Year:           r.Year,
			Source:         r.Source,
			RetrievalScore: r.RetrievalScore,
			SourceRank:     r.SourceRank,
			Popularity:     r.Popularity,
		}
		if useRanker {
			s := r.RankerScore
			item.RankerScore = &s
			item.Score = r.RankerScore
		}
		out = append(out, item)
	}
	return out
}
