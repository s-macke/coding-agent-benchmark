package disasm86

import "strings"

// String renders an instruction to normalized Intel-style text.
func (inst Instruction) String() string {
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
