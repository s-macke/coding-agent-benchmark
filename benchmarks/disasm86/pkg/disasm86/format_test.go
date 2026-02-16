package disasm86

import "testing"

func TestRenderIntel(t *testing.T) {
	inst := Instruction{
		Mnemonic: "mov",
		Operands: []Operand{{Kind: OperandKindRaw, Text: "ax"}, {Kind: OperandKindRaw, Text: "1234"}},
	}
	if got, want := RenderIntel(inst), "mov ax,1234"; got != want {
		t.Fatalf("RenderIntel() = %q, want %q", got, want)
	}
}

func TestInstructionIsPrefix(t *testing.T) {
	inst := Instruction{Prefixes: []Prefix{PrefixES}}
	if !inst.IsPrefix() {
		t.Fatal("expected IsPrefix to be true")
	}
}
