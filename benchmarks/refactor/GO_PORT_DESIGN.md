# Decompiler Go Port Design Document

## Overview

This document describes the technical design for porting the 6502/ARM decompiler from Python to Go. The decompiler converts binary machine code into C-like pseudocode through a multi-stage pipeline.

## Architecture Summary

```
Binary → Instruction Tracing → SSA Conversion → Expression Trees → Control Flow Structuring → Code Generation
         (MCodeGraph)          (SSAGraph)        (Expr)            (BasicBlock/AdvancedBlock)  (Code)
```

---

## Package Structure

```
decomp/
├── cmd/
│   └── decomp/
│       ├── main.go              # CLI entry point and decompiler pipeline ✓
│       └── args.go              # Command-line argument parsing ✓
├── internal/
│   ├── arch/
│   │   ├── arch.go              # Architecture abstraction ✓
│   │   ├── arm/
│   │   │   └── arm.go           # ARM tracing, SSA translation, entry point guessing ✓
│   │   └── mos6502/
│   │       ├── mos6502.go       # Registration entry point ✓
│   │       ├── decode.go        # Instruction decoding and disassembly ✓
│   │       ├── trace.go         # Control flow tracing ✓
│   │       ├── translate.go     # SSA translation ✓
│   │       └── mos6502_test.go  # 24 unit tests ✓
│   ├── insn/
│   │   ├── insn.go              # Instruction and MCodeGraph ✓
│   │   └── symbol.go            # Symbol table ✓
│   ├── ssa/
│   │   ├── statement.go         # SSAStatement ✓
│   │   ├── def.go               # SSADef ✓
│   │   ├── graph.go             # SSAGraph, GetAll, GetAllDefs ✓
│   │   ├── type.go              # SSAType, TypeKind constants ✓
│   │   ├── cache.go             # Package-level caches (ssaCache, funReturnsD, etc.) ✓
│   │   ├── ssaify.go            # SSAify, IdentifyReturns (Phase 7) ✓
│   │   ├── dce.go               # Dead code elimination ✓
│   │   ├── propagate.go         # Propagate, Depropagate ✓
│   │   ├── propagate_test.go    # Propagation unit tests ✓
│   │   ├── dessa.go             # De-SSA transformation ✓
│   │   ├── types.go             # RecoverSimpleTypes, RecoverCompoundTypes ✓
│   │   └── analysis.go          # FindDefinitions, FindArgs, FindRets, Simplify ✓
│   ├── expr/
│   │   ├── types.go             # ExprType constants ✓
│   │   ├── expr.go              # Expression trees, Substitute, Equals ✓
│   │   ├── simplify.go          # Expr.Simplify() with 21 rules ✓
│   │   └── simplify_test.go     # Simplification unit tests ✓
│   ├── block/
│   │   ├── basic.go             # BasicBlock ✓
│   │   ├── advanced.go          # AdvancedBlock ✓
│   │   ├── structure.go         # Control flow structuring ✓
│   │   └── block_test.go        # Block unit tests ✓
│   ├── codegen/
│   │   ├── code.go              # C code generation ✓
│   │   └── code_test.go         # 30 unit tests ✓
│   └── debug/
│       └── debug.go             # Debug logging ✓
├── pkg/
│   └── errors/
│       └── errors.go            # Custom error types ✓
├── test/
│   ├── build.sh                 # ACME assembler build script ✓
│   ├── src/                     # Assembly source files ✓
│   │   ├── simple_load.asm      # Load/store test
│   │   ├── arithmetic.asm       # ADC, SBC, INC, DEC test
│   │   ├── branch.asm           # Branch instructions test
│   │   ├── jump.asm             # JMP, JSR, RTS test
│   │   └── loop.asm             # Loop pattern test
│   └── bin/                     # Compiled test binaries (generated)
├── .gitignore                   # Ignore binaries, test output ✓
└── go.mod
```

---

## Core Data Structures

### 1. Instruction Layer (`internal/insn`)

#### Insn - Machine Instruction Node

```go
package insn

// Insn represents a single machine instruction in the control flow graph
type Insn struct {
    Addr             uint32
    Bytes            []byte
    Disas            string
    Next             []*Insn       // Successor instructions (0-2)
    ComeFrom         []*Insn       // Predecessor instructions
    Sym              *Symbol
    FakeBranch       int           // -1 = normal, 0/1 = forced path index
    FixedMem         int32         // Constant memory address discovered, -1 = none
    FixedStack       int32         // Constant stack offset discovered, -1 = none
    ArtificialBranch int           // For inserted conditional branches

    // ARM-specific fields (decoded from opcode) - added in Phase 3
    Cond      int // Condition code (bits 28-31), 0xE = always
    Op        int // Opcode field (bits 20-27)
    Rn        int // First operand register (bits 16-19)
    Rd        int // Destination register (bits 12-15)
    Rs        int // Shift register (bits 8-11)
    ShiftBits int // Shift amount (bits 7-11)
    Shift     int // Shift type (bits 5-6): 0=LSL, 1=LSR, 2=ASR, 3=ROR
    ShiftRot  int // Shift by register flag (bit 4)
    Rm        int // Second operand register (bits 0-3)
    Imm8      int // 8-bit immediate (bits 0-7)
    Imm12     int // 12-bit immediate (bits 0-11)
    Off24     int // 24-bit branch offset (bits 0-23), sign-extended
    Reglist   int // Register list for LDM/STM (bits 0-15)
    SetFlags  int // S bit - set flags (bit 20)
}

func NewInsn(addr uint32) *Insn {
    return &Insn{
        Addr:             addr,
        Next:             make([]*Insn, 0, 2),
        ComeFrom:         make([]*Insn, 0),
        FakeBranch:       -1,
        FixedMem:         -1,
        FixedStack:       -1,
        ArtificialBranch: -1,
    }
}

func (i *Insn) String() string {
    // Format: "0x8000: LDA #$00 -> [0x8002] <- [0x7ffe]"
}
```

#### Symbol - Named Function/Location

```go
// Symbol represents a named location (function entry point)
type Symbol struct {
    Address uint32
    Name    string
    Insn    *Insn   // First instruction of this symbol
}

// Global symbol table loaded from file
// Note: Python uses Symbol.symbols (class variable); Go uses package-level var
var Symbols map[uint32]string

func NewSymbol(address uint32, name string) *Symbol {
    s := &Symbol{Address: address}
    if Symbols != nil {
        if n, ok := Symbols[address]; ok {
            s.Name = n
            return s
        }
    }
    if name == "" {
        name = "sym"
    }
    s.Name = fmt.Sprintf("%s_%04x", name, address)
    return s
}

func LoadSymbols(filename string) error {
    // Parse CSV format: addr,name
}
```

