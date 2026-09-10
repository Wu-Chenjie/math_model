"""Format conversion only. All modeling, optimization, simulation and statistics are C++."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "inputs"
INPUT.mkdir(exist_ok=True)
old = ROOT.parent / "综合优化"
names = ("data", "baseline_q2", "baseline_q3", "baseline_q4_2", "baseline_q4_3")
for name in names:
    destination = INPUT / f"{name}.npz"
    if not destination.exists():
        relative = "inputs/prepared/data.npz" if name == "data" else f"artifacts/{name.removeprefix('baseline_')}.npz"
        source = old / relative
        if not source.exists():
            raise FileNotFoundError(f"Missing authorized input: {source}")
        shutil.copyfile(source, destination)
output = INPUT / "native"
output.mkdir(exist_ok=True)
manifest = {}
for name in names:
    source = INPUT / f"{name}.npz"
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    with np.load(source, allow_pickle=False) as archive:
        for key in archive.files:
            value = archive[key]
            if value.dtype.kind not in "fiu":
                continue
            target = output / f"{name}_{key}.bin"
            value.astype("<f8").tofile(target)
            manifest[target.name] = {"shape": list(value.shape), "source_sha256": sha,
                                     "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
(output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Converted {len(manifest)} numeric arrays without model calculations.")
