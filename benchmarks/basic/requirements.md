A simplified old basic interpreter for .bas files.

# Target

* Language: Golang
* Usage: `basic [-debug] <filename.bas>`

# Supported Statements

* PRINT - output to stdout; accepts one or more expressions or string literals separated by `;` (trailing semicolon suppresses newline)
* INPUT - read from stdin into variable
* Assignment - variable definition and assignment are implicit via `<var> = <expr>`
* FOR/NEXT - loop using `FOR <var> = <start> TO <end>` and `NEXT <var>` (step is always 1)
* IF/THEN - conditional; `THEN` is followed by an inline statement or list of statements (no ELSE support)
* GOTO - jump to line number
* END - terminate program
* REM - comments

# Expressions

* Arithmetic: `+`, `-`, `*`, `/`
* Comparison: `=`, `<>`, `<`, `>`, `<=`, `>=`
* Unary negation: `-`
* Standard arithmetic precedence: unary negation, then `*` and `/`, then `+` and `-`
* Parentheses for grouping and overriding precedence
* String literals in double quotes, e.g. `"hello"`

# Variables

* Numeric variable names do not end with `$` (e.g., `X`) - default to 0
* String variable names must end with `$` (e.g., `N$`) - default to ""
* Case-insensitive names

# Program Structure

* Each line starts with a line number
* Multiple statements per line separated by `:`
* Lines execute in numeric order
* Keywords are case-insensitive and do not require a space before the next token, e.g. `PRINT"hello"`

# CLI Options

* `-debug` - print all variables and values after execution

# Examples

* Example files in examples directory: example1.bas - example12.bas
