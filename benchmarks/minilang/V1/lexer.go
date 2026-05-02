package main

import "strings"

func Lex(src []byte) []string {
	return strings.Fields(string(src))
}
