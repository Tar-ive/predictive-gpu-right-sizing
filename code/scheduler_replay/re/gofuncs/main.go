// gofuncs: list Go functions (name, start, end) from .gopclntab, works on stripped ELF binaries.
package main

import (
	"encoding/binary"
	"debug/elf"
	"debug/gosym"
	"fmt"
	"os"
	"regexp"
)

func main() {
	f, err := elf.Open(os.Args[1])
	if err != nil {
		panic(err)
	}
	pcl := f.Section(".gopclntab")
	data, _ := pcl.Data()
	text := f.Section(".text")
	start := text.Addr
	if ts := binary.LittleEndian.Uint64(data[24:32]); ts != 0 {
		start = ts // go1.18+ pcHeader.textStart (runtime.text); differs from .text when cgo code precedes Go code
	}
	tab, err := gosym.NewTable(nil, gosym.NewLineTable(data, start))
	if err != nil {
		panic(err)
	}
	re := regexp.MustCompile(os.Args[2])
	for _, fn := range tab.Funcs {
		if re.MatchString(fn.Name) {
			file, line, _ := tab.PCToLine(fn.Entry)
			fmt.Printf("%#x %#x %s\t%s:%d\n", fn.Entry, fn.End, fn.Name, file, line)
		}
	}
}