#### MCodeGraph - Control Flow Graph Builder

```go
// MCodeGraph manages the traced code and discovered symbols
type MCodeGraph struct {
    Symbols   map[uint32]*Symbol
    Traced    map[uint32]*Insn
    TraceArch func(g *MCodeGraph, code []byte, org, addr uint32, ins *Insn) *Insn
}

// SetTraceFunc sets the architecture-specific trace function.
func (g *MCodeGraph) SetTraceFunc(f func(g *MCodeGraph, code []byte, org, addr uint32, ins *Insn) *Insn) {
    g.TraceArch = f
}

// Package-level variables for binary data (needed by SSA for constant folding)
var (
    Text []byte  // Binary code
    Org  uint32  // Origin address
)

// NewMCodeGraph creates a new control flow graph builder
// Note: Python's __init__ takes no params and reads arch.name from global.
// This Go version takes archName parameter for explicitness.
func NewMCodeGraph(archName string) (*MCodeGraph, error) {
    g := &MCodeGraph{
        Symbols: make(map[uint32]*Symbol),
        Traced:  make(map[uint32]*Insn),
    }
    switch archName {
    case "arm":
        g.traceArch = arch.TraceARM
    case "6502":
        g.traceArch = arch.Trace6502
    default:
        return nil, fmt.Errorf("unknown architecture: %s", archName)
    }
    return g, nil
}

func (g *MCodeGraph) TraceAll(code []byte, org uint32, entries, autoEntries []uint32) {
    Text = code
    Org = org
    for _, e := range entries {
        g.Trace(code, org, e, nil, NewSymbol(e, "start"))
    }
    for _, e := range autoEntries {
        g.Trace(code, org, e, nil, NewSymbol(e, "guess"))
    }
}

func (g *MCodeGraph) Trace(code []byte, org, addr uint32, comeFrom *Insn, sym *Symbol) *Insn {
    // Recursive tracing logic
    // Returns existing Insn if already traced, else creates new
}
```

---

### 2. Architecture Abstraction (`internal/arch`)

```go
package arch

import "decomp/internal/insn"

// TraceFunc is the signature for architecture-specific instruction tracing.
type TraceFunc func(g *insn.MCodeGraph, code []byte, org, addr uint32, ins *insn.Insn) *insn.Insn

// GuessEntryPointsFunc is the signature for architecture-specific entry point guessing.
type GuessEntryPointsFunc func(text []byte, org uint32, manualEntries []uint32) []uint32

// Arch holds architecture-specific configuration
type Arch struct {
    Name                  string
    RegisterBase          bool       // Registers as base addresses (ARM) vs direct (6502)
    MaxArrayIdx           uint32     // Max index before treating as absolute address
    RegisterType          string     // C type for registers
    RegisterSize          int        // Bits per register
    Registers             []string   // Register names
    Flags                 []string   // Flag names (C, Z, N, V)
    ReturnLocs            []string   // Registers that can hold return values
    NonReturnLocs         []string   // Registers that don't hold return values
    ArgLocs               []string   // Registers that can hold arguments
    NonArgLocs            []string   // Registers that don't hold arguments
    NumberedRegisters     bool       // R0-R15 style naming
    StackedReturnAddress  bool       // Return address on stack (6502) vs link register

    // Architecture-specific functions (set by arch-specific packages)
    Trace            TraceFunc
    GuessEntryPoints GuessEntryPointsFunc
}

// Current holds the active architecture configuration
// Note: Python uses a module-level Arch() instance with set_arch() method.
// Go uses package-level var with SetArch() function for cleaner API.
var Current *Arch

func SetArch(name string) error {
    // Initialize with 6502 defaults
    Current = &Arch{
        Name:                 name,
        RegisterBase:         false,
        MaxArrayIdx:          0x100,
        RegisterType:         "uint8_t",
        RegisterSize:         8,
        Flags:                []string{"C", "Z", "N", "V"},
        NumberedRegisters:    false,
        StackedReturnAddress: false,
    }

    switch name {
    case "arm":
        Current.RegisterBase = true
        Current.MaxArrayIdx = 0x10000000
        Current.RegisterType = "uint32_t"
        Current.RegisterSize = 32
        Current.Registers = []string{"R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7",
                                     "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15"}
        Current.ReturnLocs = Current.Registers[0:2]
        Current.NonReturnLocs = append(append([]string{}, Current.Registers[2:]...), Current.Flags...)
        Current.ArgLocs = Current.Registers[0:4]
        Current.NonArgLocs = append(append([]string{}, Current.Registers[4:]...), Current.Flags...)
        Current.NumberedRegisters = true
        // Trace and GuessEntryPoints are set by importing the arm package

    case "6502":
        Current.Registers = []string{"A", "X", "Y"}
        Current.ReturnLocs = append(append([]string{}, Current.Registers...), Current.Flags...)
        Current.NonReturnLocs = []string{}
        Current.ArgLocs = Current.ReturnLocs
        Current.NonArgLocs = []string{}
        Current.StackedReturnAddress = true

    default:
        return fmt.Errorf("unknown architecture: %s", name)
    }
    return nil
}
```

---

### 3. SSA Layer (`internal/ssa`)

#### SSAType - Type Information

```go
package ssa

// TypeKind represents the category of an SSA type
// These values match Python's SSAType class constants (ssa.py:190-196)
type TypeKind int

const (
    TypeUnknown  TypeKind = 0  // UNKNOWN = 0
    TypeScalar   TypeKind = 1  // SCALAR = 1
    TypeDPointer TypeKind = 2  // DPOINTER = 2 (Data pointer)
    TypeFPointer TypeKind = 3  // FPOINTER = 3 (Function pointer)
    TypeCompound TypeKind = 4  // COMPOUND = 4 (Struct)
    TypeSigned   TypeKind = 5  // SIGNED = 5
    TypeUnsigned TypeKind = 6  // UNSIGNED = 6
)

// SSAType represents type information for SSA definitions
type SSAType struct {
    Type       TypeKind     // Note: Named "Type" to match Python's self.type
    Size       int          // Bits: 8, 16, 32
    Signedness TypeKind     // TypeSigned or TypeUnsigned
    Members    []SSAType    // For compound types; nil by default (matches Python's None)
}

func NewSSAType() *SSAType {
    return &SSAType{
        Type:       TypeUnknown,
        Signedness: TypeUnsigned,
    }
}

func (t *SSAType) IsDPointer(size int) bool {
    if size != -1 {
        return t.Type == TypeDPointer && t.Size == size
    }
    return t.Type == TypeDPointer
}

func (t *SSAType) String() string {
    // e.g., "unsignedscalar32"
}
```

