package disasm86

import (
	"fmt"
	"strings"
)

const (
	dfPrefix  uint8 = 1
	dfNoSpace uint8 = 2
)

type decodeFunc func(*decodeState) error

type disasmEntry struct {
	text   string
	decode decodeFunc
	flags  uint8
	supp   []string
}

type decoder struct{}

type decodeState struct {
	src    ByteSource
	seg    uint16
	start  uint16
	off    uint16
	opcode byte
	out    strings.Builder
}

var byteReg = [...]string{"al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"}
var wordReg = [...]string{"ax", "cx", "dx", "bx", "sp", "bp", "si", "di"}
var segReg = [...]string{"es", "cs", "ss", "ds", "unknown_seg_reg", "unknown_seg_reg", "unknown_seg_reg", "unknown_seg_reg"}
var indexReg = [...]string{"bx+si", "bx+di", "bp+si", "bp+di", "si", "di", "bp", "bx"}
var nulReg = [...]string{"??", "??", "??", "??", "??", "??", "??", "??"}
var condition = [...]string{"o", "no", "b", "ae", "z", "nz", "be", "a", "s", "ns", "p", "np", "l", "ge", "le", "g"}

func hexN(v uint8) string {
	return fmt.Sprintf("0x%X", v)
}

func hex8(v uint8) string {
	return fmt.Sprintf("0x%02X", v)
}

func hex16(v uint16) string {
	return fmt.Sprintf("0x%04X", v)
}

func hex32(v uint32) string {
	return fmt.Sprintf("0x%08X", v)
}

func (decoder) DecodeAt(seg uint16, off uint16, src ByteSource) (Instruction, uint16, error) {
	state := decodeState{
		src:   src,
		seg:   seg,
		start: off,
		off:   off,
	}

	opcode, err := state.read8()
	if err != nil {
		return Instruction{}, off, err
	}
	state.opcode = opcode

	entry := disasmTable[opcode]
	if len(entry.supp) > 0 {
		modrm, err := state.peek8()
		if err != nil {
			return Instruction{}, state.off, err
		}
		state.out.WriteString(fmt.Sprintf("%-6s ", entry.supp[(modrm&0x38)>>3]))
	} else {
		if entry.flags&dfNoSpace != 0 {
			state.out.WriteString(entry.text)
		} else {
			state.out.WriteString(fmt.Sprintf("%-6s ", entry.text))
		}
	}

	if entry.decode != nil {
		if err := entry.decode(&state); err != nil {
			return Instruction{}, state.off, err
		}
	}

	text := strings.TrimRight(state.out.String(), " ")
	mnemonic, operands := splitInstruction(text)
	length := state.off - state.start
	raw, err := readRaw(seg, state.start, length, src)
	if err != nil {
		return Instruction{}, state.off, err
	}

	inst := Instruction{
		Opcode:   opcode,
		Mnemonic: mnemonic,
		Operands: operands,
		Length:   length,
		Prefixes: entryPrefixes(opcode, entry),
		Raw:      raw,
		Text:     text,
	}
	return inst, state.off, nil
}

func splitInstruction(text string) (string, []Operand) {
	trimmed := strings.TrimSpace(text)
	if trimmed == "" {
		return "", nil
	}

	space := strings.IndexByte(trimmed, ' ')
	if space < 0 {
		return trimmed, nil
	}

	mnemonic := trimmed[:space]
	rest := strings.TrimSpace(trimmed[space+1:])
	if rest == "" {
		return mnemonic, nil
	}

	parts := strings.Split(rest, ",")
	operands := make([]Operand, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		operands = append(operands, Operand{Kind: OperandKindRaw, Text: part})
	}
	return mnemonic, operands
}

func readRaw(seg uint16, start uint16, length uint16, src ByteSource) ([]byte, error) {
	raw := make([]byte, int(length))
	off := start
	for i := range raw {
		b, err := src.ByteAt(uint32(seg)<<4 + uint32(off))
		if err != nil {
			return nil, err
		}
		raw[i] = b
		off++
	}
	return raw, nil
}

func entryPrefixes(op byte, entry disasmEntry) []Prefix {
	if entry.flags&dfPrefix == 0 {
		return nil
	}
	prefix := Prefix(entry.text)
	switch op {
	case 0x26:
		prefix = PrefixES
	case 0x2e:
		prefix = PrefixCS
	case 0x36:
		prefix = PrefixSS
	case 0x3e:
		prefix = PrefixDS
	case 0xf0:
		prefix = PrefixLOCK
	case 0xf2:
		prefix = PrefixREPNZ
	case 0xf3:
		prefix = PrefixREPZ
	}
	return []Prefix{prefix}
}

func (s *decodeState) addr(off uint16) uint32 {
	return uint32(s.seg)<<4 + uint32(off)
}

func (s *decodeState) peek8() (byte, error) {
	return s.src.ByteAt(s.addr(s.off))
}

func (s *decodeState) read8() (byte, error) {
	b, err := s.peek8()
	if err != nil {
		return 0, err
	}
	s.off++
	return b, nil
}

