"""LMU shared-memory probe (Windows only). Does NOT need any other project file.

Step 1: start Le Mans Ultimate, enable plugins in Settings -> Gameplay,
        load a session and sit in the car (on track, not in the menu).
Step 2: python probe_lmu.py
It reports which known shared-memory names exist, their size, and how often
the first bytes (the rF2-style version counter) change = update rate estimate.
Send me the full output.
"""
import ctypes
import sys
import time
import zlib

if sys.platform != "win32":
    sys.exit("Windows only.")

k32 = ctypes.windll.kernel32
k32.OpenFileMappingW.restype = ctypes.c_void_p
k32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                              ctypes.c_uint32, ctypes.c_size_t]


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_uint32), ("PartitionId", ctypes.c_uint16),
                ("RegionSize", ctypes.c_size_t), ("State", ctypes.c_uint32),
                ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32)]


# Names used by the rF2 Shared Memory Map plugin (known). Others are guesses
# for the built-in LMU API; the probe simply reports what exists.
CANDIDATES = [
    "$rFactor2SMMP_Telemetry$", "$rFactor2SMMP_Scoring$", "$rFactor2SMMP_Extended$",
    "$rFactor2SMMP_Rules$", "$rFactor2SMMP_ForceFeedback$",
    "LMU_Data", "LMU_Telemetry", "LMU_Scoring",
]
FILE_MAP_READ = 4


def open_view(name):
    for n in (name, "Local\\" + name):
        h = k32.OpenFileMappingW(FILE_MAP_READ, False, n)
        if h:
            p = k32.MapViewOfFile(h, FILE_MAP_READ, 0, 0, 0)
            if p:
                mbi = MBI()
                k32.VirtualQuery(ctypes.c_void_p(p), ctypes.byref(mbi), ctypes.sizeof(mbi))
                return n, p, mbi.RegionSize
    return None


found = []
for name in CANDIDATES:
    r = open_view(name)
    print(f"{name:32s} -> {'FOUND, size ' + str(r[2]) + ' bytes' if r else 'not found'}")
    if r:
        found.append(r)

if not found:
    print("\nNothing found. Check: game running, session loaded, plugins enabled.")
    sys.exit(1)

print("\nSampling 5 seconds (drive or sit in the car on track)...")
state = {n: {"v": None, "vc": 0, "c": None, "cc": 0} for n, _, _ in found}
t_end = time.perf_counter() + 5.0
n_polls = 0
while time.perf_counter() < t_end:
    n_polls += 1
    for n, p, size in found:
        head = ctypes.string_at(p, 4)
        crc = zlib.crc32(ctypes.string_at(p, min(size, 65536)))
        s = state[n]
        if head != s["v"]:
            s["vc"] += 1
            s["v"] = head
        if crc != s["c"]:
            s["cc"] += 1
            s["c"] = crc
for n, s in state.items():
    print(f"{n:32s} first-4-bytes changes: {s['vc']/5:7.1f}/s | "
          f"first-64KB content changes: {s['cc']/5:7.1f}/s")
print(f"(poll loop ran {n_polls/5:.0f} times/s)")
for n, p, size in found:
    print(f"\n{n}: first 64 bytes hex:\n{ctypes.string_at(p, 64).hex(' ')}")
