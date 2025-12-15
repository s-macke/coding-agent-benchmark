# coding-agent-benchmark

Over several months I have tested a dozen of coding agents. To even get an idea about the performance I started testing them with the same tasks. This repository contains my reoccuring tasks.
Currently the evaluation is fully in person.

# Write Unit Test for http file parser.
- **Folder:** unittest
- **Mode:** Agent
- **Prompt:** `The code in the httpfile folder parses the Jetbrains .http file format. Please write a unit test. Use the testdata directory feature of Go.`

### Evaluate
- Does the test run? "go test"
- Negative cases are checked
- Is the implementation tested or the sense behind it?
- Overlapping tests?
- Is the test executed at the end?

# Refactor Single website HTML into npm package using vite, tailwind and typescript.
- **Folder:** webapp
- **Mode:** Agent
- **Prompt:** `This is a single page application with a sidebar and a main view with a canvas. Refactor the single index.html file into a separate .css and .js file.`
- **Prompt:** `Use vite as build tool for the webpage. For this, produce an initial npm package.`
- **Prompt:** `Exchange JavaScript for TypeScript.`
- **Prompt:** `Use tailwind instead of a simple .css file.`

### Evaluate
- Check for correct display. Especially the sidebar on mobile
- Bonus: Use the image as basis to produce the initial index.html.
- Uses flex or grid?

# Write Basic Interpreter with Spec and examples.
- **Folder:** basic
- **Mode:** Plan
- **Prompt:** `Read requirements.md and implement a basic interpreter.`
- Check the all basic example programs.
- Does the agent test the examples?
- Does the agent support endless running programs?
- Does the agent solve input commands for the examples?
- Is the architecture Ok?

# Write Assembler Parser with spec and examples.
- **Folder:** asm
- **Mode:** Plan
- **Prompt:** `Read requirements.md and implement an MOS6502 assembler parser according to spec.`

### Evaluate
- Check the all example .asm files.
- Are unit test automatically produced
- Check if the correct opcodes are produced in store.asm

# Refactor Python into Go.
- **Folder:** decompiler
- **Mode:** Plan
- **Prompt:** `TODO`
## Evaluate
-TODO

# Reverse Engineer obsfucated code
- **Folder:** IOCCC
- **Mode:** Plan
- **Prompt:** `In prog.c is an obsfucated code. What is the purpose of the program and write a README.md file.`
- **Prompt:** `Unobsfucate the code by writing a clean main.c file`

### Evaluate
- Compile main and run. Does Linux still boot?
