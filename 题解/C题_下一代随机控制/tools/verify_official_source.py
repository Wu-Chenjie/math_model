"""Read-only byte comparison against the official 2026 problem archive."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'artifacts/source-verification/CUMCM2026Problems.zip'


def main():
    checks = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for entry in archive.infolist():
            if not entry.filename.startswith('C题/') or entry.is_dir():
                continue
            relative = Path(entry.filename).relative_to('C题')
            local = ROOT / 'inputs' / relative
            official_sha = hashlib.sha256(archive.read(entry)).hexdigest()
            local_sha = hashlib.sha256(local.read_bytes()).hexdigest()
            checks.append({'file': str(relative), 'bytes': entry.file_size,
                           'official_sha256': official_sha,
                           'local_sha256': local_sha,
                           'equal': official_sha == local_sha})
    report = {
        'status': 'PASS' if len(checks) == 10 and all(c['equal'] for c in checks) else 'FAIL',
        'official_page': 'https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html',
        'download_url': 'https://www.mcm.edu.cn/upload_cn/CUMCM2026Problems.zip',
        'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        'checked_utc': datetime.now(timezone.utc).isoformat(),
        'checks': checks,
        'scope': 'All ten C-problem PDF/data/template files; no input modified. The separately supplied formatting PDF is outside this byte-comparison scope.'
    }
    target = ROOT / 'artifacts/source-verification/official-input-comparison.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'files': len(checks),
                      'different': [c['file'] for c in checks if not c['equal']]}, ensure_ascii=False))
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
