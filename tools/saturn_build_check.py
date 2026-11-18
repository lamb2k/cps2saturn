#!/usr/bin/env python3
"""Compile every module under saturn/ with the SH-2 cross compiler, warnings as errors. A build gate: it proves the sources build for the target.

It does not link a game and it does not run anything: a clean compile is not a working console build (see playbook, tiers HOST / BUILD / EMULATOR / CONSOLE).

The toolchain is yours, not the kit's. Found in this order: --gcc PATH, $SH_ELF_GCC, $JO/Compiler/WINDOWS/bin/sh-elf-gcc(.exe) (a Jo Engine tree),
sh-elf-gcc on PATH. saturn/cd/sat_gfs_io.c includes Sega's SEGA_GFS.H (from your SGL copy): --sgl-inc DIR, $SGL_INC or $JO/Compiler/COMMON/SGL_302j/INC;
without it that one file is reported as skipped, never as passed.

It then links two images with stand-ins for what a game supplies (tests/c/link_stubs_*.c): the loader with saturn/ld/boot.ld.in, and the runtime with
saturn/ld/rt.ld.in, and checks that nothing is unresolved except Sega's GFS functions in the loader (stubbed), that the loader starts at its base and the
runtime's _sat_start sits at the entry address. That proves the link script templates and the symbol names between the modules, not a game.

usage: saturn_build_check.py [--gcc PATH] [--sgl-inc DIR] [--keep DIR] [--quiet] [--no-link]
Exit 0 every module that could be compiled did and no module failed (a missing toolchain is "SKIP", exit 0, said on the first line),
1 a module failed, 2 bad input.
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SATURN = ROOT / "saturn"
NEEDS_SGL = {"sat_gfs_io.c"}   # the one file that includes Sega's headers
CFLAGS = ["-m2", "-mb", "-O2", "-ffreestanding", "-fno-builtin", "-fno-strict-aliasing", "-Wall", "-Wextra", "-Werror", "-c"]


def find_gcc(arg=None):
    cands = []
    if arg:
        cands.append(pathlib.Path(arg))
    if os.environ.get("SH_ELF_GCC"):
        cands.append(pathlib.Path(os.environ["SH_ELF_GCC"]))
    jo = os.environ.get("JO")
    if jo:
        for n in ("sh-elf-gcc.exe", "sh-elf-gcc"):
            cands.append(pathlib.Path(jo) / "Compiler/WINDOWS/bin" / n)
    for c in cands:
        if c.exists():
            return str(c)
    w = shutil.which("sh-elf-gcc")
    return w


def find_sgl(arg=None):
    for c in (arg, os.environ.get("SGL_INC")):
        if c and pathlib.Path(c).is_dir():
            return str(c)
    jo = os.environ.get("JO")
    if jo:
        p = pathlib.Path(jo) / "Compiler/COMMON/SGL_302j/INC"
        if p.is_dir():
            return str(p)
    return None


def modules():
    return sorted(p for p in SATURN.rglob("*") if p.suffix in (".c", ".S"))


def compile_one(gcc, src, out, extra, env):
    cmd = [gcc, *CFLAGS, *extra, str(src), "-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def fill(template, values):
    text = template.read_text()
    for k, v in values.items():
        text = text.replace(f"@{k}@", v)
    left = sorted(set(re.findall(r"@[A-Z_0-9]+@", text)))
    if left:
        raise ValueError(f"{template.name}: unfilled {left}")
    return text


def map_symbol(map_text, name):
    """Address of a symbol in a GNU ld map. Symbols from objects print without the target's leading underscore, symbols from the script with it."""
    names = "|".join(re.escape(n) for n in {name, name.lstrip("_")})
    m = re.search(r"^\s+0x([0-9a-f]{8,16})\s+(?:%s)(?:\s*=\s*\.)?\s*$" % names, map_text, re.M)
    return int(m.group(1), 16) if m else None