func (s *decodeState) read16() (uint16, error) {
	lo, err := s.read8()
	if err != nil {
		return 0, err
	}
	hi, err := s.read8()
	if err != nil {
		return 0, err
	}
	return uint16(lo) | (uint16(hi) << 8), nil
}

func (s *decodeState) read32() (uint32, error) {
	b0, err := s.read8()
	if err != nil {
		return 0, err
	}
	b1, err := s.read8()
	if err != nil {
		return 0, err
	}
	b2, err := s.read8()
	if err != nil {
		return 0, err
	}
	b3, err := s.read8()
	if err != nil {
		return 0, err
	}
	return uint32(b0) | (uint32(b1) << 8) | (uint32(b2) << 16) | (uint32(b3) << 24), nil
}

func (s *decodeState) appendf(format string, args ...any) {
	s.out.WriteString(fmt.Sprintf(format, args...))
}

func (s *decodeState) append(text string) {
	s.out.WriteString(text)
}

func (s *decodeState) setText(text string) {
	s.out.Reset()
	s.out.WriteString(text)
}

func getByteReg(modrm byte) string {
	return byteReg[(modrm&0x38)>>3]
}

func getWordReg(modrm byte) string {
	return wordReg[(modrm&0x38)>>3]
}

func getSegReg(modrm byte) string {
	return segReg[(modrm&0x38)>>3]
}

func (s *decodeState) getMem(modrm byte, reg []string, msg string) (string, error) {
	rm := modrm & 0x07
	switch modrm & 0xc0 {
	case 0x00:
		if rm != 6 {
			return fmt.Sprintf("%s[%s]", msg, indexReg[rm]), nil
		}
		num, err := s.read16()
		if err != nil {
			return "", err
		}
		return fmt.Sprintf("%s[%s]", msg, hex16(num)), nil
	case 0x40:
		disp, err := s.read8()
		if err != nil {
			return "", err
		}
		num := int(int8(disp))
		ch := '+'
		if num < 0 {
			ch = '-'
			num = -num
		}
		return fmt.Sprintf("%s[%s%c%s]", msg, indexReg[rm], ch, hex8(uint8(num))), nil
	case 0x80:
		disp, err := s.read16()
		if err != nil {
			return "", err
		}
		num := int(int16(disp))
		ch := '+'
		if num < 0 {
			ch = '-'
			num = -num
		}
		return fmt.Sprintf("%s[%s%c%s]", msg, indexReg[rm], ch, hex16(uint16(num))), nil
	case 0xc0:
		return reg[rm], nil
	default:
		return "", fmt.Errorf("invalid modrm: 0x%02X", modrm)
	}
}

func (s *decodeState) getDisp() (uint16, error) {
	disp, err := s.read8()
	if err != nil {
		return 0, err
	}
	return uint16(int32(s.off) + int32(int8(disp))), nil
}

func (s *decodeState) getDisp16() (uint16, error) {
	disp, err := s.read16()
	if err != nil {
		return 0, err
	}
	return uint16(int32(s.off) + int32(int16(disp))), nil
}

func decode_br8(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, byteReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, getByteReg(modrm))
	return nil
}

func decode_r8b(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, byteReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", getByteReg(modrm), mem)
	return nil
}

func decode_wr16(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, getWordReg(modrm))
	return nil
}

func decode_r16w(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", getWordReg(modrm), mem)
	return nil
}

func decode_r16m(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	if modrm&0xc0 == 0xc0 {
		s.setText("???")
		return nil
	}
	mem, err := s.getMem(modrm, wordReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", getWordReg(modrm), mem)
	return nil
}

func decode_ald8(s *decodeState) error {
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("al,%s", hex8(num))
	return nil
}

func decode_axd16(s *decodeState) error {
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("ax,%s", hex16(num))
	return nil
}

func decode_pushpopseg(s *decodeState) error {
	s.append(getSegReg(s.opcode))
	return nil
}

func decode_databyte(s *decodeState) error {
	s.append(hex8(s.opcode))
	return nil
}

func decode_wordreg(s *decodeState) error {
	s.append(wordReg[s.opcode&0x7])
	return nil
}

func decode_cond_jump(s *decodeState) error {
	target, err := s.getDisp()
	if err != nil {
		return err
	}
	s.appendf("%-5s %s", condition[s.opcode&0x0f], hex16(target))
	return nil
}

func decode_bd8(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, byteReg[:], "byte ptr ")
	if err != nil {
		return err
	}
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, hex8(num))
	return nil
}

func decode_wd16(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "word ptr ")
	if err != nil {
		return err
	}
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, hex16(num))
	return nil
}

func decode_wd8(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "word ptr ")
	if err != nil {
		return err
	}
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, hex8(num))
	return nil
}

func decode_ws(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, getSegReg(modrm))
	return nil
}

func decode_sw(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", getSegReg(modrm), mem)
	return nil
}

func decode_w(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "word ptr ")
	if err != nil {
		return err
	}
	s.append(mem)
	return nil
}

