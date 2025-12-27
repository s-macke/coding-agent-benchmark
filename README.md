# Coding Agent Benchmark

A collection of standardized tasks for evaluating coding agents. Over several months, I have tested a dozen coding agents. To compare their performance, I started testing them with the same tasks. This repository contains those recurring benchmark tasks.

Currently, the evaluation is done manually.

## Table of Contents

1. [Unit Test for HTTP File Parser](#1-unit-test-for-http-file-parser)
2. [Refactor HTML into NPM Package](#2-refactor-html-into-npm-package)
3. [BASIC Interpreter](#3-basic-interpreter)
4. [MOS6502 Assembler Parser](#4-mos6502-assembler-parser)
5. [Port Python Decompiler to Go](#5-port-python-decompiler-to-go)
6. [Reverse Engineer Obfuscated Code](#6-reverse-engineer-obfuscated-code)
7. [Migrate FFmpeg Library](#7-migrate-ffmpeg-library)

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
- Are the opcodes in `store.asm` correct regarding page boundaries?
- Does the agent handle label forward references correctly?
- Does the agent use the provided `opcodes.go` or reimplement it?
- How many passes does the assembler do?
- Is the code architecture clean (separate lexer, parser, interpreter)?

---

## 5. Port Python Decompiler to Go

Tests the agent's ability to translate a complex Python codebase to idiomatic Go while preserving functionality.

- **Folder:** `refactor`
- **Mode:** Plan
- **Prompt:** `Port the 6502/ARM decompiler from Python to Go. Use GO_PORT_DESIGN.md as the architecture guide.`

**Context:** The `decomp-6502-arm/` folder contains a Python decompiler (~12 files, ~3000 lines) that converts 6502/ARM machine code into C-like pseudocode through a multi-stage pipeline:

```
Binary → Instruction Tracing → SSA Conversion → Expression Trees → Control Flow Structuring → Code Generation
```

Key components:
- `decomp.py` - Main entry point and CLI
- `insn.py`, `insn_6502.py`, `insn_arm.py` - Instruction tracing and decoding
- `ssa.py`, `ssa_6502.py`, `ssa_arm.py` - SSA form conversion
- `expr.py` - Expression tree with 90+ operation types and simplification rules
- `block.py` - Control flow structuring (if-then-else, loops)
- `code.py` - C code generation

A comprehensive `GO_PORT_DESIGN.md` provides the target architecture with Go struct definitions, package layout, and implementation notes.

Test binaries in `test/` can verify the port produces identical output.

### Evaluate

- Does the Go port compile and run?
- Does it produce identical output to the Python version on test binaries?
- Does the agent follow the design document's package structure?
- Is the Go code idiomatic (error handling, interfaces, no global state)?
- Does the agent write unit tests?
- How does the agent handle Python-specific patterns (dynamic typing, `None`, `isinstance()`)?

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
- Hidden comments with clues ("haystack test", "Find the clue", "strawberry")

A compiled binary `a` is included for reference.

### Evaluate

- Does the agent correctly identify the program's purpose?
- Does `main.c` compile and produce the same behavior as `prog.c`?
- How many iterations does the agent need to fully unobfuscate?
- Does the agent follow the embedded clues?
- Is the final `main.c` readable and well-documented?

---

## 7. Migrate FFmpeg Library

Tests the agent's ability to migrate a Go project from a deprecated library to a modern replacement with different APIs.

- **Folder:** `newlib`
- **Mode:** Agent
- **Prompt:** `Migrate main.go from the deprecated goav library to go-astiav. Test with sample.mp4.`

**Context:** The code is an ASCII cinema server that decodes video files using FFmpeg (via Go bindings) and converts frames to colored ASCII art. It serves the stream over HTTP (port 12345) and TCP (port 8081), playing videos in an endless loop.

The current implementation uses `github.com/giorgisio/goav`, which is outdated. It must be migrated to `github.com/asticode/go-astiav`.

### Evaluate

- Does the migrated code compile and run?
- Does the ASCII video stream display correctly in a terminal?
- Does the agent consult the go-astiav documentation or examples?
- Does the agent preserve all functionality (HTTP/TCP serving, color output, looping)?
- Does the agent test with the provided sample video?

## 8. Write decode for an unknown encode function.

Test the capability to analyze a difficult encoding/compression format.
Compile encode.go in the utils and put it into the encode directory.

- **Folder:** `newlib`
- **Mode:** Agent
  **Prompt:** `The Encode CLI program provides a file encoding algorithm. Analyze the output of the encoding function and determine the algorithm. Write a spec.md file with the used algorithm.`

### Evaluate

- Does the agent recognizes the huffman encoding in the error message?
- Does the agent recognizes the bit encoding format?


## 9. Port of old Adventure Game
- **Folder:** `gameport`
- **Mode:** Agent
- **Prompts:**
  1. `Detokenize the basic code and write the result into .bas files`
  2. `What does the basic file reveal about the binary world file? Write the result a into spec.md file`
  3. `Extract the world map and show the map as a png file`
  4. `Can you use the correct tile pixel information for the image?`

## 10. Port of old Strategy game
- **Folder:** `gameport`
- **Mode:** Agent
- **Prompts:**
  1. `Analyze weltendaemmerung.bin and write the results into spec.md`
  2. `Disassemble the file using disasm6502.py`
  3. `Extract the map with tiles and store into a png image`
  4. `Extract the stats of the units`
