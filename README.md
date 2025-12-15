# Coding Agent Benchmark

A collection of standardized tasks for evaluating coding agents. Over several months, I have tested a dozen coding agents. To compare their performance, I started testing them with the same tasks. This repository contains those recurring benchmark tasks.

Currently, the evaluation is done manually.

## Table of Contents

1. [Unit Test for HTTP File Parser](#1-unit-test-for-http-file-parser)
2. [Refactor HTML into NPM Package](#2-refactor-html-into-npm-package)
3. [BASIC Interpreter](#3-basic-interpreter)
4. [MOS6502 Assembler Parser](#4-mos6502-assembler-parser)
5. [Refactor Python into Go](#5-refactor-python-into-go)
6. [Reverse Engineer Obfuscated Code](#6-reverse-engineer-obfuscated-code)

---

## 1. Unit Test for HTTP File Parser

Tests the agent's ability to write comprehensive unit tests for existing Go code.

- **Folder:** `unittest`
- **Mode:** Agent
- **Prompt:** `The code in the httpfile folder parses the JetBrains .http file format. Write unit tests for the parser. Use Go's testdata directory convention.`

**Context:** The parser is a state machine that handles HTTP requests with headers, bodies, comments, and request separators (`###`). An `example.http` file is provided as reference.

### Evaluate

- Does `go test` pass?
- Are edge cases tested (malformed input, empty files, missing headers)?
- Are tests well-structured without redundancy?
- Does the agent run the tests before finishing?

---

## 2. Refactor HTML into NPM Package

Tests progressive refactoring skills: extracting code from a monolithic file and modernizing the toolchain.

- **Folder:** `webapp`
- **Mode:** Agent
- **Prompts:** (run sequentially in separate sessions)
  1. `Refactor index.html into separate .css and .js files. It's a single page app with a collapsible sidebar and a canvas.`
  2. `Set up Vite as the build tool with an npm package.`
  3. `Convert JavaScript to TypeScript.`
  4. `Replace the CSS file with Tailwind CSS.`

**Context:** The `index.html` is a ~24KB WebGPU demo with embedded styles (~300 lines) and scripts (~240 lines). It has a dark theme, collapsible sidebar navigation, and responsive mobile layout with a hamburger menu. A reference screenshot (`webgpu_demo_page.png`) is included.

### Evaluate

- Does the app display correctly after each refactoring step?
- Does the mobile sidebar (hamburger menu) still work?
- Does the agent use flexbox or grid for layout?
- Does the agent preserve all WebGPU functionality?
- **Bonus:** Can the agent recreate `index.html` from the screenshot alone?

---

## 3. BASIC Interpreter

Tests the agent's ability to implement a complete interpreter from a specification.

- **Folder:** `basic`
- **Mode:** Plan
- **Prompt:** `Read requirements.md and implement a BASIC interpreter in Go.`

**Context:** The spec defines a minimal BASIC dialect with:
- Statements: `PRINT`, `INPUT`, `LET`, `FOR/NEXT`, `IF/THEN`, `GOTO`, `END`, `REM`
- Expressions: arithmetic (`+`, `-`, `*`, `/`), comparisons, parentheses
- Variables: numeric (`X`) and string (`N$`), case-insensitive
- Line numbers required; multiple statements per line with `:` separator
- CLI: `basic [-debug] <filename.bas>`

Eight example programs are provided, ranging from simple "hello world" to a number guessing game with user input.

### Evaluate

- Do all 8 example programs (`example1.bas` through `example8.bas`) run correctly?
- Does the agent validate its implementation by running the examples?
- Can it handle infinite loops (e.g., `10 GOTO 10`) without crashing?
- Does the `INPUT` statement work interactively?
- Is the code architecture clean (separate lexer, parser, interpreter)?

---

## 4. MOS6502 Assembler Parser

Tests the agent's ability to implement a parser with complex addressing modes and binary output.

- **Folder:** `asm`
- **Mode:** Plan
- **Prompt:** `Read requirements.md and implement an MOS6502 assembler in Go. Output JSON with symbols and machine code.`

**Context:** The spec defines a 6502 assembler supporting:
- 56 instruction mnemonics (LDA, STA, JMP, BEQ, etc.)
- 11 addressing modes (immediate, zero page, absolute, indexed, indirect, etc.)
- Numeric formats: hex (`$FF`), decimal (`255`), binary (`%11111111`)
- Operand modifiers: `<` (low byte), `>` (high byte), `+`/`-` (arithmetic)
- Directives: `* = $XXXX` (origin), labels, constants, comments

A partial `opcodes.go` with enums is provided. Output is JSON containing symbol table and assembled instructions with addresses and opcodes.

Seven example `.asm` files test various instructions and addressing modes.

### Evaluate

- Do all 7 example files (`simple_load.asm`, `arithmetic.asm`, `branch.asm`, etc.) assemble without errors?
- Does the agent write unit tests?
- Are the opcodes in `store.asm` correct? (verify against 6502 reference)
- Does the agent handle label forward references correctly?
- Does the agent use the provided `opcodes.go` or reimplement it?

---

## 5. Refactor Python into Go

Tests the agent's ability to translate idiomatic Python code into idiomatic Go.

- **Folder:** `decompiler`
- **Mode:** Plan
- **Prompt:** *Not yet defined*

**Status:** This benchmark is planned but not yet populated with content.

### Evaluate

- *Not yet defined*

---

## 6. Reverse Engineer Obfuscated Code

Tests the agent's ability to analyze and understand heavily obfuscated C code (IOCCC-style).

- **Folder:** `IOCCC`
- **Mode:** Plan
- **Prompts:**
  1. `Analyze prog.c and determine what this obfuscated program does. Write a README.md explaining its purpose.`
  2. `Unobfuscate the code by writing a clean, readable main.c that does the same thing.`

**Context:** The file `prog.c` (~1.7MB) is an International Obfuscated C Code Contest entry featuring:
- Aggressive macro obfuscation (`#define` abuse)
- Compressed variable names and cryptic formatting
- Complex bitwise operations and pointer arithmetic
- Terminal I/O (uses `termios.h`)
- Hidden comments with clues ("haystack test", "Find the clue", "strawberry")

A compiled binary `a` is included for reference.

### Evaluate

- Does the agent correctly identify the program's purpose?
- Does `main.c` compile and produce the same behavior as `prog.c`?
- How many iterations does the agent need to fully unobfuscate?
- Does the agent follow the embedded clues?
- Is the final `main.c` readable and well-documented?
