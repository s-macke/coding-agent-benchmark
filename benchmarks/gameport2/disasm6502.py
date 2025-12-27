#!/usr/bin/env python3
"""Flow-following 6502 disassembler for C64 PRG files"""

import sys
import re
from collections import deque

# 6502 opcodes: (mnemonic, addressing mode, bytes, flow_type)
# flow_type: "normal", "branch", "jump", "call", "return", "break"
OPCODES = {
    0x00: ("BRK", "IMP", 1, "break"),
    0x01: ("ORA", "IDX", 2, "normal"),
    0x05: ("ORA", "ZP", 2, "normal"),
    0x06: ("ASL", "ZP", 2, "normal"),
    0x08: ("PHP", "IMP", 1, "normal"),
    0x09: ("ORA", "IMM", 2, "normal"),
    0x0A: ("ASL", "ACC", 1, "normal"),
    0x0D: ("ORA", "ABS", 3, "normal"),
    0x0E: ("ASL", "ABS", 3, "normal"),
    0x10: ("BPL", "REL", 2, "branch"),
    0x11: ("ORA", "IDY", 2, "normal"),
    0x15: ("ORA", "ZPX", 2, "normal"),
    0x16: ("ASL", "ZPX", 2, "normal"),
    0x18: ("CLC", "IMP", 1, "normal"),
    0x19: ("ORA", "ABY", 3, "normal"),
    0x1D: ("ORA", "ABX", 3, "normal"),
    0x1E: ("ASL", "ABX", 3, "normal"),
    0x20: ("JSR", "ABS", 3, "call"),
    0x21: ("AND", "IDX", 2, "normal"),
    0x24: ("BIT", "ZP", 2, "normal"),
    0x25: ("AND", "ZP", 2, "normal"),
    0x26: ("ROL", "ZP", 2, "normal"),
    0x28: ("PLP", "IMP", 1, "normal"),
    0x29: ("AND", "IMM", 2, "normal"),
    0x2A: ("ROL", "ACC", 1, "normal"),
    0x2C: ("BIT", "ABS", 3, "normal"),
    0x2D: ("AND", "ABS", 3, "normal"),
    0x2E: ("ROL", "ABS", 3, "normal"),
    0x30: ("BMI", "REL", 2, "branch"),
    0x31: ("AND", "IDY", 2, "normal"),
    0x35: ("AND", "ZPX", 2, "normal"),
    0x36: ("ROL", "ZPX", 2, "normal"),
    0x38: ("SEC", "IMP", 1, "normal"),
    0x39: ("AND", "ABY", 3, "normal"),
    0x3D: ("AND", "ABX", 3, "normal"),
    0x3E: ("ROL", "ABX", 3, "normal"),
    0x40: ("RTI", "IMP", 1, "return"),
    0x41: ("EOR", "IDX", 2, "normal"),
    0x45: ("EOR", "ZP", 2, "normal"),
    0x46: ("LSR", "ZP", 2, "normal"),
    0x48: ("PHA", "IMP", 1, "normal"),
    0x49: ("EOR", "IMM", 2, "normal"),
    0x4A: ("LSR", "ACC", 1, "normal"),
    0x4C: ("JMP", "ABS", 3, "jump"),
    0x4D: ("EOR", "ABS", 3, "normal"),
    0x4E: ("LSR", "ABS", 3, "normal"),
    0x50: ("BVC", "REL", 2, "branch"),
    0x51: ("EOR", "IDY", 2, "normal"),
    0x55: ("EOR", "ZPX", 2, "normal"),
    0x56: ("LSR", "ZPX", 2, "normal"),
    0x58: ("CLI", "IMP", 1, "normal"),
    0x59: ("EOR", "ABY", 3, "normal"),
    0x5D: ("EOR", "ABX", 3, "normal"),
    0x5E: ("LSR", "ABX", 3, "normal"),
    0x60: ("RTS", "IMP", 1, "return"),
    0x61: ("ADC", "IDX", 2, "normal"),
    0x65: ("ADC", "ZP", 2, "normal"),
    0x66: ("ROR", "ZP", 2, "normal"),
    0x68: ("PLA", "IMP", 1, "normal"),
    0x69: ("ADC", "IMM", 2, "normal"),
    0x6A: ("ROR", "ACC", 1, "normal"),
    0x6C: ("JMP", "IND", 3, "jump_indirect"),
    0x6D: ("ADC", "ABS", 3, "normal"),
    0x6E: ("ROR", "ABS", 3, "normal"),
    0x70: ("BVS", "REL", 2, "branch"),
    0x71: ("ADC", "IDY", 2, "normal"),
    0x75: ("ADC", "ZPX", 2, "normal"),
    0x76: ("ROR", "ZPX", 2, "normal"),
    0x78: ("SEI", "IMP", 1, "normal"),
    0x79: ("ADC", "ABY", 3, "normal"),
    0x7D: ("ADC", "ABX", 3, "normal"),
    0x7E: ("ROR", "ABX", 3, "normal"),
    0x81: ("STA", "IDX", 2, "normal"),
    0x84: ("STY", "ZP", 2, "normal"),
    0x85: ("STA", "ZP", 2, "normal"),
    0x86: ("STX", "ZP", 2, "normal"),
    0x88: ("DEY", "IMP", 1, "normal"),
    0x8A: ("TXA", "IMP", 1, "normal"),
    0x8C: ("STY", "ABS", 3, "normal"),
    0x8D: ("STA", "ABS", 3, "normal"),
    0x8E: ("STX", "ABS", 3, "normal"),
    0x90: ("BCC", "REL", 2, "branch"),
    0x91: ("STA", "IDY", 2, "normal"),
    0x94: ("STY", "ZPX", 2, "normal"),
    0x95: ("STA", "ZPX", 2, "normal"),
    0x96: ("STX", "ZPY", 2, "normal"),
    0x98: ("TYA", "IMP", 1, "normal"),
    0x99: ("STA", "ABY", 3, "normal"),
    0x9A: ("TXS", "IMP", 1, "normal"),
    0x9D: ("STA", "ABX", 3, "normal"),
    0xA0: ("LDY", "IMM", 2, "normal"),
    0xA1: ("LDA", "IDX", 2, "normal"),
    0xA2: ("LDX", "IMM", 2, "normal"),
    0xA4: ("LDY", "ZP", 2, "normal"),
    0xA5: ("LDA", "ZP", 2, "normal"),
    0xA6: ("LDX", "ZP", 2, "normal"),
    0xA8: ("TAY", "IMP", 1, "normal"),
    0xA9: ("LDA", "IMM", 2, "normal"),
    0xAA: ("TAX", "IMP", 1, "normal"),
    0xAC: ("LDY", "ABS", 3, "normal"),
    0xAD: ("LDA", "ABS", 3, "normal"),
    0xAE: ("LDX", "ABS", 3, "normal"),
    0xB0: ("BCS", "REL", 2, "branch"),
    0xB1: ("LDA", "IDY", 2, "normal"),
    0xB4: ("LDY", "ZPX", 2, "normal"),
    0xB5: ("LDA", "ZPX", 2, "normal"),
    0xB6: ("LDX", "ZPY", 2, "normal"),
    0xB8: ("CLV", "IMP", 1, "normal"),
    0xB9: ("LDA", "ABY", 3, "normal"),

    0xBA: ("TSX", "IMP", 1, "normal"),
    0xBC: ("LDY", "ABX", 3, "normal"),
    0xBD: ("LDA", "ABX", 3, "normal"),
    0xBE: ("LDX", "ABY", 3, "normal"),
    0xC0: ("CPY", "IMM", 2, "normal"),
    0xC1: ("CMP", "IDX", 2, "normal"),
    0xC4: ("CPY", "ZP", 2, "normal"),
    0xC5: ("CMP", "ZP", 2, "normal"),
    0xC6: ("DEC", "ZP", 2, "normal"),
    0xC8: ("INY", "IMP", 1, "normal"),
    0xC9: ("CMP", "IMM", 2, "normal"),
    0xCA: ("DEX", "IMP", 1, "normal"),
    0xCC: ("CPY", "ABS", 3, "normal"),
    0xCD: ("CMP", "ABS", 3, "normal"),
    0xCE: ("DEC", "ABS", 3, "normal"),
    0xD0: ("BNE", "REL", 2, "branch"),
    0xD1: ("CMP", "IDY", 2, "normal"),
    0xD5: ("CMP", "ZPX", 2, "normal"),
    0xD6: ("DEC", "ZPX", 2, "normal"),
    0xD8: ("CLD", "IMP", 1, "normal"),
    0xD9: ("CMP", "ABY", 3, "normal"),
    0xDD: ("CMP", "ABX", 3, "normal"),
    0xDE: ("DEC", "ABX", 3, "normal"),
    0xE0: ("CPX", "IMM", 2, "normal"),
    0xE1: ("SBC", "IDX", 2, "normal"),
    0xE4: ("CPX", "ZP", 2, "normal"),
    0xE5: ("SBC", "ZP", 2, "normal"),
    0xE6: ("INC", "ZP", 2, "normal"),
    0xE8: ("INX", "IMP", 1, "normal"),
    0xE9: ("SBC", "IMM", 2, "normal"),
    0xEA: ("NOP", "IMP", 1, "normal"),
    0xEC: ("CPX", "ABS", 3, "normal"),
    0xED: ("SBC", "ABS", 3, "normal"),
    0xEE: ("INC", "ABS", 3, "normal"),
    0xF0: ("BEQ", "REL", 2, "branch"),
    0xF1: ("SBC", "IDY", 2, "normal"),
    0xF5: ("SBC", "ZPX", 2, "normal"),
    0xF6: ("INC", "ZPX", 2, "normal"),
    0xF8: ("SED", "IMP", 1, "normal"),
    0xF9: ("SBC", "ABY", 3, "normal"),
    0xFD: ("SBC", "ABX", 3, "normal"),
    0xFE: ("INC", "ABX", 3, "normal"),
}

