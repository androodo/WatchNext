package recommendation

import "testing"

func TestFilterRemovesDuplicatesAndDislikes(t *testing.T) {
	items := []RankedItem{
		{ItemID: "1"},
		{ItemID: "1"},
		{ItemID: "2"},
		{ItemID: "3"},
	}
	out := Filter(items, map[string]struct{}{"2": {}})
	if len(out) != 2 || out[0].ItemID != "1" || out[1].ItemID != "3" {
		t.Fatalf("got %+v", out)
	}
}

func TestFilterByGenreKeepsMatchingTitles(t *testing.T) {
	items := []RankedItem{
		{ItemID: "1", Categories: []string{"comedy"}},
		{ItemID: "2", Categories: []string{"sci_fi", "action"}},
	}
	out := FilterByGenre(items, "Sci-Fi")
	if len(out) != 1 || out[0].ItemID != "2" {
		t.Fatalf("got %+v", out)
	}
}

func TestExcludeSetDropsLikedAndSkipped(t *testing.T) {
	items := []RankedItem{
		{ItemID: "liked"},
		{ItemID: "skip"},
		{ItemID: "fresh"},
	}
	feats := &UserFeatures{
		LikedItems:    []string{"liked"},
		DislikedItems: []string{"skip"},
	}
	out := Filter(items, ExcludeSet(feats))
	if len(out) != 1 || out[0].ItemID != "fresh" {
		t.Fatalf("got %+v", out)
	}
}

func TestAffinityOverlayPrefersMatchingCategory(t *testing.T) {
	items := []RankedItem{
		{ItemID: "comedy", RankerScore: 0.50, Categories: []string{"comedy"}},
		{ItemID: "scifi", RankerScore: 0.51, Categories: []string{"sci_fi"}},
	}
	feats := &UserFeatures{Affinities: map[string]float64{"sci_fi": 0.8, "comedy": 0.1}}
	out := ApplyAffinityOverlay(items, feats, 0.35)
	if out[0].ItemID != "scifi" {
		t.Fatalf("expected sci-fi first after overlay, got %+v", out)
	}
}
