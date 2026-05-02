package main

import "fmt"

func Run(code []Instr) {
	var data, ret IntStack
	pc := 0
	for pc < len(code) {
		ins := code[pc]
		pc++
		switch ins.Op {
		case "push", "pushaddr":
			data.Push(ins.Arg)
		case "+":
			a, b := data.Pop(), data.Pop()
			data.Push(b + a)
		case "=":
			a, b := data.Pop(), data.Pop()
			if a == b {
				data.Push(1)
			} else {
				data.Push(0)
			}
		case "print":
			fmt.Println(data.Pop())
		case "goto":
			pc = data.Pop()
		case "if":
			addr, cond := data.Pop(), data.Pop()
			if cond != 0 {
				pc = addr
			}
		case "ifnot":
			addr, cond := data.Pop(), data.Pop()
			if cond == 0 {
				pc = addr
			}
		case "gosub":
			addr := data.Pop()
			ret.Push(pc)
			pc = addr
		case "ret":
			pc = ret.Pop()
		default:
			panic("unknown instruction: " + ins.Op)
		}
	}
}