#### SSADef - SSA Variable Definition

```go
// DefKey uniquely identifies an SSA definition location
// Note: Python uses (dtype, addr) tuple as key where addr can be None
type DefKey struct {
    Type string  // Register name, memory type ("M", "Mh", "Mw"), "s" (stack), "ap" (auto)
    Addr int32   // Address/offset; use sentinel value for "no address" (see HasAddr)
}

// SSADef represents a single SSA variable definition
// Note: Python's SSADef.__init__ has addr=None default. In Go we use a sentinel.
type SSADef struct {
    Type            string         // Location type
    Addr            int32          // Address; NoAddr (-1) for registers without address
    Idx             int            // SSA index: 0=input, 1+=assignments
    DefineStatement *SSAStatement  // Statement that creates this def
    DessaName       string         // De-SSA variable name
    IsDessaTmp      bool           // Is a temporary created during de-SSA
    DataType        *SSAType
    ParentDef       *expr.Expr     // For struct members, points to containing AUTO expr
}

// Key returns the unique identifier for this definition's location
func (d *SSADef) Key() DefKey {
    return DefKey{Type: d.Type, Addr: d.Addr}
}

// IsText returns true if this is a memory location in the code section
func (d *SSADef) IsText() bool {
    if d.Type[0] != 'M' {
        return false
    }
    addr, ok := d.Addr, d.Addr >= 0
    if !ok {
        return false
    }
    return uint32(addr) >= insn.Org && uint32(addr) < insn.Org+uint32(len(insn.Text))
}

func (d *SSADef) String() string {
    // Format: "R0(1)" or "M0x2000(2)"
}
```

#### SSAStatement - SSA Operation Node

```go
// StmtOp represents the operation type of an SSA statement
// Values match Python constants (ssa.py:30-35): ASGN=0, BRANCH_COND=1, etc.
type StmtOp int

const (
    OpAsgn       StmtOp = 0  // ASGN = 0
    OpBranchCond StmtOp = 1  // BRANCH_COND = 1
    OpCall       StmtOp = 2  // CALL = 2
    OpReturn     StmtOp = 3  // RETURN = 3
    OpEndlessLoop StmtOp = 4 // ENDLESS_LOOP = 4
    OpImpure     StmtOp = 5  // IMPURE = 5 (operation with side-effects)
)

// SSAStatement represents a single operation in the SSA graph
type SSAStatement struct {
    Num         int            // Unique statement number
    Op          StmtOp
    Dest        []*SSADef      // Destination definitions
    Expr        *expr.Expr     // Expression tree
    Next        []*SSAStatement
    ComeFrom    []*SSAStatement
    Insn        *insn.Insn     // Source machine instruction
    Reaching    []*SSADef      // Reaching definitions at this point
    CallUses    []*SSADef      // Definitions used by a CALL
    Comment     []string       // Attached comments
    CommentOnce []string       // Comments to emit only once
}

var statementCount int

func NewSSAStatement() *SSAStatement {
    s := &SSAStatement{
        Num:      statementCount,
        Dest:     make([]*SSADef, 0),
        Next:     make([]*SSAStatement, 0),
        ComeFrom: make([]*SSAStatement, 0),
    }
    statementCount++
    return s
}

func (s *SSAStatement) Chain(ctx *SSAifyContext, next *SSAStatement) {
    s.Next = append(s.Next, next)
    // Copy reaching definitions
    s.Reaching = make([]*SSADef, 0, len(ctx.LocalIndices))
    for _, def := range ctx.LocalIndices {
        s.Reaching = append(s.Reaching, def)
    }
    next.ComeFrom = append(next.ComeFrom, s)
    if next.Insn == nil {
        next.Insn = s.Insn
    }
}

func (s *SSAStatement) DestHasMem(savedRegsOff int32) bool {
    for _, d := range s.Dest {
        if d.Type == "s" && d.Addr < savedRegsOff {
            return true
        }
        if len(d.Type) > 0 && d.Type[0] == 'M' {
            return true
        }
    }
    return false
}

func (s *SSAStatement) AddComment(text string, once bool) {
    if once {
        for _, c := range s.CommentOnce {
            if c == text { return }
        }
        s.CommentOnce = append(s.CommentOnce, text)
    } else {
        for _, c := range s.Comment {
            if c == text { return }
        }
        s.Comment = append(s.Comment, text)
    }
}

func (s *SSAStatement) String() string {
    // Format: "42 R0(1) := (R1(0) + 4) -> 43 <- 41 {0x8000: ADD R0, R1, #4}"
}
```

#### SSAGraph - Function-Level SSA Graph

