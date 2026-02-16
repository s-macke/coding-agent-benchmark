package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"strconv"
	"strings"

	"disasm86/pkg/disasm86"
)

func main() {
	var (
		hexInput string
		filePath string
		segText  string
		offText  string
	)

	flag.StringVar(&hexInput, "hex", "", "hex bytes (space/comma separated)")
	flag.StringVar(&filePath, "file", "", "path to binary input")
	flag.StringVar(&segText, "seg", "0", "segment (decimal or 0x...)")
	flag.StringVar(&offText, "off", "0", "offset (decimal or 0x...)")
	flag.Parse()

	if (hexInput == "" && filePath == "") || (hexInput != "" && filePath != "") {
		exitErr("provide exactly one of -hex or -file")
	}

	seg, err := parseUint16(segText)
	if err != nil {
		exitErr("invalid -seg: " + err.Error())
	}
	off, err := parseUint16(offText)
	if err != nil {
		exitErr("invalid -off: " + err.Error())
	}

	var data []byte
	if hexInput != "" {
		data, err = parseHexBytes(hexInput)
		if err != nil {
			exitErr("invalid -hex: " + err.Error())
		}
	} else {
		data, err = os.ReadFile(filePath)
		if err != nil {
			exitErr("read file: " + err.Error())
		}
	}

	startAddr := uint32(seg)<<4 + uint32(off)
	mem := make([]byte, int(startAddr)+len(data))
	copy(mem[int(startAddr):], data)
	if len(data) == 0 {
		return
	}

	src := disasm86.SliceSource{Data: mem}
	dec := disasm86.NewDecoder()
	curr := off
	consumed := 0
	for consumed < len(data) {
		inst, next, err := dec.DecodeAt(seg, curr, src)
		if err != nil {
			exitErr(fmt.Sprintf("decode 0x%04X:0x%04X: %v", seg, curr, err))
		}
		fmt.Printf("0x%04X:0x%04X %-30s%s\n", seg, curr, encodeRaw(inst.Raw), disasm86.RenderIntel(inst))
		if inst.Length == 0 {
			exitErr(fmt.Sprintf("decode 0x%04X:0x%04X produced zero-length instruction", seg, curr))
		}
		consumed += int(inst.Length)
		curr = next
	}
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

func encodeRaw(raw []byte) string {
	if len(raw) == 0 {
		return ""
	}
	out := make([]string, 0, len(raw))
	for _, b := range raw {
		out = append(out, fmt.Sprintf("0x%02X", b))
	}
	return strings.Join(out, " ")
}

func exitErr(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}
