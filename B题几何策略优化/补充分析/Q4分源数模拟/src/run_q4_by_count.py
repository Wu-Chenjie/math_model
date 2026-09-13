import concurrent.futures, hashlib, json, platform, subprocess, time
from pathlib import Path
R = Path(__file__).resolve().parents[1]
P = R.parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(R / "bin").mkdir(exist_ok=True)
(R / "results").mkdir(exist_ok=True)
(R / "artifacts").mkdir(exist_ok=True)
cc = subprocess.check_output(["bash", "-lc", "command -v clang++ || command -v g++"], text=True).strip()
src = R / "src" / "q4_by_count.cpp"
exe = R / "bin" / "q4_by_count"
compile_cmd = [cc, "-O2", "-std=c++17", str(src), "-o", str(exe)]
begin = time.time()
built = subprocess.run(compile_cmd, capture_output=True, text=True)
comp = {"command": compile_cmd, "exit_code": built.returncode, "runtime_s": time.time() - begin, "stderr": built.stderr}
(R / "artifacts" / "compile.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2))
if built.returncode:
    raise SystemExit(built.stderr)
jobs = []
for n in range(10, 17):
    start = 2810001 + 1000 * (n - 10)
    for method in (78, 84):
        jobs.append((n, start, method))

def run(job):
    n, start, method = job
    out = R / "results" / f"q4_n{n}_m{method}.csv"
    cmd = [str(exe), str(out), str(n), str(start), "40", str(method)]
    begin = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    rec = {"n": n, "method": method, "start": start, "count": 40, "command": cmd, "exit_code": p.returncode,
           "runtime_s": time.time() - begin, "stdout": p.stdout, "stderr": p.stderr, "output": str(out.relative_to(R))}
    if p.returncode == 0:
        rec["sha256"] = sha(out)
    (R / "artifacts" / f"run_n{n}_m{method}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"n={n} method={method} exit={p.returncode} {rec['runtime_s']:.1f}s", flush=True)
    if p.returncode:
        raise RuntimeError(rec)
    return rec

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(run, jobs))
(R / "artifacts" / "execution.json").write_text(json.dumps({
    "environment": platform.platform(),
    "compiler": cc,
    "binary_sha256": sha(exe),
    "source_sha256": sha(src),
    "records": records
}, ensure_ascii=False, indent=2))
print("all jobs complete")