```go
// SSAifyContext holds the local state during SSA construction
// Note: Python uses _pass (underscore) to avoid keyword conflict; Go uses Pass
type SSAifyContext struct {
    Graph        *SSAGraph
    Pass         int                            // Python: self._pass
    LocalIndices map[DefKey]*SSADef  // Current definition for each location
}

func NewSSAifyContext(graph *SSAGraph) *SSAifyContext {
    ctx := &SSAifyContext{
        Graph:        graph,
        Pass:         graph.Pass,
        LocalIndices: make(map[DefKey]*SSADef),
    }
    // Initialize zero-index definitions for all registers and flags
    for _, reg := range arch.Current.Registers {
        NewSSADef(ctx, reg, -1, 0, false)
    }
    for _, flag := range arch.Current.Flags {
        NewSSADef(ctx, flag, -1, 0, false)
    }
    return ctx
}

func (c *SSAifyContext) Copy() *SSAifyContext {
    newCtx := &SSAifyContext{
        Graph:        c.Graph,
        Pass:         c.Pass,
        LocalIndices: make(map[DefKey]*SSADef, len(c.LocalIndices)),
    }
    for k, v := range c.LocalIndices {
        newCtx.LocalIndices[k] = v
    }
    return newCtx
}

// SSAGraph represents a function's complete SSA representation
type SSAGraph struct {
    Start         *SSAStatement
    Insns         map[*insn.Insn]*SSAStatement  // First SSA statement for each instruction
    SSAForInsn    map[*insn.Insn]*SSAStatement
    LastSSAForInsn map[*insn.Insn]*SSAStatement
    Indices       map[DefKey]*SSADef            // All definitions by location
    Zeros         map[DefKey]*SSADef            // Zero-index (input) definitions
    Definitions   []*SSADef                     // Definitions that reach function exit
    DefinitionsAll []*SSADef                    // All reaching definitions
    ActualReturns []*SSADef                     // Actual return values after analysis; nil initially (Python: None)
    FirstInsn     *insn.Insn
    Origin        uint32
    Symbol        string

    // Call graph
    CallersGraphs []*SSAGraph
    CallersSt     []*SSAStatement
    CalleeGraphs  []*SSAGraph

    // Stack frame
    BasePtr       int32
    EndBasePtr    int32
    // Note: StackObjPtrs stores stack offsets (int32) as keys for quick lookup.
    // RecoverCompoundTypes collects AUTO expressions separately for size calculation.
    StackObjPtrs  map[int32]struct{}       // Set of stack object offsets
    StackObjDefs  map[*SSADef]struct{}     // Stack object definitions

    // Configuration
    IOMap         []IORange                // MMIO address ranges
    Pass          int
    Blocks        interface{}              // BasicBlock after structuring

    // Architecture-specific translator (set by caller)
    Translate     TranslateFunc
}

// IORange represents an MMIO address range
type IORange struct {
    Start uint32
    End   uint32  // 0 for single address
}

// TranslateFunc signature for arch-specific instruction translation
type TranslateFunc func(g *SSAGraph, ctx *SSAifyContext, ins *insn.Insn,
                        sp, endBP, bp int32) (start, end *SSAStatement,
                        newSP, newBP, newEndBP int32, nextOverride []*insn.Insn)

func NewSSAGraph(iomap []IORange, pass int) *SSAGraph {
    return &SSAGraph{
        Insns:          make(map[*insn.Insn]*SSAStatement),
        SSAForInsn:     make(map[*insn.Insn]*SSAStatement),
        LastSSAForInsn: make(map[*insn.Insn]*SSAStatement),
        Indices:        make(map[DefKey]*SSADef),
        Zeros:          make(map[DefKey]*SSADef),
        Definitions:    []*SSADef{},
        StackObjPtrs:   make(map[int32]struct{}),
        StackObjDefs:   make(map[*SSADef]struct{}),
        CallersGraphs:  []*SSAGraph{},
        CallersSt:      []*SSAStatement{},
        CalleeGraphs:   []*SSAGraph{},
        IOMap:          iomap,
        Pass:           pass,
    }
    // Note: Caller must set g.Translate to the appropriate architecture-specific function
    // e.g., g.Translate = arm.TranslateARM or g.Translate = mos6502.Translate6502
}

// Key methods
func (g *SSAGraph) Add(ins *insn.Insn, sp, bp, endBP int32, ctx *SSAifyContext) *SSAStatement
func (g *SSAGraph) GetAll() []*SSAStatement  // Traverse all statements
func (g *SSAGraph) DCE()                      // Dead code elimination
func (g *SSAGraph) Propagate(pass int)        // Constant/copy propagation
func (g *SSAGraph) Depropagate()              // Reverse propagation for readability
func (g *SSAGraph) Simplify(pass int)         // Expression simplification
func (g *SSAGraph) Dessa()                    // Convert back from SSA form
func (g *SSAGraph) FindDefinitions()
func (g *SSAGraph) FindArgs()
func (g *SSAGraph) FindRets()
func (g *SSAGraph) IsIO(addr uint32) bool     // Check if address is in MMIO range
func (g *SSAGraph) RecoverCompoundTypes()
func (g *SSAGraph) RecoverSimpleTypes(mark string)
```

#### SSA Caches (Package Level)

```go
// Package-level caches for cross-function analysis
var (
    ssaCache            = make(map[uint32]*SSAGraph)
    ssaInProgress       = make(map[*insn.Insn]struct{})
    funReturnsD         = make(map[*insn.Insn][]*SSADef)
    funReturnsTentative = make(map[uint32]struct{})
    funArgsD            = make(map[*insn.Insn][]*SSADef)
    funArgsTentative    = make(map[uint32]struct{})
)

// SSAify converts an instruction to SSA form (main entry point)
func SSAify(ins *insn.Insn, symbol string, iomap []IORange) *SSAGraph

// IdentifyReturns analyzes return values across call graph
func IdentifyReturns(graphs []*SSAGraph)
```

---

### 4. Expression Trees (`internal/expr`)

