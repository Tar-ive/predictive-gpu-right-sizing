"""Remote ZIP reader over HTTP Range: list members, open stored members as seekable files."""
import io, struct, zlib, requests, functools
S = requests.Session()

def rng(url, a, b):
    r = S.get(url, headers={"Range": f"bytes={a}-{b-1}"}, timeout=300); r.raise_for_status()
    assert len(r.content) == b - a, (len(r.content), b - a)
    return r.content

@functools.lru_cache(None)
def size(url):
    return int(S.head(url, timeout=60).headers["Content-Length"])

def members(url):
    n = size(url); tail = rng(url, n - 65536 - 22, n)
    i = tail.rfind(b"PK\x05\x06"); eocd = tail[i:]
    cd_n, cd_size, cd_off = struct.unpack("<HII", eocd[10:20])[0], *struct.unpack("<II", eocd[12:20])
    cd_n = struct.unpack("<H", eocd[10:12])[0]
    j = tail.rfind(b"PK\x06\x06")
    if j >= 0:
        z = tail[j:]; cd_n, cd_size, cd_off = struct.unpack("<QQQ", z[32:56])
    cd = rng(url, cd_off, cd_off + cd_size); out = []; p = 0
    while p < len(cd) and cd[p:p+4] == b"PK\x01\x02":
        method = struct.unpack("<H", cd[p+10:p+12])[0]
        csz, usz = struct.unpack("<II", cd[p+20:p+28]); fl, el, cl = struct.unpack("<HHH", cd[p+28:p+34])
        lho = struct.unpack("<I", cd[p+42:p+46])[0]; name = cd[p+46:p+46+fl].decode()
        ex = cd[p+46+fl:p+46+fl+el]; q = 0
        while q < len(ex):
            hid, hl = struct.unpack("<HH", ex[q:q+4]); body = ex[q+4:q+4+hl]
            if hid == 1:
                vals = []; k = 0
                for v, w in ((usz, 0xFFFFFFFF), (csz, 0xFFFFFFFF), (lho, 0xFFFFFFFF)):
                    if v == w: vals.append(struct.unpack("<Q", body[k:k+8])[0]); k += 8
                    else: vals.append(v)
                usz, csz, lho = vals
            q += 4 + hl
        out.append(dict(name=name, method=method, csize=csz, usize=usz, lho=lho)); p += 46 + fl + el + cl
    return out

def data_offset(url, m):
    h = rng(url, m["lho"], m["lho"] + 30); fl, el = struct.unpack("<HH", h[26:30])
    return m["lho"] + 30 + fl + el

class RemoteFile(io.RawIOBase):
    def __init__(self, url, off, n): self.url, self.off, self.n, self.pos = url, off, n, 0
    def readable(self): return True
    def seekable(self): return True
    def seek(self, p, wh=0):
        self.pos = p if wh == 0 else self.pos + p if wh == 1 else self.n + p; return self.pos
    def tell(self): return self.pos
    def readinto(self, b):
        k = min(len(b), self.n - self.pos)
        if k <= 0: return 0
        b[:k] = rng(self.url, self.off + self.pos, self.off + self.pos + k); self.pos += k; return k

def open_member(url, m):
    off = data_offset(url, m)
    if m["method"] == 0:
        return io.BufferedReader(RemoteFile(url, off, m["usize"]), buffer_size=1 << 20)
    raw = rng(url, off, off + m["csize"]); return io.BytesIO(zlib.decompress(raw, -15))
