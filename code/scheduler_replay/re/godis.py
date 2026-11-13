"""godis.py BIN FUNC_REGEX [maxlines]: disassemble Go functions found via pclntab; annotate rodata float64/float32 constants."""
import os, subprocess, sys, re, struct
from elftools.elf.elffile import ELFFile
GOFUNCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gofuncs", "gofuncs")  # go build -o gofuncs ./gofuncs
b, pat = sys.argv[1], sys.argv[2]; mx = int(sys.argv[3]) if len(sys.argv) > 3 else 400
fs = subprocess.run([GOFUNCS, b, pat], capture_output=True, text=True).stdout.splitlines()
allf = {int(l.split()[0],16): l.split()[2] for l in subprocess.run([GOFUNCS, b, "."], capture_output=True, text=True).stdout.splitlines()}
elf = ELFFile(open(b, "rb")); secs = [s for s in elf.iter_sections() if s['sh_addr']]
def rd(addr, n):
    for s in secs:
        if s['sh_addr'] <= addr < s['sh_addr'] + s['sh_size'] and s['sh_type'] != 'SHT_NOBITS':
            o = addr - s['sh_addr']; return s.data()[o:o+n]
for line in fs:
    a, e, name = line.split()[:3]
    print(f"### {name}  [{a}-{e}]  {line.split(chr(9))[1] if chr(9) in line else ''}")
    out = subprocess.run(["objdump", "-d", "--no-show-raw-insn", "-M", "intel", f"--start-address={a}", f"--stop-address={e}", b], capture_output=True, text=True).stdout.splitlines()
    n = 0
    for l in out:
        if not re.match(r"\s+[0-9a-f]+:", l): continue
        ann = ""
        m = re.search(r"(QWORD|DWORD) PTR \[rip\+0x[0-9a-f]+\]\s+#\s+(?:0x)?([0-9a-f]+)", l)
        if m and re.search(r"\b(movsd|mulsd|divsd|addsd|subsd|u?comisd|maxsd|minsd|movss|mulss|movsd)\b", l):
            addr = int(m.group(2), 16); w = rd(addr, 8 if m.group(1) == "QWORD" else 4)
            if w: ann = f"   ; const={struct.unpack('<d' if len(w)==8 else '<f', w)[0]!r}"
        m2 = re.search(r"\blea\s+\w+,\[rip\+0x[0-9a-f]+\]\s+#\s+(?:0x)?([0-9a-f]+)", l)
        if m2:
            w = rd(int(m2.group(1), 16), 40)
            if w and sum(32 <= c < 127 for c in w[:12]) == 12: ann = "   ; str~" + repr(bytes(c if 32 <= c < 127 else 46 for c in w).decode())
        mc = re.search(r"\bcall\s+([0-9a-f]+)", l)
        if mc and int(mc.group(1),16) in allf: l = re.sub(r"<[^>]*>", "", l) + "  -> " + allf[int(mc.group(1),16)].split("/")[-1]
        print(l.strip() + ann); n += 1
        if n >= mx: print("..."); break