```go
package expr

// Package-level configuration set by main/arch to avoid circular imports.
// These are used by Simplify() for constant memory folding.
var (
    TextData     []byte  // Binary code being analyzed
    TextOrg      uint32  // Origin address of TextData
    RegisterSize int = 32  // Architecture's register size in bits
)

// SSADefInterface allows type checking SSADef without circular imports.
type SSADefInterface interface {
    IsText() bool
    GetType() string
    GetAddr() int32
}

// ExprType represents the type of expression operation
type ExprType int

// IMPORTANT: These constants use explicit values to match Python exactly.
// Python has gaps in the numbering (e.g., 4 is unused), so iota cannot be used.
// See expr.py:29-112 for the authoritative values.
const (
    CONST        ExprType = 0
    VAR          ExprType = 1
    COMPARE_EQ   ExprType = 2
    COMPARE_GE   ExprType = 3
    // 4 is unused in Python
    SUB          ExprType = 5
    ADD          ExprType = 6
    ADD_PTR      ExprType = 7
    AND          ExprType = 8
    BITFLAGS_N   ExprType = 9
    BITFLAGS_V   ExprType = 10
    OR           ExprType = 11
    // ... continues with explicit values through MUL32 = 93
    // Full list in internal/expr/types.go
)

// Operand can be an integer constant, SSADef pointer, or nested Expr
type Operand interface{}

// Expr represents an expression tree node
type Expr struct {
    Type           ExprType
    Ops            []Operand  // Can be: int, *ssa.SSADef, *Expr
    DontPropagate  bool
    DontEliminate  bool
}

// NewExpr creates a new expression node
// Note: Python takes a list: Expr(ADD, [op1, op2])
// Go uses variadic for convenience: NewExpr(ADD, op1, op2)
func NewExpr(typ ExprType, ops ...Operand) *Expr {
    return &Expr{
        Type: typ,
        Ops:  ops,
    }
}

// Equals performs structural equality comparison
func (e *Expr) Equals(other *Expr) bool {
    if e.Type != other.Type || len(e.Ops) != len(other.Ops) {
        return false
    }
    for i := range e.Ops {
        switch v := e.Ops[i].(type) {
        case *Expr:
            o, ok := other.Ops[i].(*Expr)
            if !ok || !v.Equals(o) {
                return false
            }
        default:
            if e.Ops[i] != other.Ops[i] {
                return false
            }
        }
    }
    return true
}

// GetAllOps returns all leaf operands (non-Expr) recursively
func (e *Expr) GetAllOps() []Operand {
    var ops []Operand
    for _, op := range e.Ops {
        if nested, ok := op.(*Expr); ok {
            ops = append(ops, nested.GetAllOps()...)
        } else {
            ops = append(ops, op)
        }
    }
    return ops
}

// GetAllSubExprs returns all nested Expr nodes recursively
func (e *Expr) GetAllSubExprs() []*Expr {
    var exprs []*Expr
    for _, op := range e.Ops {
        if nested, ok := op.(*Expr); ok {
            exprs = append(exprs, nested)
            exprs = append(exprs, nested.GetAllSubExprs()...)
        }
    }
    return exprs
}

// Copy creates a deep copy of the expression tree
func (e *Expr) Copy() *Expr {
    newOps := make([]Operand, len(e.Ops))
    for i, op := range e.Ops {
        if nested, ok := op.(*Expr); ok {
            newOps[i] = nested.Copy()
        } else {
            newOps[i] = op
        }
    }
    return &Expr{
        Type:          e.Type,
        Ops:           newOps,
        DontPropagate: e.DontPropagate,
        DontEliminate: e.DontEliminate,
    }
}

// Substitute replaces all occurrences of old with new
func (e *Expr) Substitute(old, new Operand, dup bool) *Expr {
    target := e
    if dup {
        target = e.Copy()
    }
    for i := range target.Ops {
        if nested, ok := target.Ops[i].(*Expr); ok {
            target.Ops[i] = nested.Substitute(old, new, false)
        } else if target.Ops[i] == old {
            target.Ops[i] = new
        }
    }
    return target
}

// SubstituteExpr replaces sub-expressions matching old with new
func (e *Expr) SubstituteExpr(old *Expr, new Operand)

// Remove removes an operand from the expression
func (e *Expr) Remove(op Operand)

// Simplify performs algebraic simplification (extensive rules)
func (e *Expr) Simplify()

func (e *Expr) String() string {
    // Format: "(R0(1) + 4)" or "phi(R0(1), R0(2))"
}

// AccessSize returns the bit width for memory operations
func AccessSize(typ ExprType) int {
    switch typ {
    case LOAD32, STORE32, IOIN32, IOOUT32:
        return 32
    case LOAD16, STORE16, IOIN16, IOOUT16:
        return 16
    case LOAD, STORE, IOIN, IOOUT:
        return 8
    default:
        panic("unknown access size for op")
    }
}

// Helper sets for comparison operations
var (
    Compares        = map[ExprType]bool{COMPARE_EQ: true, COMPARE_GE: true, ...}
    SignedCompares  = map[ExprType]bool{COMPARE_GES: true, COMPARE_GTS: true, ...}
    UnsignedCompares = map[ExprType]bool{COMPARE_GE: true, COMPARE_LT: true, ...}
    UnsignedToSigned = map[ExprType]ExprType{COMPARE_GE: COMPARE_GES, ...}
)
```

---

### 5. Control Flow Structuring (`internal/block`)

```go
package block

// BlockType represents the type of advanced block
type BlockType int

const (
    IfThen BlockType = iota
    IfThenElse
    Sequence
    PostLoop
    EmptyLoop
    PreLoop
)

var blockTypeNames = map[BlockType]string{
    IfThen:     "ifthen",
    IfThenElse: "ite",
    Sequence:   "sequence",
    PostLoop:   "ploop",
    EmptyLoop:  "eloop",
    PreLoop:    "prelp",
}

// BasicBlock represents a linear sequence of SSA statements
type BasicBlock struct {
    StartSt     *ssa.SSAStatement
    EndSt       *ssa.SSAStatement
    Next        []*BasicBlock    // Successor blocks (0-2)
    ComeFrom    []*BasicBlock    // Predecessor blocks
    Containered bool             // Part of an AdvancedBlock
    Clipped     bool             // End statement removed (branch)
}

func NewBasicBlock() *BasicBlock {
    return &BasicBlock{
        Next:     make([]*BasicBlock, 0, 2),
        ComeFrom: make([]*BasicBlock, 0),
    }
}

func (b *BasicBlock) Parse(start *ssa.SSAStatement, comeFrom *BasicBlock)
func (b *BasicBlock) Dump(level int)
func (b *BasicBlock) Sdump() string
func (b *BasicBlock) Relink(new *BasicBlock)
func (b *BasicBlock) Recomefrom(old []*BasicBlock, new *BasicBlock)

func (b *BasicBlock) String() string {
    if b.StartSt != nil && b.StartSt.Insn != nil {
        return fmt.Sprintf("bas%X", b.StartSt.Insn.Addr)
    }
    return fmt.Sprintf("bas%p", b)
}

// advancedBlockRegistry tracks which BasicBlocks are actually AdvancedBlocks.
// This is needed for type identification since Go doesn't have runtime type
// information for embedded structs in the same way Python has isinstance().
var advancedBlockRegistry = make(map[*BasicBlock]*AdvancedBlock)

// AdvancedBlock extends BasicBlock with structured control flow
type AdvancedBlock struct {
    BasicBlock
    Type      BlockType
    Blocks    []*BasicBlock   // Contained sub-blocks
    Condition *expr.Expr      // For conditionals/loops
    Prolog    []*ssa.SSAStatement  // Statements before loop condition
}

func NewAdvancedBlock() *AdvancedBlock {
    ab := &AdvancedBlock{
        BasicBlock: BasicBlock{
            Next:     make([]*BasicBlock, 0, 2),
            ComeFrom: make([]*BasicBlock, 0),
        },
        Blocks: make([]*BasicBlock, 0),
    }
    // Register in the advanced block registry for type identification
    advancedBlockRegistry[&ab.BasicBlock] = ab
    return ab
}

func (a *AdvancedBlock) SetBlocks(blocks []*BasicBlock) {
    a.Blocks = blocks
    for _, b := range blocks {
        b.Containered = true
    }
}

func (a *AdvancedBlock) AddBlock(block *BasicBlock)
func (a *AdvancedBlock) Dump(level int)
func (a *AdvancedBlock) Sdump() string

func (a *AdvancedBlock) String() string {
    if a.StartSt != nil && a.StartSt.Insn != nil {
        return fmt.Sprintf("adv%s%X", blockTypeNames[a.Type], a.StartSt.Insn.Addr)
    }
    return fmt.Sprintf("adv%s%p", blockTypeNames[a.Type], a)
}

// Package-level map for block lookup during parsing
var basicBlocks map[*ssa.SSAStatement]*BasicBlock

// ResetBasicBlocks clears the mapping (for tests)
func ResetBasicBlocks()

// ResetAdvancedBlockRegistry clears the registry (for tests)
func ResetAdvancedBlockRegistry()

// Blockify converts an SSA graph to basic blocks
func Blockify(graph *ssa.SSAGraph) *BasicBlock

// Structure performs pattern-matching control flow recovery
// Returns (resultBlock, foundStructure)
// Recognizes 6 patterns: PreLoop, PostLoop (self), IfThenElse, IfThen, Sequence, PostLoop (two-block)
func Structure(block *BasicBlock, done map[*BasicBlock]bool) (*BasicBlock, bool)

// Dump recursively dumps all blocks starting from given block
func Dump(level int, block *BasicBlock, dumped map[*BasicBlock]bool)

// Graphviz exports block structure to DOT format
func Graphviz(blk *BasicBlock, filename string)

// isAdvancedBlock checks if a BasicBlock is actually an AdvancedBlock
func isAdvancedBlock(b *BasicBlock) (*AdvancedBlock, bool)
```