def link_one(gcc, env, out_dir, label, objs, script, extra=()):
    elf, mp = out_dir / f"{label}.elf", out_dir / f"{label}.map"
    cmd = [gcc, "-m2", "-mb", "-nostdlib", "-T", str(script), *map(str, objs), *extra, "-lgcc", f"-Wl,-Map={mp}", "-o", str(elf)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip(), (mp.read_text(errors="replace") if mp.exists() else "")


def link_images(gcc, env, out_dir, base):
    """Link the loader and the runtime against stand-in game files. Returns a list of failure labels."""
    failed = []
    stubs = ROOT / "tests" / "c"
    for stub in ("link_stubs_loader.c", "link_stubs_rt.c"):
        rc, text = compile_one(gcc, stubs / stub, out_dir / (stub[:-2] + ".o"), base, env)
        if rc:
            print(f"FAIL {stub}", text, sep="\n")
            return [stub]
    o = lambda n: out_dir / f"{n}.o"
    ld = SATURN / "ld"
    # loader: crt0 first, GFS stubbed
    boot = out_dir / "boot.ld"
    boot.write_text(fill(ld / "boot.ld.in", {"LOADER_BASE": "0x06004000", "LOADER_STACK": "4096"}))
    rc, text, mp = link_one(gcc, env, out_dir, "loader", [o(n) for n in ("crt0", "sat_diag", "sat_boot", "sat_cart_soak", "sat_boot_main", "sat_store", "sat_gfs_io", "link_stubs_loader")], boot)
    start = map_symbol(mp, "_sat_crt0")
    top = map_symbol(mp, "_sat_boot_sp")
    if not rc and top is not None and top > 0x06013fa0:
        rc, text = 1, f"the loader (with its stack) ends at {top:#x}, over the mailboxes at 0x06013fa0"
    if rc or start != 0x06004000:
        print(f"FAIL loader link (crt0 at {start if start is None else hex(start)})", text, sep="\n")
        failed.append("loader link")
    # runtime: sat_ctx first by the template, the rest in any order
    rt = out_dir / "rt.ld"
    rt.write_text(fill(ld / "rt.ld.in", {"HW_BASE": "0x06014000", "HW_OBJECTS": "", "LW_BASE": "0x00200000", "LW_OBJECTS": "", "CART_BASE": "0x02400000", "CART_OBJECTS": ""}))
    names = ("sat_ctx", "sat_sync", "sat_pad", "sat_opx", "sat_vdp1", "sat_vdp2", "sat_tilecache", "sat_layer", "sat_scsp", "sat_cdda", "sat_store", "sat_diag", "link_stubs_rt")
    rc, text, mp = link_one(gcc, env, out_dir, "runtime", [o(n) for n in names], rt)
    start = map_symbol(mp, "_sat_start")
    if rc or start != 0x06014000:
        print(f"FAIL runtime link (_sat_start at {start if start is None else hex(start)})", text, sep="\n")
        failed.append("runtime link")
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gcc")
    ap.add_argument("--sgl-inc")
    ap.add_argument("--keep")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-link", action="store_true")
    a = ap.parse_args(argv)
    gcc = find_gcc(a.gcc)
    if not gcc:
        print("SKIP: no SH-2 cross compiler found (--gcc, SH_ELF_GCC, JO or sh-elf-gcc on PATH); nothing compiled")
        return 0
    sgl = find_sgl(a.sgl_inc)
    env = dict(os.environ)
    env["PATH"] = str(pathlib.Path(gcc).parent) + os.pathsep + env.get("PATH", "")   # the compiler's DLLs on Windows
    out_dir = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp(prefix="satbuild-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    failed, passed, skipped = [], [], []
    base = ["-I", str(SATURN)]
    for src in modules():
        rel = src.relative_to(ROOT).as_posix()
        extra = list(base)
        if src.name in NEEDS_SGL:
            if not sgl:
                skipped.append(rel)
                continue
            extra += ["-I", sgl]
        variants = [[]]
        if src.name == "sat_ctx.S":
            variants = [[], ["-DSAT_R14_SYMBOL=_game_state"]]
        for k, v in enumerate(variants):
            out = out_dir / (src.stem + (f".{k}" if k else "") + ".o")
            rc, text = compile_one(gcc, src, out, extra + v, env)
            (failed if rc else passed).append(rel + (" " + " ".join(v) if v else ""))
            if rc:
                print(f"FAIL {rel}\n{text}")
            elif text and not a.quiet:
                print(f"note {rel}\n{text}")
    link_failed = []
    if not a.no_link and not failed:
        link_failed = link_images(gcc, env, out_dir, base)
    if not a.keep:
        shutil.rmtree(out_dir, ignore_errors=True)
    failed += link_failed
    print(f"saturn build check ({gcc}): {len(passed)} compiled, {len(failed)} failed, {len(skipped)} skipped"
          + (f" (no SGL headers: {', '.join(skipped)})" if skipped else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
