package main

type VM struct {
	Data IntStack
	PC   int
}

type Op func(*VM)

func Run(ops []Op) {
	vm := &VM{}
	for vm.PC < len(ops) {
		op := ops[vm.PC]
		vm.PC++
		op(vm)
	}
}
