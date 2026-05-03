package main

import "fmt"

func Compile(code []Instr) []Op {
	ops := make([]Op, len(code))
	for i, ins := range code {
		ops[i] = compileOne(ins)
	}
	return ops
}

func compileOne(ins Instr) Op {
	switch ins.Op {
	case "push", "pushaddr":
		arg := ins.Arg
		return func(v *VM) { v.Data.Push(arg) }
	case "dup":
		return func(v *VM) { v.Data.Push(v.Data.Peek()) }
	case "+":
		return func(v *VM) {
			a, b := v.Data.Pop(), v.Data.Pop()
			v.Data.Push(b + a)
		}
	case "=":
		return func(v *VM) {
			a, b := v.Data.Pop(), v.Data.Pop()
			if a == b {
				v.Data.Push(1)
			} else {
				v.Data.Push(0)
			}
		}
	case "print":
		return func(v *VM) { fmt.Println(v.Data.Pop()) }
	case "goto":
		return func(v *VM) { v.PC = v.Data.Pop() }
	case "if":
		return func(v *VM) {
			addr, cond := v.Data.Pop(), v.Data.Pop()
			if cond != 0 {
				v.PC = addr
			}
		}
	case "ifnot":
		return func(v *VM) {
			addr, cond := v.Data.Pop(), v.Data.Pop()
			if cond == 0 {
				v.PC = addr
			}
		}
	}
	panic("unknown instruction: " + ins.Op)
}
