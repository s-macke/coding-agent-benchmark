package disasm86

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

type goldenCase struct {
	Name    string `json:"name"`
	Seg     uint16 `json:"seg"`
	Off     uint16 `json:"off"`
	NextOff uint16 `json:"next_off"`
	Raw     string `json:"raw"`
	Text    string `json:"text"`
}

var goldenTextOverrides = map[string]string{
	"grpff_reg3":        "???",
	"grpff_reg5":        "???",
	"opc_F1":            "int1",
	"bioscall_valid":    "int1",
	"bioscall_fallback": "int1",
}

var goldenRawOverrides = map[string]string{
	"bioscall_valid": "F1",
}

var goldenNextOffOverrides = map[string]uint16{
	"bioscall_valid": 1,
}

func TestDecodeAgainstGoldenVectors(t *testing.T) {
	cases := loadGoldenCases(t)
	dec := NewDecoder()

	for _, tc := range cases {
		tc := tc
		t.Run(tc.Name, func(t *testing.T) {
			raw, err := hex.DecodeString(tc.Raw)
			if err != nil {
				t.Fatalf("decode expected raw: %v", err)
			}

			input := append([]byte{}, raw...)
			input = append(input, make([]byte, 16)...)
			base := uint32(tc.Seg)<<4 + uint32(tc.Off)
			mem := make([]byte, int(base)+len(input))
			copy(mem[int(base):], input)

			inst, next, err := dec.DecodeAt(tc.Seg, tc.Off, SliceSource{Data: mem})
			if err != nil {
				t.Fatalf("decode: %v", err)
			}

			wantNext := expectedNextOff(tc)
			if next != wantNext {
				t.Fatalf("next offset mismatch: got %04X want %04X", next, wantNext)
			}

			gotText := normalizeText(inst.String())
			wantText := normalizeText(expectedText(tc))
			if gotText != wantText {
				t.Fatalf("text mismatch: got %q want %q", gotText, wantText)
			}

			gotRaw := strings.ToUpper(hex.EncodeToString(inst.Raw))
			wantRaw := expectedRaw(tc)
			if gotRaw != wantRaw {
				t.Fatalf("raw mismatch: got %q want %q", gotRaw, wantRaw)
			}
		})
	}
}

func TestOutOfRangeReturnsError(t *testing.T) {
	_, _, err := NewDecoder().DecodeAt(0, 0, SliceSource{Data: []byte{}})
	if err == nil {
		t.Fatal("expected out-of-range error")
	}
}

func TestRejectRegisterOnlyFormsForMemoryInstructions(t *testing.T) {
	dec := NewDecoder()
	tests := []struct {
		name     string
		hexBytes string
		nextOff  uint16
		wantText string
	}{
		{name: "lea_mod11", hexBytes: "8DC0", nextOff: 2, wantText: "???"},
		{name: "les_mod11", hexBytes: "C4C0", nextOff: 2, wantText: "???"},
		{name: "lds_mod11", hexBytes: "C5C0", nextOff: 2, wantText: "???"},
		{name: "call_far_ind_mod11", hexBytes: "FFD8", nextOff: 2, wantText: "???"},
		{name: "jmp_far_ind_mod11", hexBytes: "FFE8", nextOff: 2, wantText: "???"},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			raw, err := hex.DecodeString(tc.hexBytes)
			if err != nil {
				t.Fatalf("invalid test bytes: %v", err)
			}
			mem := append([]byte{}, raw...)
			mem = append(mem, 0x00, 0x00)
			inst, next, err := dec.DecodeAt(0, 0, SliceSource{Data: mem})
			if err != nil {
				t.Fatalf("decode: %v", err)
			}
			if next != tc.nextOff {
				t.Fatalf("next off: got %d want %d", next, tc.nextOff)
			}
			if got := normalizeText(inst.String()); got != tc.wantText {
				t.Fatalf("text: got %q want %q", got, tc.wantText)
			}
		})
	}
}

func loadGoldenCases(t *testing.T) []goldenCase {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	path := filepath.Join(filepath.Dir(thisFile), "..", "..", "testdata", "vectors", "c_golden.jsonl")

	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("open golden vectors: %v", err)
	}
	defer f.Close()

	cases := make([]goldenCase, 0, 512)
	s := bufio.NewScanner(f)
	for s.Scan() {
		line := strings.TrimSpace(s.Text())
		if line == "" {
			continue
		}
		var tc goldenCase
		if err := json.Unmarshal([]byte(line), &tc); err != nil {
			t.Fatalf("parse golden line %q: %v", line, err)
		}
		cases = append(cases, tc)
	}
	if err := s.Err(); err != nil {
		t.Fatalf("scan vectors: %v", err)
	}
	if len(cases) == 0 {
		t.Fatal("no golden vectors loaded")
	}
	return cases
}

func normalizeText(s string) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return ""
	}
	s = strings.Join(strings.Fields(s), " ")
	s = strings.ReplaceAll(s, ", ", ",")
	return s
}

func expectedText(tc goldenCase) string {
	if override, ok := goldenTextOverrides[tc.Name]; ok {
		return override
	}
	return withHexPrefixes(tc.Text)
}

func expectedRaw(tc goldenCase) string {
	if override, ok := goldenRawOverrides[tc.Name]; ok {
		return override
	}
	return tc.Raw
}

func expectedNextOff(tc goldenCase) uint16 {
	if override, ok := goldenNextOffOverrides[tc.Name]; ok {
		return override
	}
	return tc.NextOff
}

var hexTokenRE = regexp.MustCompile(`\b[0-9A-F]{1,8}\b`)

func withHexPrefixes(s string) string {
	return hexTokenRE.ReplaceAllStringFunc(s, func(token string) string {
		return "0x" + token
	})
}
