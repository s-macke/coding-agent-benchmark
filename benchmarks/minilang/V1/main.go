package main

import "os"

func main() {
	src, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	Run(Parse(Lex(src)))
}
