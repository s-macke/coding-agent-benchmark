package main

import (
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestParseHexBytes(t *testing.T) {
	got, err := parseHexBytes("B8,34 12")
	if err != nil {
		t.Fatalf("parseHexBytes() error = %v", err)
	}
	if len(got) != 3 || got[0] != 0xB8 || got[1] != 0x34 || got[2] != 0x12 {
		t.Fatalf("unexpected bytes: %v", got)
	}
}

func TestCLIOutput(t *testing.T) {
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	root := filepath.Join(filepath.Dir(thisFile), "..", "..")

	cmd := exec.Command("go", "run", "./cmd/disasm86", "-hex", "B8 34 12")
	cmd.Dir = root
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run failed: %v\n%s", err, string(out))
	}
	if !strings.Contains(string(out), "mov ax,0x1234") {
		t.Fatalf("unexpected output: %s", string(out))
	}
}

func TestCLIContinuesUntilEndOfBuffer(t *testing.T) {
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	root := filepath.Join(filepath.Dir(thisFile), "..", "..")

	cmd := exec.Command("go", "run", "./cmd/disasm86", "-hex", "B8 34 12 90")
	cmd.Dir = root
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run failed: %v\n%s", err, string(out))
	}

	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	if len(lines) != 2 {
		t.Fatalf("expected 2 decoded lines, got %d: %q", len(lines), string(out))
	}
	if !strings.Contains(lines[0], "mov ax,0x1234") {
		t.Fatalf("unexpected first line: %s", lines[0])
	}
	if !strings.Contains(lines[1], "nop") {
		t.Fatalf("unexpected second line: %s", lines[1])
	}
}
