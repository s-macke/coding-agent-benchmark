package disasm86

// ByteSource provides random-access bytes by physical address.
type ByteSource interface {
	ByteAt(addr uint32) (byte, error)
}

// Decoder decodes one instruction at a segment:offset address.
type Decoder interface {
	DecodeAt(seg uint16, off uint16, src ByteSource) (Instruction, uint16, error)
}

type OperandKind int

const (
	OperandKindRaw OperandKind = iota
)

// Operand is a rendered operand token.
type Operand struct {
	Kind OperandKind
	Text string
}

type Prefix string

const (
	PrefixES    Prefix = "es"
	PrefixCS    Prefix = "cs"
	PrefixSS    Prefix = "ss"
	PrefixDS    Prefix = "ds"
	PrefixLOCK  Prefix = "lock"
	PrefixREPZ  Prefix = "repz"
	PrefixREPNZ Prefix = "repnz"
)

// Instruction is the structured representation of one decoded instruction.
type Instruction struct {
	Opcode   byte
	Mnemonic string
	Operands []Operand
	Length   uint16
	Prefixes []Prefix
	Raw      []byte
}

func (i Instruction) IsPrefix() bool {
	return len(i.Prefixes) > 0
}

// NewDecoder constructs a stateless 8086 decoder.
func NewDecoder() Decoder {
	return decoder{}
}