---

### 6. Code Generation (`internal/codegen`)

```go
package codegen

// Code generates C-like pseudocode from structured blocks
type Code struct {
    graph        *ssa.SSAGraph
    symDict      map[uint32]*insn.Symbol
    graphDict    map[uint32]*ssa.SSAGraph

    currentStmt  *ssa.SSAStatement
    retStructCount int

    declareLocals  map[string]localDecl
    declareGlobals map[string]string
    declareArrays  map[string]string

    structs           map[structKey]*ssa.SSAType
    structMembers     map[memberKey]*ssa.SSAType
    structMembersList map[structKey][]structMember  // Members with actual offsets
}

type localDecl struct {
    Type    string
    Init    string  // Optional initializer
}

type structKey struct {
    graph *ssa.SSAGraph
    addr  int32
    size  int32
}

type memberKey struct {
    memberAddr int32  // Member's address
    baseAddr   int32  // Struct base address
    size       int32  // Struct size
}

type structMember struct {
    Type   *ssa.SSAType
    Offset int32  // Actual offset within struct
}

func NewCode() *Code {
    return &Code{
        symDict:           make(map[uint32]*insn.Symbol),
        graphDict:         make(map[uint32]*ssa.SSAGraph),
        declareLocals:     make(map[string]localDecl),
        declareGlobals:    make(map[string]string),
        declareArrays:     make(map[string]string),
        structs:           make(map[structKey]*ssa.SSAType),
        structMembers:     make(map[memberKey]*ssa.SSAType),
        structMembersList: make(map[structKey][]structMember),
    }
}

// Generate generates C code for a function (main entry point)
func (c *Code) Generate(blk *block.BasicBlock, symbol string,
                        symbols map[uint32]*insn.Symbol,
                        graphs []*ssa.SSAGraph,
                        graph *ssa.SSAGraph) string

// Conversion methods
func (c *Code) any2c(any interface{}, prio int, preferHex, implicitGlobal bool) string
func (c *Code) def2c(ssad *ssa.SSADef, prio int, implicitGlobal bool) string
func (c *Code) expr2c(ex *expr.Expr, prio int, preferHex, derefAuto bool) string
func (c *Code) statement2c(st *ssa.SSAStatement, indent int, graph *ssa.SSAGraph, bare bool) string
func (c *Code) getReturns(actualReturns []*ssa.SSADef) (rets, mrets []*ssa.SSADef)
func (c *Code) rets2struct(rets []*ssa.SSADef) string

// Block processing helpers
func (c *Code) doCode(out *strings.Builder, blk *block.BasicBlock, ...)      // Recursive code generation
func (c *Code) doAdvancedBlock(out *strings.Builder, blk *block.AdvancedBlock, ...) // Advanced block handling
func (c *Code) doBasicBlock(out *strings.Builder, blk *block.BasicBlock, ...)   // Basic block handling
func (c *Code) emitGoto(out *strings.Builder, blk *block.BasicBlock, ...)        // Goto emission
func (c *Code) label(blk *block.BasicBlock) string                            // Label generation

// Expression handlers
func (c *Code) handleArgs(ex *expr.Expr, preferHex bool) string    // Function calls
func (c *Code) handleLoad(ex *expr.Expr, preferHex bool) string    // Memory loads
func (c *Code) handleStore(ex *expr.Expr, preferHex bool) string   // Memory stores
func (c *Code) handleIOIn(ex *expr.Expr, preferHex bool) string    // I/O input
func (c *Code) handleIOOut(ex *expr.Expr, preferHex bool) string   // I/O output
func (c *Code) handleCall(st *ssa.SSAStatement, ...) string        // Call statements
func (c *Code) handleReturn(st *ssa.SSAStatement, ...) string      // Return statements

// Struct handling
func (c *Code) getStruct(addr, size int32) string                  // Get/create struct type
func (c *Code) updateStructs()                                      // Populate struct members
func (c *Code) addStructMember(ssad *ssa.SSADef, addr, size int32) // Register struct member

// Package-level helpers
func ind(num int) string                                           // Indentation
func zhex(num uint32) string                                       // Hex format (4 digit)
func zhexSigned(num int32) string                                  // Signed hex format
func memAccessStyle(ops []expr.Operand, typ expr.ExprType) (string, int, int, bool)
func blockComment(indent int, comment string) string               // Comment formatting
func ssaType2C(ssat *ssa.SSAType) string                          // SSA type to C type
func type2DessaName(typ string) string                            // Type to de-SSA name
```

---

### 7. Debug System (`internal/debug`)

