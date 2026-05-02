package main

import (
	"fmt"
	"strconv"
	"strings"
)

type Instr struct {
	Op  string
	Arg int
}

func Parse(toks []string) []Instr {
	labels := map[string]int{}
	pos := 0
	for _, t := range toks {
		if strings.HasSuffix(t, ":") {
			labels[strings.TrimSuffix(t, ":")] = pos
		} else {
			pos++
		}
	}

	var code []Instr
	for _, t := range toks {
		switch {
		case strings.HasSuffix(t, ":"):
			// already recorded in pass 1
		case strings.HasPrefix(t, "&"):
			name := t[1:]
			addr, ok := labels[name]
			if !ok {
				panic(fmt.Sprintf("undefined label: %s", name))
			}
			code = append(code, Instr{Op: "pushaddr", Arg: addr})
		default:
			if n, err := strconv.Atoi(t); err == nil {
				code = append(code, Instr{Op: "push", Arg: n})
			} else {
				code = append(code, Instr{Op: t})
			}
		}
	}
	return code
}
