package main

import (
	"errors"
	"reflect"
	"strings"
	"testing"
)

func TestParseConfigHex(t *testing.T) {
	cfg, err := parseConfig([]string{"-hex", "B8 34 12", "-seg", "0x20", "-off", "0x10"}, func(string) ([]byte, error) {
		return nil, errors.New("should not read file")
	})
	if err != nil {
		t.Fatalf("parseConfig() error = %v", err)
	}
	if cfg.seg != 0x20 || cfg.off != 0x10 {
		t.Fatalf("unexpected seg/off: %+v", cfg)
	}
	want := []byte{0xB8, 0x34, 0x12}
	if !reflect.DeepEqual(cfg.data, want) {
		t.Fatalf("unexpected data: got %v want %v", cfg.data, want)
	}
}

func TestParseConfigFile(t *testing.T) {
	cfg, err := parseConfig([]string{"-file", "prog.bin"}, func(path string) ([]byte, error) {
		if path != "prog.bin" {
			t.Fatalf("unexpected file path: %q", path)
		}
		return []byte{0x90}, nil
	})
	if err != nil {
		t.Fatalf("parseConfig() error = %v", err)
	}
	if len(cfg.data) != 1 || cfg.data[0] != 0x90 {
		t.Fatalf("unexpected data: %v", cfg.data)
	}
}

func TestParseConfigRejectsMissingInput(t *testing.T) {
	_, err := parseConfig(nil, func(string) ([]byte, error) { return nil, nil })
	if err == nil || !strings.Contains(err.Error(), "exactly one of -hex or -file") {
		t.Fatalf("unexpected error: %v", err)
	}
}
