# disasm86

Go port of the legacy `disasm8086` C disassembler.

## Layout

- `pkg/disasm86`: reusable decode library with a separate byte-source interface.
- `cmd/disasm86`: CLI wrapper.
- `disasm8086`: legacy C source kept as a reference implementation.
- `tools/c_ref`: harness and script to regenerate C-based golden vectors.

## Quick Start

```bash
go test ./...
go run ./cmd/disasm86 -hex "B8 34 12"
```

All rendered hex values are prefixed with `0x`.
The CLI decodes continuously until the end of the provided buffer.

## Regenerate C Golden Vectors

```bash
tools/c_ref/generate_vectors.sh
```
