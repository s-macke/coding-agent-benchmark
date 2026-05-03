# minilang

`minilang` is a tiny postfix programming language for teaching stack machines.

Programs are written as a sequence of tokens. Most operations consume values from
the data stack and push a result back onto the stack.

## Running

- `minilang file.ml` runs through the interpreter.
- `minilang -s file.ml` prints x86-64 Linux assembly.
- `minilang -o program file.ml` writes a standalone x86-64 Linux ELF executable.

## Core Ideas

- Postfix notation: `2 3 +`
- A data stack for numbers and intermediate results
- Labels for control flow
- Label addresses as first-class values via `&label`

## Lexical Rules

- Tokens are separated by whitespace.
- Integer literals push their value onto the data stack.
- Instruction names are case-sensitive. Use lowercase keywords such as `print`.
- A label definition is an identifier followed by `:`, for example `loop:`.
- `&name` pushes the address of label `name` onto the data stack.

## Execution Model

Execution starts at the first token in the file and proceeds left to right. The
data stack stores integers and label addresses.

## Instructions

### Stack and Arithmetic

- `dup` copies the top data-stack value
- `+` pops `a` and `b`, then pushes `a + b`
- `=` pops `a` and `b`, then pushes `1` if they are equal, otherwise `0`
- `print` pops one value and prints it

For binary operations, the left operand is the older stack value. For example:

```minilang
2 3 +
```

pushes `5`.

## Control Flow

### Labels

```minilang
start:
```

defines a jump target named `start`.

### Unconditional Jump

```minilang
&start goto
```

`goto` pops a label address from the data stack and transfers control there.

### Conditional Jump

```minilang
condition &target if
condition &target ifnot
```

- `if` pops a target address and a condition, then jumps if the condition is nonzero
- `ifnot` pops a target address and a condition, then jumps if the condition is zero

## Examples

Addition:

```minilang
2 3 + print
```

See [examples/add.ml](examples/add.ml).

Printing a literal:

```minilang
3 print
```

See [examples/print.ml](examples/print.ml).

Equality result:

```minilang
1 1 = print
1 2 = print
```

See [examples/equal.ml](examples/equal.ml) and [examples/unequal.ml](examples/unequal.ml).

Loop:

```minilang
loop:
3 print
&loop goto
```

See [examples/loop.ml](examples/loop.ml).

Count from 1 through 10 with a loop:

```minilang
1
loop:
dup print
dup 10 = &done if
1 +
&loop goto
done:
```

See [examples/count_to_ten_loop.ml](examples/count_to_ten_loop.ml).

Forward jump:

```minilang
&start goto
0 print

start:
1 print
```

See [examples/goto.ml](examples/goto.ml).

Conditional branch:

```minilang
1 2 = &equal if
0 print
&done goto

equal:
1 print

done:
```

See [examples/if.ml](examples/if.ml).

Conditional branch on zero:

```minilang
1 2 = &notequal ifnot
0 print
&done goto

notequal:
1 print

done:
```

See [examples/ifnot.ml](examples/ifnot.ml).

## Summary

`minilang` is intentionally small. The current language consists of:

- integer literals
- labels and label addresses
- `dup`
- `+`
- `=`
- `print`
- `goto`
- `if`
- `ifnot`
