package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	asm := flag.Bool("s", false, "emit x86_64 Linux assembly to stdout instead of running")
	out := flag.String("o", "", "write a Linux x86_64 ELF executable to this path instead of running")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "usage: %s [-s | -o output] <file.ml>\n", os.Args[0])
		flag.PrintDefaults()
	}
	flag.Parse()

	if flag.NArg() != 1 || (*asm && *out != "") {
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
	if *out != "" {
		f, err := os.OpenFile(*out, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
		if err != nil {
			panic(err)
		}
		if err := WriteELF(code, f); err != nil {
			f.Close()
			panic(err)
		}
		if err := f.Close(); err != nil {
			panic(err)
		}
		return
	}
	Run(Compile(code))
}
