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

- **Folder:** `unittest`
- **Mode:** Agent
- **Prompt:** `The code in the httpfile folder parses the Jetbrains .http file format. Please write a unit test. Use the testdata directory feature of Go.`

### Evaluate

- Does the test pass? (`go test`)
- Are negative cases checked?
- Is the implementation tested, or just the surface behavior?
- Are there overlapping/redundant tests?
- Does the agent execute the test at the end?

---

## 2. Refactor HTML into NPM Package

- **Folder:** `webapp`
- **Mode:** Agent
- **Prompts:**
  1. `This is a single page application with a sidebar and a main view with a canvas. Refactor the single index.html file into a separate .css and .js file.`
  2. `Use vite as build tool for the webpage. For this, produce an initial npm package.`
  3. `Exchange JavaScript for TypeScript.`
  4. `Use tailwind instead of a simple .css file.`

### Evaluate

- Check for correct display, especially the sidebar on mobile
- Does it use flex or grid?
- **Bonus:** Use the image as basis to produce the initial index.html

---

## 3. BASIC Interpreter

- **Folder:** `basic`
- **Mode:** Plan
- **Prompt:** `Read requirements.md and implement a basic interpreter.`

### Evaluate

- Do all BASIC example programs run correctly?
- Does the agent test the examples?
- Does the agent support endless-running programs?
- Does the agent handle INPUT commands for the examples?
- Is the architecture reasonable?

---

## 4. MOS6502 Assembler Parser

- **Folder:** `asm`
- **Mode:** Plan
- **Prompt:** `Read requirements.md and implement an MOS6502 assembler parser according to spec.`

### Evaluate

- Do all example `.asm` files assemble correctly?
- Are unit tests automatically produced?
- Are the correct opcodes produced in `store.asm`?

---

## 5. Refactor Python into Go

- **Folder:** `decompiler`
- **Mode:** Plan
- **Prompt:** `TODO`

### Evaluate

- TODO

---

## 6. Reverse Engineer Obfuscated Code

- **Folder:** `IOCCC`
- **Mode:** Plan
- **Prompts:**
  1. `In prog.c is an obfuscated program. What is its purpose? Write a README.md file explaining it.`
  2. `Unobfuscate the code by writing a clean main.c file.`

### Evaluate

- Compile `main.c` and run it. Does Linux still boot?
- Let the agent teiterate multiple times. What is the final result. 