```go
package debug

// Debug category constants
type Category int

const (
    SSA Category = iota
    DESSA
    EXPR
    ARGRET
    TRACE
    BLOCK
    CODE
    MAIN
    TYPE
)

var categoryNames = map[Category]string{
    SSA:    "ssa",
    DESSA:  "dessa",
    EXPR:   "expr",
    ARGRET: "argret",
    TRACE:  "trace",
    BLOCK:  "block",
    CODE:   "code",
    MAIN:   "main",
    TYPE:   "type",
}

var (
    Level   int                      // Verbosity 0-6
    Enabled = make(map[Category]bool)
    Out     io.Writer = os.Stdout   // Note: Python uses sys.stdout, not stderr
)

func Enable(categories []string) {
    for _, cat := range categories {
        if cat == "all" {
            for c := range categoryNames {
                Enabled[c] = true
            }
            return
        }
        for c, name := range categoryNames {
            if name == cat {
                Enabled[c] = true
                break
            }
        }
    }
}

func IsEnabled(cat Category, level int) bool {
    return Enabled[cat] && level <= Level
}

func Debug(cat Category, level int, args ...interface{}) {
    if IsEnabled(cat, level) {
        fmt.Fprintln(Out, args...)
    }
}
```

---

## Key Implementation Considerations

### 1. Interface Design for Operands

The Python code uses dynamic typing where expression operands can be `int`, `SSADef`, or `Expr`. In Go, use an empty interface or a dedicated interface:

```go
// Option 1: Empty interface (simpler but less safe)
type Operand interface{}

// Option 2: Sealed interface with type switch (more Go-idiomatic)
type Operand interface {
    operand()  // Unexported method for sealing
}

func (i Int) operand()      {}
func (d *SSADef) operand()  {}
func (e *Expr) operand()    {}

type Int int

// Usage:
switch v := op.(type) {
case Int:
    // Handle integer
case *SSADef:
    // Handle definition
case *Expr:
    // Handle nested expression
}
```

### 2. Graph Traversal Pattern

Replace Python's recursive traversal with iterative or use Go's stack-based approach:

```go
func (g *SSAGraph) GetAll() []*SSAStatement {
    if g.Start == nil {
        return nil
    }

    var all []*SSAStatement
    visited := make(map[*SSAStatement]bool)
    stack := []*SSAStatement{g.Start}

    for len(stack) > 0 {
        st := stack[len(stack)-1]
        stack = stack[:len(stack)-1]

        if visited[st] {
            continue
        }
        visited[st] = true
        all = append(all, st)

        for _, next := range st.Next {
            if !visited[next] {
                stack = append(stack, next)
            }
        }
    }
    return all
}
```

### 3. Context Copying for SSA Construction

The SSA construction requires forking contexts at branch points:

```go
func (c *SSAifyContext) Copy() *SSAifyContext {
    newCtx := &SSAifyContext{
        Graph:        c.Graph,
        Pass:         c.Pass,
        LocalIndices: make(map[DefKey]*SSADef, len(c.LocalIndices)),
    }
    // Shallow copy of map - SSADef pointers are shared intentionally
    for k, v := range c.LocalIndices {
        newCtx.LocalIndices[k] = v
    }
    return newCtx
}
```

### 4. Set Operations

Python uses sets extensively. Use Go maps with empty struct values:

```go
// Set of SSADef
type DefSet map[*SSADef]struct{}

func (s DefSet) Add(d *SSADef)      { s[d] = struct{}{} }
func (s DefSet) Contains(d *SSADef) bool { _, ok := s[d]; return ok }
func (s DefSet) Remove(d *SSADef)   { delete(s, d) }

// Set intersection
func (s DefSet) Intersect(other DefSet) DefSet {
    result := make(DefSet)
    for k := range s {
        if other.Contains(k) {
            result.Add(k)
        }
    }
    return result
}
```

### 5. Expression Simplification

The `Simplify()` method in Python modifies `self` in place and calls itself recursively. In Go:

```go
func (e *Expr) Simplify() {
    // First simplify children
    for i, op := range e.Ops {
        if nested, ok := op.(*Expr); ok {
            nested.Simplify()
            // Unwrap single-element VAR/CONST
            if nested.Type == VAR || nested.Type == CONST {
                e.Ops[i] = nested.Ops[0]
            }
        }
    }

    // Track if we made changes for re-simplification
    changed := true
    for changed {
        changed = false

        // Double NOT elimination
        if e.Type == NOT {
            if inner, ok := e.Ops[0].(*Expr); ok && inner.Type == NOT {
                e.Type = VAR
                e.Ops = []Operand{inner.Ops[0]}
                changed = true
            }
        }

        // ... more simplification rules
    }
}
```

### 6. Architecture-Specific Translation

Use function variables or interfaces for architecture-specific code:

```go
// Option 1: Function variable (as in Python)
type TranslateFunc func(*SSAGraph, *SSAifyContext, *insn.Insn, int32, int32, int32) (
    *SSAStatement, *SSAStatement, int32, int32, int32, []*insn.Insn)

// Option 2: Interface (more Go-idiomatic)
type ArchTranslator interface {
    Translate(g *SSAGraph, ctx *SSAifyContext, ins *insn.Insn,
              sp, endBP, bp int32) TranslateResult
    GuessEntryPoints(text []byte, org uint32, manual []uint32) []uint32
}

type TranslateResult struct {
    Start, End           *SSAStatement
    SP, BP, EndBP        int32
    NextOverride         []*insn.Insn
}
```

### 7. Avoiding Circular Imports

The Python code freely imports across modules, but Go requires acyclic package dependencies.
Key patterns used in this port:

```go
// Problem: arch imports insn, insn imports expr, expr needs arch data
// Solution: Use package-level variables in expr, set from main

// In internal/expr/simplify.go:
var (
    TextData     []byte   // Set by main after loading binary
    TextOrg      uint32   // Set by main
    RegisterSize int = 32 // Set by main from arch.Current.RegisterSize
)

// In internal/arch/arm/arm.go (separate package from arch):
// ARM-specific code that can import both arch and ssa without cycles
func Register() {
    if arch.Current != nil && arch.Current.Name == "arm" {
        arch.Current.Trace = TraceARM
        arch.Current.GuessEntryPoints = GuessARMEntryPoints
    }
}

// In cmd/decomp/main.go:
func main() {
    arch.SetArch("arm")
    arm.Register()  // Wire up ARM functions after arch is set
    expr.RegisterSize = arch.Current.RegisterSize
    expr.TextData = binaryData
    expr.TextOrg = origin
}
```

This "registration" pattern allows architecture-specific packages to depend on core
packages while the core packages remain independent.

---

## Error Handling

Replace Python exceptions with Go's error handling:

```go
// errors.go
package decomp

import "errors"

var (
    ErrInternalError = errors.New("internal error")
    ErrUserError     = errors.New("user error")
)

type InternalError struct {
    Message string
}

func (e InternalError) Error() string {
    return "internal error: " + e.Message
}

type UserError struct {
    Message string
}

func (e UserError) Error() string {
    return "user error: " + e.Message
}
```

