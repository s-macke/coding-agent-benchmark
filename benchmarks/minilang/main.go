package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	asm := flag.Bool("s", false, "emit x86_64 Linux assembly to stdout instead of running")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "usage: %s [-s] <file.ml>\n", os.Args[0])
		flag.PrintDefaults()
	}
	flag.Parse()

	if flag.NArg() != 1 {
		flag.Usage()
		os.Exit(2)
	}

	src, err := os.ReadFile(flag.Arg(0))
	if err != nil {
		panic(err)
	}

	code := Parse(Lex(src))
	if *asm {
		Assemble(code, os.Stdout)
		return
	}
	Run(Compile(code))
}
