#!/bin/bash
# Compile all .asm files in src/ to bin/ using ACME

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SCRIPT_DIR/bin"

for src in "$SCRIPT_DIR/src/"*.asm; do
    name=$(basename "$src" .asm)
    out="$SCRIPT_DIR/bin/${name}.8000.8000.default.bin"
    echo "Building $name..."
    acme -f plain -o "$out" "$src"
done

echo "Done."
