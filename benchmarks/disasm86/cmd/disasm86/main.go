package main

import (
	"disasm86/pkg/disasm86"
	"fmt"
	"os"
)

func main() {
	cfg, err := parseConfig(os.Args[1:], os.ReadFile)
	if err != nil {
		exitErr(err.Error())
	}
	if len(cfg.data) == 0 {
		return
	}

	startAddr := uint32(cfg.seg)<<4 + uint32(cfg.off)
	mem := make([]byte, int(startAddr)+len(cfg.data))
	copy(mem[int(startAddr):], cfg.data)

	src := disasm86.SliceSource{Data: mem}
	dec := disasm86.NewDecoder()
	curr := cfg.off
	consumed := 0
	for consumed < len(cfg.data) {
		inst, next, err := dec.DecodeAt(cfg.seg, curr, src)
		if err != nil {
			exitErr(fmt.Sprintf("decode 0x%04X:0x%04X: %v", cfg.seg, curr, err))
		}
		fmt.Printf("0x%04X:0x%04X %s\n", cfg.seg, curr, inst)
		if inst.Length == 0 {
			exitErr(fmt.Sprintf("decode 0x%04X:0x%04X produced zero-length instruction", cfg.seg, curr))
		}
		consumed += int(inst.Length)
		curr = next
	}
}

func exitErr(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}
