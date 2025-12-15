# MOS6502 Assembler in Go

## Overview

A MOS6502 assembler written in Golang that parses assembly source files and outputs machine code in JSON format.

## Usage

```
asm [-debug] <filename.asm>
```

- `-debug`: Enable debug output
- `<filename.asm>`: Input assembly file

## Input Syntax

### Directives & Definitions

| Element  | Syntax        | Example          |
|----------|---------------|------------------|
| Origin   | `* = $XXXX`   | `* = $8000`      |
| Label    | `name:`       | `start:`         |
| Constant | `NAME = expr` | `SCREEN = $0400` |
| Comment  | `; text`      | `; comment`      |

### Numeric Formats

| Format      | Syntax           | Example        |
|-------------|------------------|----------------|
| Hexadecimal | `$XX` or `$XXXX` | `$42`, `$8000` |
| Decimal     | `nn`             | `40`, `256`    |
| Binary      | `%xxxxxxxx`      | `%10101010`    |

### Operand Modifiers

| Modifier | Meaning     | Example        |
|----------|-------------|----------------|
| `<expr`  | Low byte    | `lda #<SCREEN` |
| `>expr`  | High byte   | `lda #>SCREEN` |
| `expr+n` | Addition    | `sta ptr+1`    |
| `expr-n` | Subtraction | `sta ptr-1`    |

## Addressing Modes

| Mode             | Syntax    | Size | Example       |
|------------------|-----------|------|---------------|
| Implied          | (none)    | 1    | `rts`         |
| Accumulator      | `A`       | 1    | `asl a`       |
| Immediate        | `#$XX`    | 2    | `lda #$42`    |
| Zero Page        | `$XX`     | 2    | `sta $00`     |
| Zero Page,X      | `$XX,X`   | 2    | `lda $10,x`   |
| Zero Page,Y      | `$XX,Y`   | 2    | `ldx $10,y`   |
| Absolute         | `$XXXX`   | 3    | `jmp $8000`   |
| Absolute,X       | `$XXXX,X` | 3    | `lda $1000,x` |
| Absolute,Y       | `$XXXX,Y` | 3    | `lda $1000,y` |
| Indirect         | `($XXXX)` | 3    | `jmp ($FFFC)` |
| Indexed Indirect | `($XX,X)` | 2    | `lda ($40,x)` |
| Indirect Indexed | `($XX),Y` | 2    | `sta (ptr),y` |
| Relative         | `label`   | 2    | `bne loop`    |

## Output Format

JSON object containing symbol table and assembled instructions:

```json
{
  "symbols": {
    "SCREEN": {
      "value": 1024,
      "type": "constant"
    },
    "ptr": {
      "value": 251,
      "type": "constant"
    },
    "start": {
      "value": 32768,
      "type": "label"
    },
    "loop": {
      "value": 32770,
      "type": "label"
    }
  },
  "instructions": [
    {
      "Address": "0x8000",
      "Opcode": "0xA9",
      "Value": 66
    },
    {
      "Address": "0x8002",
      "Opcode": "0x85",
      "Value": 0
    }
  ]
}
```

### Symbol Table

| Field   | Description                                                                  |
|---------|------------------------------------------------------------------------------|
| `value` | Numeric value of the symbol                                                  |
| `type`  | Symbol type: `"constant"` (defined with `=`) or `"label"` (defined with `:`) |

### Instructions

| Field     | Description                                                      |
|-----------|------------------------------------------------------------------|
| `Address` | Memory address of instruction (hex string)                       |
| `Opcode`  | Instruction opcode byte (hex string)                             |
| `Value`   | Operand value as integer (omitted for implied/accumulator modes) |

Note: `Value` is an integer to support signed relative branch offsets (-128 to 127).

## Dependencies

- `opcodes.go` - Opcode definitions, addressing modes, instruction metadata

## Testing

Test the implementation against all files in the "examples" directory.
