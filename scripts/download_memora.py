#!/usr/bin/env python3
"""从官方 GitHub 仓库下载固定的 Memora 子集。

默认读取 configs/sample_personas.json，并检出其中固定的 commit。这样将来官方
仓库更新后，仍能复现本项目中的 3 personas / 45 QA 数据。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 Memora 官方固定子集")
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "configs" / "sample_personas.json"),
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data" / "raw"),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="目标 persona 已存在时覆盖（只会处理配置中明确列出的目录）",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    output_root = Path(args.output).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    period = config["period"]
    personas = config["personas"]

    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memora-download-") as temp_dir:
        clone_dir = Path(temp_dir) / "Memora"
        run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                config["source_repository"],
                str(clone_dir),
            ]
        )
        run(["git", "checkout", config["source_commit"], "--", "data", "LICENSE"], cwd=clone_dir)

        for persona in personas:
            source = clone_dir / "data" / period / persona
            destination = output_root / period / persona
            if destination.exists():
                if not args.force:
                    raise FileExistsError(
                        f"目标已存在：{destination}；如需覆盖请加 --force"
                    )
                # destination 由固定 output/period/persona 拼出，不接受通配符。
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)

        shutil.copy2(clone_dir / "LICENSE", output_root.parent / "MEMORA_LICENSE")

    source_info = {
        "repository": config["source_repository"],
        "commit": config["source_commit"],
        "period": period,
        "personas": personas,
    }
    (output_root / "SOURCE.json").write_text(
        json.dumps(source_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"下载完成：{period} / {len(personas)} personas -> {output_root}")


if __name__ == "__main__":
    main()
