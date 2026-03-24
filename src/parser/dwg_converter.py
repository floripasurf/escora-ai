"""Conversão de DWG para DXF via ODA File Converter."""

import subprocess
import os
from pathlib import Path
from typing import Optional


def find_oda_converter() -> Optional[str]:
    """Procura o ODA File Converter no sistema."""
    possible_paths = [
        "/usr/bin/ODAFileConverter",
        "/usr/local/bin/ODAFileConverter",
        "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
        os.path.expanduser("~/ODAFileConverter/ODAFileConverter"),
    ]
    for path in possible_paths:
        if os.path.isfile(path):
            return path
    return None


def convert_dwg_to_dxf(
    input_path: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Converte um arquivo DWG para DXF usando ODA File Converter.

    Retorna o caminho do arquivo DXF gerado.
    Raises FileNotFoundError se o ODA não estiver instalado.
    """
    converter = find_oda_converter()
    if converter is None:
        raise FileNotFoundError(
            "ODA File Converter não encontrado. "
            "Baixe em: https://www.opendesign.com/guestfiles/oda_file_converter"
        )

    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    if output_dir is None:
        output_dir = str(input_file.parent)

    result = subprocess.run(
        [
            converter,
            str(input_file.parent),
            output_dir,
            "ACAD2018",
            "DXF",
            "0",
            "1",
            input_file.name,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Erro na conversão: {result.stderr}")

    output_path = os.path.join(output_dir, input_file.stem + ".dxf")
    if not os.path.exists(output_path):
        raise RuntimeError(f"Arquivo de saída não gerado: {output_path}")

    return output_path
