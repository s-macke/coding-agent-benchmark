package disasm86

import (
	"fmt"
	"strings"
)

type decodeState struct {
	src      ByteSource
	seg      uint16
	start    uint16
	off      uint16
	opcode   byte
	mnemonic string
	operands []Operand
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

func (s *decodeState) appendf(format string, args ...any) {
	s.append(fmt.Sprintf(format, args...))
}

func (s *decodeState) append(text string) {
	parts := strings.Split(text, ",")
	for _, part := range parts {
		s.addOperand(part)
	}
}

func (s *decodeState) setText(text string) {
	s.mnemonic = strings.TrimSpace(text)
	s.operands = nil
}

func (s *decodeState) setMnemonic(text string) {
	s.mnemonic = strings.TrimSpace(text)
}

func (s *decodeState) appendMnemonicSuffix(suffix string) {
	s.mnemonic += suffix
}

func (s *decodeState) addOperand(text string) {
	text = strings.TrimSpace(text)
	if text == "" {
		return
	}
	s.operands = append(s.operands, Operand{Kind: OperandKindRaw, Text: text})
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