func decode_b(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, byteReg[:], "byte ptr ")
	if err != nil {
		return err
	}
	s.append(mem)
	return nil
}

func decode_xchgax(s *decodeState) error {
	s.appendf("ax,%s", wordReg[s.opcode&0x7])
	return nil
}

func decode_far(s *decodeState) error {
	offset, err := s.read16()
	if err != nil {
		return err
	}
	segment, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("%s:%s", hex16(segment), hex16(offset))
	return nil
}

func decode_almem(s *decodeState) error {
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("al,[%s]", hex16(num))
	return nil
}

func decode_axmem(s *decodeState) error {
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("ax,[%s]", hex16(num))
	return nil
}

func decode_memal(s *decodeState) error {
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("[%s],al", hex16(num))
	return nil
}

func decode_memax(s *decodeState) error {
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.appendf("[%s],ax", hex16(num))
	return nil
}

func decode_string(s *decodeState) error {
	if s.opcode&0x01 != 0 {
		s.append("w")
	} else {
		s.append("b")
	}
	return nil
}

func decode_rd(s *decodeState) error {
	if (s.opcode & 0x0f) > 7 {
		num, err := s.read16()
		if err != nil {
			return err
		}
		s.appendf("%s,%s", wordReg[s.opcode&0x07], hex16(num))
		return nil
	}
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("%s,%s", byteReg[s.opcode&0x07], hex8(num))
	return nil
}

func decode_d16(s *decodeState) error {
	num, err := s.read16()
	if err != nil {
		return err
	}
	s.append(hex16(num))
	return nil
}

func decode_int3(s *decodeState) error {
	s.append(hexN(3))
	return nil
}

func decode_d8(s *decodeState) error {
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.append(hex8(num))
	return nil
}

func decode_bbit1(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, byteReg[:], "byte ptr ")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, hexN(1))
	return nil
}

func decode_wbit1(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "word ptr ")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", mem, hexN(1))
	return nil
}

func decode_bbitcl(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, byteReg[:], "byte ptr ")
	if err != nil {
		return err
	}
	s.appendf("%s,cl", mem)
	return nil
}

func decode_wbitcl(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, wordReg[:], "word ptr ")
	if err != nil {
		return err
	}
	s.appendf("%s,cl", mem)
	return nil
}

func decode_escape(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	mem, err := s.getMem(modrm, nulReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("%s,%s", hexN(s.opcode&0x7), mem)
	return nil
}

func decode_disp(s *decodeState) error {
	target, err := s.getDisp()
	if err != nil {
		return err
	}
	s.append(hex16(target))
	return nil
}

func decode_adjust(s *decodeState) error {
	num, err := s.read8()
	if err != nil {
		return err
	}
	if num != 10 {
		s.append(hex8(num))
	}
	return nil
}

func decode_d8al(s *decodeState) error {
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("%s,al", hex8(num))
	return nil
}

func decode_d8ax(s *decodeState) error {
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("%s,ax", hex8(num))
	return nil
}

func decode_axd8(s *decodeState) error {
	num, err := s.read8()
	if err != nil {
		return err
	}
	s.appendf("ax,%s", hex8(num))
	return nil
}

func decode_disp16(s *decodeState) error {
	target, err := s.getDisp16()
	if err != nil {
		return err
	}
	s.append(hex16(target))
	return nil
}

func decode_far_ind(s *decodeState) error {
	modrm, err := s.read8()
	if err != nil {
		return err
	}
	if modrm&0xc0 == 0xc0 {
		s.setText("???")
		return nil
	}
	mem, err := s.getMem(modrm, wordReg[:], "")
	if err != nil {
		return err
	}
	s.appendf("far %s", mem)
	return nil
}

func decode_portdx(s *decodeState) error {
	switch s.opcode {
	case 0xec:
		s.append("al,dx")
	case 0xed:
		s.append("ax,dx")
	case 0xee:
		s.append("dx,al")
	case 0xef:
		s.append("dx,ax")
	}
	return nil
}

func decode_f6(s *decodeState) error {
	modrm, err := s.peek8()
	if err != nil {
		return err
	}
	if modrm&0x38 == 0x00 {
		return decode_bd8(s)
	}
	return decode_b(s)
}

func decode_f7(s *decodeState) error {
	modrm, err := s.peek8()
	if err != nil {
		return err
	}
	if modrm&0x38 == 0x00 {
		return decode_wd16(s)
	}
	return decode_w(s)
}

func decode_ff(s *decodeState) error {
	modrm, err := s.peek8()
	if err != nil {
		return err
	}
	group := (modrm & 0x38) >> 3
	if group == 3 || group == 5 {
		return decode_far_ind(s)
	}
	return decode_w(s)
}

func decode_bioscall(s *decodeState) error {
	next, err := s.peek8()
	if err != nil {
		return err
	}
	if next == 0xf1 {
		_, _ = s.read8()
		addr, err := s.read32()
		if err != nil {
			return err
		}
		s.appendf("bios   %s", hex32(addr))
		return nil
	}
	s.append("db     0xF1")
	return nil
}
