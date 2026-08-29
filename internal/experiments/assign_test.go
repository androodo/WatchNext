package experiments

import "testing"

func TestAssignIsDeterministic(t *testing.T) {
	a, ba := Assign("ranker-vs-retrieval", "42")
	b, bb := Assign("ranker-vs-retrieval", "42")
	if a != b || ba != bb {
		t.Fatalf("expected stable assignment, got %s/%d vs %s/%d", a, ba, b, bb)
	}
}

func TestAssignSpreadsUsers(t *testing.T) {
	control, treatment := 0, 0
	for i := 0; i < 400; i++ {
		v, _ := Assign("ranker-vs-retrieval", itoa(i))
		if v == VariantControl {
			control++
		} else {
			treatment++
		}
	}
	if control < 120 || treatment < 120 {
		t.Fatalf("assignment looks skewed: control=%d treatment=%d", control, treatment)
	}
}

func TestDifferentUsersCanDiffer(t *testing.T) {
	seen := map[string]bool{}
	for i := 0; i < 50; i++ {
		v, _ := Assign("exp", itoa(i))
		seen[v] = true
	}
	if len(seen) < 2 {
		t.Fatal("expected both variants across 50 users")
	}
}

func itoa(i int) string {
	return string(rune('a'+(i%26))) + string(rune('0'+(i%10))) + string(rune(i))
}