---

## Testing Strategy

1. **Unit tests** for each package:
   - `expr_test.go`: Test expression simplification rules
   - `ssa_test.go`: Test SSA construction, DCE, propagation
   - `block_test.go`: Test control flow structuring patterns

2. **Integration tests** using the existing test binaries:
   ```go
   func TestDecompile(t *testing.T) {
       testFiles, _ := filepath.Glob("testdata/*.bin")
       for _, f := range testFiles {
           t.Run(f, func(t *testing.T) {
               // Parse test filename for origin, entry, mmio
               // Run decompiler
               // Compare output with golden file
           })
       }
   }
   ```

3. **Fuzzing** for expression simplification and binary parsing

---

## Migration Path

1. **Phase 1**: Core data structures (`insn`, `ssa`, `expr`) ✅ COMPLETE
   - `internal/insn/insn.go`, `symbol.go` - Instruction and symbol types
   - `internal/ssa/statement.go`, `def.go`, `graph.go`, `type.go`, `cache.go`
   - `internal/expr/types.go`, `expr.go` - Expression tree with all operations
   - `internal/arch/arch.go` - Architecture abstraction
   - `internal/debug/debug.go` - Debug logging system
   - `pkg/errors/errors.go` - Error types

2. **Phase 2**: Architecture-independent SSA transforms ✅ COMPLETE
   - `internal/ssa/dce.go` - Dead code elimination with phi loop detection
   - `internal/ssa/propagate.go` - Constant/copy propagation, depropagation
   - `internal/ssa/dessa.go` - De-SSA transformation
   - `internal/ssa/types.go` - Type recovery (simple and compound)
   - `internal/ssa/analysis.go` - FindDefinitions, FindArgs, FindRets, Dereach, Dump, Simplify
   - `internal/expr/simplify.go` - Expression simplification (21 rules)

3. **Phase 3**: Architecture-specific tracing and translation (start with ARM) ✅ COMPLETE
   - `internal/arch/arm/arm.go` - ARM instruction tracing, SSA translation, entry point guessing
   - `internal/arch/arch.go` - TraceFunc and GuessEntryPointsFunc type definitions
   - `internal/insn/insn.go` - ARM-specific Insn fields (Cond, Op, Rn, Rd, etc.)
   - `internal/expr/simplify.go` - Package-level TextData, TextOrg, RegisterSize (to avoid circular imports)
   - Note: ARM functions registered at runtime via `arm.Register()` to avoid import cycles

4. **Phase 4**: Control flow structuring ✅ COMPLETE
   - `internal/block/basic.go` - BasicBlock with Parse, Relink, Recomefrom, Dump, Sdump
   - `internal/block/advanced.go` - AdvancedBlock (if-then-else, loops, sequences), advancedBlockRegistry
   - `internal/block/structure.go` - Blockify, Structure (6 patterns), Dump, Graphviz
   - Note: advancedBlockRegistry added to identify AdvancedBlocks (Go lacks Python's isinstance())

5. **Phase 5**: Code generation ✅ COMPLETE
   - `internal/codegen/code.go` - C-like pseudocode generation
   - Code struct with expression/statement/block conversion
   - Helper functions: ind, zhex, zhexSigned, ssaType2C, blockComment, memAccessStyle
   - any2c, def2c, expr2c methods for expression conversion
   - statement2c for statement conversion
   - Generate() main method for block processing
   - Support for all expression types (comparisons, arithmetic, bitwise, shifts, flags, I/O, memory)
   - Declaration tracking (locals, globals, arrays, structs)
   - Control flow structures (if-then-else, loops, sequences, gotos)
   - 30 unit tests in code_test.go

6. **Phase 6**: 6502 architecture support ✅ COMPLETE
   - `internal/arch/mos6502/mos6502.go` - Registration entry point
   - `internal/arch/mos6502/decode.go` - Instruction decoding:
     - InsnSize - instruction size determination (1, 2, or 3 bytes)
     - IsIllegalOpcode - illegal opcode detection
     - disas6502 - full disassembly for all addressing modes
   - `internal/arch/mos6502/trace.go` - Control flow tracing:
     - Trace6502 - control flow tracing matching Python insn_6502.py
     - Guess6502EntryPoints - stub for entry point discovery
   - `internal/arch/mos6502/translate.go` - SSA translation:
     - Translate6502 - SSA translation for ~150 opcodes
     - Flag chain helpers (chainFlagsLd, chainFlagsIncDec, etc.)
   - `internal/arch/mos6502/mos6502_test.go` - 24 unit tests covering:
     - Instruction sizing (all opcode classes)
     - Disassembly (all addressing modes)
     - Tracing (branches, JSR, JMP indirect, out of range)
     - SSA translation (loads, stores, arithmetic, flags, stack ops)

7. **Phase 7**: CLI and integration ✅ COMPLETE
   - `cmd/decomp/main.go` - Full command-line interface
   - `internal/ssa/ssaify.go` - SSAify and IdentifyReturns functions
   - Implemented features:
     - Binary file loading
     - Command-line argument parsing (-o/-origin, -e/-entries, -i/-io-ranges, -a/-arch, -g/-guess, -s/-symbols, -d/-debug, -v/-debug-level, -f/-debug-file, --version)
     - Integration of MCodeGraph.TraceAll with arch-specific tracers
     - SSAify calls for each traced function (two-pass analysis)
     - IdentifyReturns for cross-function return value analysis
     - Block structuring via Blockify and iterative Structure
     - Code generation via codegen.Code.Generate
     - Symbol table loading from CSV files
     - MMIO range parsing (ranges and single addresses)
     - Debug output configuration (file, categories, level)
     - Default entry point detection (6502 vectors, origin fallback)

8. **Phase 8**: Integration test infrastructure ✅ COMPLETE
   - `test/build.sh` - ACME assembler build script
   - `test/src/*.asm` - Simple 6502 assembly test cases:
     - simple_load.asm - LDA, STA, LDX, STX, LDY, STY
     - arithmetic.asm - ADC, SBC, INC, DEC, INX, DEY
     - branch.asm - BEQ, BNE conditional branches
     - jump.asm - JMP, JSR, RTS control flow
     - loop.asm - Simple DEX/BNE loop pattern
   - `test/bin/` - Compiled binaries (naming: name.8000.8000.default.bin)
   - `.gitignore` - Excludes decomp binary, test/bin/, test_results/

Each phase should maintain compatibility with the Python version for comparison testing.
