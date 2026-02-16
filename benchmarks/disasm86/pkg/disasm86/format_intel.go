package disasm86

import "strings"

// RenderIntel renders an instruction to normalized Intel-style text.
func RenderIntel(inst Instruction) string {
	if inst.Mnemonic == "" {
		return ""
	}
	if len(inst.Operands) == 0 {
		return inst.Mnemonic
	}
	parts := make([]string, 0, len(inst.Operands))
	for _, op := range inst.Operands {
		parts = append(parts, op.Text)
	}
	return inst.Mnemonic + " " + strings.Join(parts, ",")
}