def format_operand(mode, operand_bytes, pc):
    """Format the operand based on addressing mode"""
    if mode == "IMP" or mode == "ACC":
        return "", None
    elif mode == "IMM":
        return f"#${operand_bytes[0]:02X}", None
    elif mode == "ZP":
        return f"${operand_bytes[0]:02X}", None
    elif mode == "ZPX":
        return f"${operand_bytes[0]:02X},X", None
    elif mode == "ZPY":
        return f"${operand_bytes[0]:02X},Y", None
    elif mode == "ABS":
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        return f"${addr:04X}", addr
    elif mode == "ABX":
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        return f"${addr:04X},X", None
    elif mode == "ABY":
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        return f"${addr:04X},Y", None
    elif mode == "IND":
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        return f"(${addr:04X})", None
    elif mode == "IDX":
        return f"(${operand_bytes[0]:02X},X)", None
    elif mode == "IDY":
        return f"(${operand_bytes[0]:02X}),Y", None
    elif mode == "REL":
        offset = operand_bytes[0] if operand_bytes[0] < 128 else operand_bytes[0] - 256
        target = pc + 2 + offset
        return f"${target:04X}", target
    return "", None


class FlowDisassembler:
    def __init__(self, data, load_addr):
        self.data = data
        self.load_addr = load_addr
        self.end_addr = load_addr + len(data)

        # Track what we've found
        self.code_addresses = set()      # Addresses that are code
        self.data_addresses = set()      # Addresses that are data
        self.labels = {}                 # addr -> label name
        self.instructions = {}           # addr -> (bytes, mnemonic, operand, target)
        self.entry_points = []           # List of entry points

    def addr_to_offset(self, addr):
        """Convert memory address to data offset"""
        return addr - self.load_addr

    def is_valid_addr(self, addr):
        """Check if address is within our data range"""
        return self.load_addr <= addr < self.end_addr

    def get_byte(self, addr):
        """Get byte at address"""
        if not self.is_valid_addr(addr):
            return None
        return self.data[self.addr_to_offset(addr)]

    def get_bytes(self, addr, count):
        """Get multiple bytes starting at address"""
        offset = self.addr_to_offset(addr)
        if offset < 0 or offset + count > len(self.data):
            return None
        return self.data[offset:offset + count]

    def find_sys_entry(self):
        """Look for BASIC SYS command to find entry point"""
        # Look for pattern: 9E (SYS token) followed by ASCII digits
        for i in range(len(self.data) - 6):
            if self.data[i] == 0x9E:  # SYS token
                # Read ASCII digits
                j = i + 1
                num_str = ""
                while j < len(self.data) and 0x30 <= self.data[j] <= 0x39:
                    num_str += chr(self.data[j])
                    j += 1
                if num_str:
                    return int(num_str)
        return None

    def add_label(self, addr, prefix="L"):
        """Add a label for an address"""
        if addr not in self.labels:
            self.labels[addr] = f"{prefix}_{addr:04X}"

    def trace_flow(self, start_addr):
        """Trace code flow from a starting address"""
        queue = deque([start_addr])

        while queue:
            addr = queue.popleft()

            # Skip if already processed or invalid
            if addr in self.code_addresses:
                continue
            if not self.is_valid_addr(addr):
                continue

            # Disassemble instruction at this address
            opcode = self.get_byte(addr)
            if opcode is None:
                continue

            if opcode not in OPCODES:
                # Unknown opcode - stop this flow
                self.data_addresses.add(addr)
                continue

            mnemonic, mode, size, flow_type = OPCODES[opcode]

            # Get instruction bytes
            instr_bytes = self.get_bytes(addr, size)
            if instr_bytes is None:
                continue

            # Mark as code
            for i in range(size):
                self.code_addresses.add(addr + i)

            # Format operand and get target address
            operand_bytes = instr_bytes[1:] if size > 1 else []
            operand_str, target = format_operand(mode, operand_bytes, addr)

            # Store instruction
            self.instructions[addr] = (instr_bytes, mnemonic, operand_str, target)

            # Add label for branch/jump targets
            if target is not None and self.is_valid_addr(target):
                self.add_label(target)

            # Determine next addresses to trace
            next_addr = addr + size

            if flow_type == "normal":
                # Continue to next instruction
                queue.append(next_addr)

            elif flow_type == "branch":
                # Conditional branch: trace both paths
                queue.append(next_addr)  # Fall through
                if target is not None:
                    queue.append(target)  # Branch taken

            elif flow_type == "jump":
                # Unconditional jump: only trace target
                if target is not None:
                    queue.append(target)

            elif flow_type == "jump_indirect":
                # Indirect jump: can't follow statically
                pass

            elif flow_type == "call":
                # JSR: trace both the subroutine and return path
                queue.append(next_addr)  # Return address
                if target is not None:
                    queue.append(target)  # Subroutine
                    self.add_label(target, "SUB")

            elif flow_type == "return" or flow_type == "break":
                # RTS/RTI/BRK: end of this flow
                pass

    def disassemble(self, entry_points=None):
        """Main disassembly routine"""
        # Find entry points
        if entry_points is None:
            entry_points = []

            # Try to find SYS entry
            sys_addr = self.find_sys_entry()
            if sys_addr and self.is_valid_addr(sys_addr):
                entry_points.append(sys_addr)
                self.add_label(sys_addr, "START")

            # Also start from load address
            if self.load_addr not in entry_points:
                entry_points.insert(0, self.load_addr)
                self.add_label(self.load_addr, "ENTRY")

        self.entry_points = entry_points

        # Trace flow from each entry point
        for entry in entry_points:
            self.trace_flow(entry)

        return self.generate_output()

    def generate_output(self):
        """Generate the assembly output"""
        lines = []
        lines.append(f"; Flow-following disassembly")
        lines.append(f"; Load address: ${self.load_addr:04X}")
        lines.append(f"; End address: ${self.end_addr:04X}")
        lines.append(f"; Size: {len(self.data)} bytes")
        lines.append(f"; Code bytes: {len(self.code_addresses)}")
        lines.append(f"; Entry points: {', '.join(f'${e:04X}' for e in self.entry_points)}")
        lines.append("")

        addr = self.load_addr
        in_data_block = False
        data_block_start = None
        data_bytes = []

        while addr < self.end_addr:
            # Check if this is a labeled address
            if addr in self.labels:
                # Flush any pending data block
                if in_data_block and data_bytes:
                    lines.append(self.format_data_block(data_block_start, data_bytes))
                    data_bytes = []
                    in_data_block = False
                lines.append("")
                lines.append(f"{self.labels[addr]}:")

            if addr in self.instructions:
                # Flush any pending data block
                if in_data_block and data_bytes:
                    lines.append(self.format_data_block(data_block_start, data_bytes))
                    data_bytes = []
                    in_data_block = False

                # Output instruction
                instr_bytes, mnemonic, operand_str, target = self.instructions[addr]

                # Use label if target has one
                if target is not None and target in self.labels:
                    operand_str = self.labels[target]

                if operand_str:
                    lines.append(f"    {mnemonic:4} {operand_str}")
                else:
                    lines.append(f"    {mnemonic}")

                addr += len(instr_bytes)
            else:
                # Data byte
                if not in_data_block:
                    in_data_block = True
                    data_block_start = addr
                    data_bytes = []

                byte_val = self.get_byte(addr)
                if byte_val is not None:
                    data_bytes.append(byte_val)
                addr += 1

                # Flush data block periodically or at labeled addresses
                if len(data_bytes) >= 16 or (addr in self.labels):
                    lines.append(self.format_data_block(data_block_start, data_bytes))
                    data_bytes = []
                    in_data_block = False

        # Flush final data block
        if in_data_block and data_bytes:
            lines.append(self.format_data_block(data_block_start, data_bytes))

        return "\n".join(lines)

    def format_data_block(self, start_addr, data_bytes):
        """Format a block of data bytes"""
        hex_str = ", ".join(f"${b:02X}" for b in data_bytes)

        # Also show ASCII representation
        ascii_str = ""
        for b in data_bytes:
            if 0x20 <= b < 0x7F:
                ascii_str += chr(b)
            else:
                ascii_str += "."

        return f"    .BYTE {hex_str}  ; {ascii_str}"


def main():
    if len(sys.argv) < 2:
        print("Usage: disasm6502.py <file.bin> [entry_point_hex ...]")
        print("  entry_point_hex: Additional entry points in hex (e.g., 0E16)")
        sys.exit(1)

    filename = sys.argv[1]

    with open(filename, "rb") as f:
        data = f.read()

    # C64 PRG format: first two bytes are load address (little-endian)
    load_addr = data[0] | (data[1] << 8)
    code = data[2:]

    # Parse additional entry points from command line
    extra_entries = []
    for arg in sys.argv[2:]:
        try:
            extra_entries.append(int(arg, 16))
        except ValueError:
            print(f"Warning: Invalid hex entry point '{arg}', skipping")

    disasm = FlowDisassembler(code, load_addr)

    # Add any extra entry points
    entry_points = None
    if extra_entries:
        sys_addr = disasm.find_sys_entry()
        entry_points = [load_addr]
        if sys_addr and disasm.is_valid_addr(sys_addr):
            entry_points.append(sys_addr)
        entry_points.extend(extra_entries)

    output = disasm.disassemble(entry_points)
    print(output)


if __name__ == "__main__":
    main()