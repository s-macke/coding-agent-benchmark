package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

var huffmanTable = []string{
	"1111110101100100000010", "1111110101100100000011", "1111110101100100000100", "1111110101100100000101",
	"1111110101100100000110", "1111110101100100000111", "1111110101100100001000", "1111110101100100001001",
	"1111110101100100001010", "00111", "10101", "1111110101100100001011", "1111110101100100001100",
	"1111110101100100001101", "1111110101100100001110", "1111110101100100001111", "1111110101100100010000",
	"1111110101100100010001", "1111110101100100010010", "1111110101100100010011", "1111110101100100010100",
	"1111110101100100010101", "1111110101100100010110", "1111110101100100010111", "1111110101100100011000",
	"1111110101100100011001", "1111110101100100011010", "1111110101100100011011", "1111110101100100011100",
	"1111110101100100011101", "1111110101100100011110", "1111110101100100011111", "110", "01100000101",
	"0000011", "10110110111", "101101101100", "1111110101101", "1111110100", "11111101011000", "0100100",
	"0100101", "11101100", "10111110", "11100", "1111011", "1110111", "1001111", "101100", "111100",
	"010110", "1011110", "1011010", "0101110", "0000010", "0110001", "0101111", "0100001", "1110101",
	"10111111", "101101101101", "010101", "01111100", "111111010100", "0111111100100", "010011101",
	"111011010", "0100110", "101101111", "011000010", "100111010", "011000000", "1001110110", "01111101",
	"011000001001", "111111010111", "101101100", "111111011", "101101110", "0111111101", "11111100",
	"0111111111", "01111110", "0100000", "01001111", "011111110011", "01111111000", "1001110111",
	"11111101011001001", "011000001000", "1111110101100101", "00101", "111111010101", "00110", "10011100",
	"1110100", "0110000011", "10001", "0101000", "011001", "1111010", "0001", "1001101", "1111101",
	"000010", "10100", "010011100", "111011011", "101110", "010001", "10010", "01101", "011110",
	"1011011010", "01110", "00100", "10000", "000011", "0101001", "011000011", "1111100", "1001100",
	"0111111110", "1111111", "0111111100101", "000000", "111111010110011", "111111010110010000000",
}

func splitString(s string, n int) []string {
	var result []string
	for i := 0; i < len(s); i += n {
		end := i + n
		if end > len(s) {
			end = len(s)
		}
		result = append(result, s[i:end])
	}
	return result
}

func HuffmanEncode(body string) string {
	var result strings.Builder
	for _, ch := range body {
		result.WriteString(huffmanTable[int(ch)])
	}
	// encode a final EOT character
	result.WriteString(huffmanTable[4])
	bits := result.String()
	// add trailing zeros to match a multiple of 13 bits
	nzeros := 13 - (len(bits) % 13)
	if nzeros == 13 {
		nzeros = 0
	}
	for i := 0; i < nzeros; i++ {
		bits += "0"
	}
	return bits
}

func reverseString(s string) string {
	runes := []rune(s)
	for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
		runes[i], runes[j] = runes[j], runes[i]
	}
	return string(runes)
}

func Base95Encode(s string) string {
	code := splitString(s, 13)
	var result strings.Builder
	for _, c := range code {
		// convert string of 13 bits to be in reversed order
		reversed := reverseString(c)
		number, _ := strconv.ParseInt(reversed, 2, 64)
		hi := number / 95
		lo := number - hi*95
		result.WriteByte(byte(hi + 32))
		result.WriteByte(byte(lo + 32))
	}
	return result.String()
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintf(os.Stderr, "Usage: %s <input_file> <output_file>\n", os.Args[0])
		//		fmt.Fprintln(os.Stderr, "Encode Mathematica files")
		os.Exit(1)
	}

	inputFile := os.Args[1]
	outputFile := os.Args[2]

	body, err := os.ReadFile(inputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading input file: %v\n", err)
		os.Exit(1)
	}

	bits := HuffmanEncode(string(body))
	code := Base95Encode(bits)

	lines := splitString(code, 70)
	output := "(*!1N!*)mcm\n" + strings.Join(lines, "\n") + "\n"

	err = os.WriteFile(outputFile, []byte(output), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error writing output file: %v\n", err)
		os.Exit(1)
	}
}
