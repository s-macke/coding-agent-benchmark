package main

import (
	"encoding/binary"
	"fmt"
	"io"
)

const (
	elfBaseVA       = 0x400000
	elfHeaderSize   = 64
	elfPhdrSize     = 56
	elfTextOffset   = elfHeaderSize + elfPhdrSize
	elfPageAlign    = 0x1000
	elfTextStartVA  = elfBaseVA + elfTextOffset
	elfLoadSegmentR = 4
	elfLoadSegmentX = 1
)

func WriteELF(code []Instr, w io.Writer) error {
	text, entryOff, err := buildELFText(code)
	if err != nil {
		return err
	}

	file := make([]byte, elfTextOffset+len(text))
	copy(file[elfTextOffset:], text)

	entry := uint64(elfTextStartVA + entryOff)
	writeELFHeader(file, entry, uint64(len(file)), uint64(len(file)))

	_, err = w.Write(file)
	return err
}

func writeELFHeader(file []byte, entry, fileSize, memSize uint64) {
	copy(file[0:4], []byte{0x7f, 'E', 'L', 'F'})
	file[4] = 2 // 64-bit
	file[5] = 1 // little-endian
	file[6] = 1 // original ELF version

	binary.LittleEndian.PutUint16(file[16:], 2)  // ET_EXEC
	binary.LittleEndian.PutUint16(file[18:], 62) // EM_X86_64
	binary.LittleEndian.PutUint32(file[20:], 1)
	binary.LittleEndian.PutUint64(file[24:], entry)
	binary.LittleEndian.PutUint64(file[32:], elfHeaderSize)
	binary.LittleEndian.PutUint16(file[52:], elfHeaderSize)
	binary.LittleEndian.PutUint16(file[54:], elfPhdrSize)
	binary.LittleEndian.PutUint16(file[56:], 1)

	ph := file[elfHeaderSize:]
	binary.LittleEndian.PutUint32(ph[0:], 1) // PT_LOAD
	binary.LittleEndian.PutUint32(ph[4:], elfLoadSegmentR|elfLoadSegmentX)
	binary.LittleEndian.PutUint64(ph[8:], 0)
	binary.LittleEndian.PutUint64(ph[16:], elfBaseVA)
	binary.LittleEndian.PutUint64(ph[24:], elfBaseVA)
	binary.LittleEndian.PutUint64(ph[32:], fileSize)
	binary.LittleEndian.PutUint64(ph[40:], memSize)
	binary.LittleEndian.PutUint64(ph[48:], elfPageAlign)
}

type rel32Fixup struct {
	offset int
	target string
	addend int64
}

type elfTextBuilder struct {
	buf    []byte
	labels map[string]int
	fixups []rel32Fixup
}

func buildELFText(code []Instr) ([]byte, int, error) {
	b := &elfTextBuilder{
		labels: map[string]int{},
	}

	b.emitRuntime()
	entryOff := b.label("_start")

	for i, ins := range code {
		b.label(opLabel(i))
		if err := b.emitInstr(i, ins); err != nil {
			return nil, 0, err
		}
	}

	b.label(opLabel(len(code)))
	b.movImm32Reg(60, 0)      // movq $60, %rax
	b.bytes(0x48, 0x31, 0xff) // xorq %rdi, %rdi
	b.bytes(0x0f, 0x05)       // syscall

	if err := b.patchRel32(); err != nil {
		return nil, 0, err
	}
	return b.buf, entryOff, nil
}

func (b *elfTextBuilder) emitRuntime() {
	b.label("print_int")
	b.bytes(0x48, 0x83, 0xec, 32)       // subq $32, %rsp
	b.bytes(0x48, 0x8d, 0x74, 0x24, 31) // leaq 31(%rsp), %rsi
	b.bytes(0xc6, 0x06, 10)             // movb $10, (%rsi)
	b.bytes(0x48, 0x89, 0xf8)           // movq %rdi, %rax
	b.bytes(0x4d, 0x31, 0xdb)           // xorq %r11, %r11
	b.bytes(0x48, 0x85, 0xc0)           // testq %rax, %rax
	b.jcc(0x89, "print_nonneg")         // jns print_nonneg
	b.bytes(0x48, 0xf7, 0xd8)           // negq %rax
	b.movImm32Reg(1, 11)                // movq $1, %r11
	b.label("print_nonneg")
	b.movImm32Reg(10, 1) // movq $10, %rcx
	b.label("print_loop")
	b.bytes(0x48, 0x31, 0xd2)     // xorq %rdx, %rdx
	b.bytes(0x48, 0xf7, 0xf1)     // divq %rcx
	b.bytes(0x48, 0x83, 0xc2, 48) // addq $'0', %rdx
	b.bytes(0x48, 0xff, 0xce)     // decq %rsi
	b.bytes(0x88, 0x16)           // movb %dl, (%rsi)
	b.bytes(0x48, 0x85, 0xc0)     // testq %rax, %rax
	b.jcc(0x85, "print_loop")     // jnz print_loop
	b.bytes(0x4d, 0x85, 0xdb)     // testq %r11, %r11
	b.jcc(0x84, "print_write")    // jz print_write
	b.bytes(0x48, 0xff, 0xce)     // decq %rsi
	b.bytes(0xc6, 0x06, '-')      // movb $'-', (%rsi)
	b.label("print_write")
	b.bytes(0x48, 0x8d, 0x54, 0x24, 32) // leaq 32(%rsp), %rdx
	b.bytes(0x48, 0x29, 0xf2)           // subq %rsi, %rdx
	b.movImm32Reg(1, 0)                 // movq $1, %rax
	b.movImm32Reg(1, 7)                 // movq $1, %rdi
	b.bytes(0x0f, 0x05)                 // syscall
	b.bytes(0x48, 0x83, 0xc4, 32)       // addq $32, %rsp
	b.bytes(0xc3)                       // ret
}

