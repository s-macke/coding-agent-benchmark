package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"strconv"
	"strings"
)

type cliConfig struct {
	seg  uint16
	off  uint16
	data []byte
}

func parseConfig(args []string, readFile func(string) ([]byte, error)) (cliConfig, error) {
	fs := flag.NewFlagSet("disasm86", flag.ContinueOnError)
	fs.SetOutput(io.Discard)

	var (
		hexInput string
		filePath string
		segText  string
		offText  string
	)

	fs.StringVar(&hexInput, "hex", "", "hex bytes (space/comma separated)")
	fs.StringVar(&filePath, "file", "", "path to binary input")
	fs.StringVar(&segText, "seg", "0x1000", "segment (decimal or 0x...)")
	fs.StringVar(&offText, "off", "0x100", "offset (decimal or 0x...)")

	if err := fs.Parse(args); err != nil {
		return cliConfig{}, err
	}
	if (hexInput == "" && filePath == "") || (hexInput != "" && filePath != "") {
		return cliConfig{}, errors.New("provide exactly one of -hex or -file")
	}

	seg, err := parseUint16(segText)
	if err != nil {
		return cliConfig{}, fmt.Errorf("invalid -seg: %w", err)
	}
	off, err := parseUint16(offText)
	if err != nil {
		return cliConfig{}, fmt.Errorf("invalid -off: %w", err)
	}

	var data []byte
	if hexInput != "" {
		data, err = parseHexBytes(hexInput)
		if err != nil {
			return cliConfig{}, fmt.Errorf("invalid -hex: %w", err)
		}
	} else {
		data, err = readFile(filePath)
		if err != nil {
			return cliConfig{}, fmt.Errorf("read file: %w", err)
		}
	}

	return cliConfig{
		seg:  seg,
		off:  off,
		data: data,
	}, nil
}

func parseUint16(v string) (uint16, error) {
	n, err := strconv.ParseUint(strings.TrimSpace(v), 0, 16)
	if err != nil {
		return 0, err
	}
	return uint16(n), nil
}

func parseHexBytes(input string) ([]byte, error) {
	tokens := strings.FieldsFunc(input, func(r rune) bool {
		switch r {
		case ' ', '\t', '\n', '\r', ',':
			return true
		default:
			return false
		}
	})
	if len(tokens) == 0 {
		return nil, errors.New("no bytes provided")
	}
	out := make([]byte, 0, len(tokens))
	for _, tok := range tokens {
		base := 16
		if strings.HasPrefix(tok, "0x") || strings.HasPrefix(tok, "0X") {
			base = 0
		}
		n, err := strconv.ParseUint(tok, base, 8)
		if err != nil {
			return nil, fmt.Errorf("token %q: %w", tok, err)
		}
		out = append(out, byte(n))
	}
	return out, nil
}
