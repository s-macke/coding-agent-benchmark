package main

type IntStack struct {
	data []int
}

func (s *IntStack) Push(v int) {
	s.data = append(s.data, v)
}

func (s *IntStack) Pop() int {
	n := len(s.data) - 1
	v := s.data[n]
	s.data = s.data[:n]
	return v
}
