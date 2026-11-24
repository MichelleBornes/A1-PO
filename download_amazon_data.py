"""Baixa somente o JSON de coordenadas de rota do dataset Amazon no AWS S3.

"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from last_mile.config import AMAZON_DATA_DIR, ensure_project_dirs

S3_PREFIX = "s3://amazon-last-mile-challenges/almrrc2021"
OBJECTS = {
    "training": (
        f"{S3_PREFIX}/almrrc2021-data-training/model_build_inputs/route_data.json"
    ),
    "evaluation": (
        f"{S3_PREFIX}/almrrc2021-data-evaluation/model_apply_inputs/eval_route_data.json"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa o JSON route_data da base oficial Amazon (não baixa os demais arquivos)."
    )
    parser.add_argument("--split", choices=tuple(OBJECTS), default="training")
    parser.add_argument("--output", type=Path, default=AMAZON_DATA_DIR / "route_data.json")
    parser.add_argument("--force", action="store_true", help="Sobrescreve o arquivo de saída existente.")
    args = parser.parse_args()

    ensure_project_dirs()
    if args.output.exists() and not args.force:
        print(f"Arquivo já existe: {args.output}")
        print("Use --force para baixar novamente.")
        return

    aws = shutil.which("aws")
    if aws is None:
        raise SystemExit(
            "AWS CLI não foi encontrado. Instale-o primeiro. No macOS com Homebrew: "
            "brew install awscli. Depois confirme com: aws --version"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    s3_uri = OBJECTS[args.split]
    comando = [aws, "s3", "cp", "--no-sign-request", s3_uri, str(args.output)]
    print(f"Baixando somente o arquivo de rotas ({args.split})...")
    print(f"Origem: {s3_uri}")
    subprocess.run(comando, check=True)
    print(f"Arquivo salvo em: {args.output}")
    print("Próximo passo: python main.py --list-routes")


if __name__ == "__main__":
    main()
