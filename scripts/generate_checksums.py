#!/usr/bin/env python3
"""为已提交的原始与转换数据生成 SHA-256 清单。"""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    paths = sorted(
        path
        for directory in (DATA_ROOT / "raw", DATA_ROOT / "converted")
        for path in directory.rglob("*")
        if path.is_file()
    )
    lines = [
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in paths
    ]
    output = DATA_ROOT / "CHECKSUMS.sha256"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"已写入 {len(lines)} 条 SHA-256 -> {output}")


if __name__ == "__main__":
    main()
