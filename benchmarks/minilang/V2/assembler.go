package main

import (
	"fmt"
	"io"
)

const asmPrologue = `.section .text
.globl _start

# print_int(rdi): writes signed decimal + '\n' to stdout
print_int:
    subq $32, %rsp
    leaq 31(%rsp), %rsi
    movb $10, (%rsi)
    movq %rdi, %rax
    xorq %r11, %r11
    testq %rax, %rax
    jns 1f
    negq %rax
    movq $1, %r11
1:  movq $10, %rcx
2:  xorq %rdx, %rdx
    divq %rcx
    addq $'0', %rdx
    decq %rsi
    movb %dl, (%rsi)
    testq %rax, %rax
    jnz 2b
    testq %r11, %r11
    jz 3f
    decq %rsi
    movb $'-', (%rsi)
3:  leaq 32(%rsp), %rdx
    subq %rsi, %rdx
    movq $1, %rax
    movq $1, %rdi
    syscall
    addq $32, %rsp
    ret

_start:
`

func Assemble(code []Instr, w io.Writer) {
	io.WriteString(w, asmPrologue)
	for i, ins := range code {
		fmt.Fprintf(w, "# %s\n", srcOf(ins))
		fmt.Fprintf(w, "Lop_%d:\n", i)
		emitInstr(w, i, ins)
	}
	fmt.Fprintf(w, "Lop_%d:\n", len(code))
	io.WriteString(w, "    movq $60, %rax\n    xorq %rdi, %rdi\n    syscall\n")
}

func srcOf(ins Instr) string {
	switch ins.Op {
	case "push":
		return fmt.Sprintf("%d", ins.Arg)
	case "pushaddr":
		return fmt.Sprintf("&Lop_%d", ins.Arg)
	}
	return ins.Op
}

func emitInstr(w io.Writer, i int, ins Instr) {
	switch ins.Op {
	case "push":
		fmt.Fprintf(w,
			"    movabsq $%d, %%rax\n"+
				"    pushq %%rax\n", ins.Arg)
	case "pushaddr":
		fmt.Fprintf(w,
			"    leaq Lop_%d(%%rip), %%rax\n"+
				"    pushq %%rax\n", ins.Arg)
	case "dup":
		io.WriteString(w,
			"    pushq (%rsp)\n")
	case "+":
		io.WriteString(w,
			"    popq %rax\n"+
				"    addq %rax, (%rsp)\n")
	case "=":
		io.WriteString(w,
			"    popq %rax\n"+
				"    xorq %rdx, %rdx\n"+
				"    cmpq %rax, (%rsp)\n"+
				"    sete %dl\n"+
				"    movq %rdx, (%rsp)\n")
	case "print":
		io.WriteString(w,
			"    popq %rdi\n"+
				"    call print_int\n")
	case "goto":
		io.WriteString(w,
			"    popq %rax\n"+
				"    jmp *%rax\n")
	case "if":
		fmt.Fprintf(w,
			"    popq %%rax\n"+
				"    popq %%rcx\n"+
				"    testq %%rcx, %%rcx\n"+
				"    jz Lop_skip_%d\n"+
				"    jmp *%%rax\n"+
				"Lop_skip_%d:\n", i, i)
	case "ifnot":
		fmt.Fprintf(w,
			"    popq %%rax\n"+
				"    popq %%rcx\n"+
				"    testq %%rcx, %%rcx\n"+
				"    jnz Lop_skip_%d\n"+
				"    jmp *%%rax\n"+
				"Lop_skip_%d:\n", i, i)
	default:
		panic("unknown instruction: " + ins.Op)
	}
}
