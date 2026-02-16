package disasm86

import "fmt"

// SliceSource provides ByteSource over a flat []byte memory image.
type SliceSource struct {
	Data []byte
}

func (s SliceSource) ByteAt(addr uint32) (byte, error) {
	if addr >= uint32(len(s.Data)) {
		return 0, fmt.Errorf("address 0x%X out of range", addr)
	}
	return s.Data[addr], nil
}