func (b *elfTextBuilder) emitInstr(i int, ins Instr) error {
	switch ins.Op {
	case "push":
		b.bytes(0x48, 0xb8)           // movabsq $imm64, %rax
		b.u64(uint64(int64(ins.Arg))) // movabsq $imm64, %rax
		b.bytes(0x50)                 // pushq %rax
	case "pushaddr":
		b.leaRIP(opLabel(ins.Arg), 0, 0) // leaq op_N(%rip), %rax
		b.bytes(0x50)                    // pushq %rax
	case "dup":
		b.bytes(0xff, 0x34, 0x24) // pushq (%rsp)
	case "+":
		b.bytes(0x58)                   // popq %rax
		b.bytes(0x48, 0x01, 0x04, 0x24) // addq %rax, (%rsp)
	case "=":
		b.bytes(0x58)                   // popq %rax
		b.bytes(0x48, 0x31, 0xd2)       // xorq %rdx, %rdx
		b.bytes(0x48, 0x39, 0x04, 0x24) // cmpq %rax, (%rsp)
		b.bytes(0x0f, 0x94, 0xc2)       // sete %dl
		b.bytes(0x48, 0x89, 0x14, 0x24) // movq %rdx, (%rsp)
	case "print":
		b.bytes(0x5f)       // popq %rdi
		b.call("print_int") // call print_int
	case "goto":
		b.bytes(0x58)       // popq %rax
		b.bytes(0xff, 0xe0) // jmp *%rax
	case "if":
		skip := fmt.Sprintf("skip_%d", i)
		b.bytes(0x58)             // popq %rax
		b.bytes(0x59)             // popq %rcx
		b.bytes(0x48, 0x85, 0xc9) // testq %rcx, %rcx
		b.jcc(0x84, skip)         // jz skip_N
		b.bytes(0xff, 0xe0)       // jmp *%rax
		b.label(skip)
	case "ifnot":
		skip := fmt.Sprintf("skip_%d", i)
		b.bytes(0x58)             // popq %rax
		b.bytes(0x59)             // popq %rcx
		b.bytes(0x48, 0x85, 0xc9) // testq %rcx, %rcx
		b.jcc(0x85, skip)         // jnz skip_N
		b.bytes(0xff, 0xe0)       // jmp *%rax
		b.label(skip)
	default:
		return fmt.Errorf("unknown instruction: %s", ins.Op)
	}
	return nil
}

func (b *elfTextBuilder) bytes(v ...byte) {
	b.buf = append(b.buf, v...)
}

func (b *elfTextBuilder) u32(v uint32) {
	var scratch [4]byte
	binary.LittleEndian.PutUint32(scratch[:], v)
	b.bytes(scratch[:]...) // rel32 or imm32 operand bytes for the current instruction
}

func (b *elfTextBuilder) u64(v uint64) {
	var scratch [8]byte
	binary.LittleEndian.PutUint64(scratch[:], v)
	b.bytes(scratch[:]...) // imm64 operand bytes for the current instruction
}

func (b *elfTextBuilder) label(name string) int {
	offset := len(b.buf)
	b.labels[name] = offset
	return offset
}

func (b *elfTextBuilder) rel32(target string, addend int64) {
	b.fixups = append(b.fixups, rel32Fixup{offset: len(b.buf), target: target, addend: addend})
	b.u32(0) // rel32 placeholder for the current instruction
}

func (b *elfTextBuilder) leaRIP(target string, addend int64, reg byte) {
	b.bytes(0x48, 0x8d, 0x05|(reg<<3)) // leaq disp32(%rip), r64
	b.rel32(target, addend)            // leaq disp32(%rip), r64
}

func (b *elfTextBuilder) call(target string) {
	b.bytes(0xe8)      // call rel32
	b.rel32(target, 0) // call rel32
}

func (b *elfTextBuilder) jcc(cc byte, target string) {
	b.bytes(0x0f, cc)  // jcc rel32
	b.rel32(target, 0) // jcc rel32
}

func (b *elfTextBuilder) movImm32Reg(imm int32, reg byte) {
	rex := byte(0x48)
	if reg >= 8 {
		rex |= 0x01
	}
	b.bytes(rex, 0xc7, 0xc0|(reg&7)) // movq $imm32, r64
	b.u32(uint32(imm))               // movq $imm32, r64
}

func (b *elfTextBuilder) patchRel32() error {
	for _, f := range b.fixups {
		target, ok := b.targetVA(f.target)
		if !ok {
			return fmt.Errorf("unknown code generation target: %s", f.target)
		}
		next := int64(elfTextStartVA + f.offset + 4)
		disp := int64(target) + f.addend - next
		if disp < -0x80000000 || disp > 0x7fffffff {
			return fmt.Errorf("target out of rel32 range: %s", f.target)
		}
		binary.LittleEndian.PutUint32(b.buf[f.offset:], uint32(int32(disp)))
	}
	return nil
}

func (b *elfTextBuilder) targetVA(name string) (uint64, bool) {
	if offset, ok := b.labels[name]; ok {
		return uint64(elfTextStartVA + offset), true
	}
	return 0, false
}

func opLabel(i int) string {
	return fmt.Sprintf("op_%d", i)
}
