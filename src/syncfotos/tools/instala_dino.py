from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

CPU_INDEX = "https://download.pytorch.org/whl/cpu"
CUDA_INDEX = "https://download.pytorch.org/whl/cu128"


def has_nvidia_gpu() -> bool:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return False
    try:
        return subprocess.run([exe, "-L"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Instal.la torch (CPU o CUDA segons el maquinari) i transformers per activar DINOv2."
    )
    parser.add_argument("--cpu", action="store_true", help="Força la versio de CPU")
    parser.add_argument("--cuda", action="store_true", help="Força la versio CUDA")
    parser.add_argument("--index-url", default=None, help="Index de PyTorch personalitzat")
    args = parser.parse_args()

    use_cuda = args.cuda or (not args.cpu and has_nvidia_gpu())
    index = args.index_url or (CUDA_INDEX if use_cuda else CPU_INDEX)
    if not index.startswith("https://"):
        sys.exit("L'index de PyTorch ha de ser una URL https.")
    print(f"Variant de torch: {'CUDA' if use_cuda else 'CPU'} ({index})")

    pip = [sys.executable, "-m", "pip", "install"]
    cmd = pip + ["torch", "--index-url", index]
    # PyPI com a index addicional només amb els índexs oficials de PyTorch (evita confusió de dependències).
    if index in (CPU_INDEX, CUDA_INDEX):
        cmd += ["--extra-index-url", "https://pypi.org/simple"]
    if subprocess.call(cmd) != 0:
        sys.exit("No s'ha pogut instal.lar torch. Per a CUDA, prova --index-url amb un altre cuXXX.")
    sys.exit(subprocess.call(pip + ["transformers"]))


if __name__ == "__main__":
    main()
