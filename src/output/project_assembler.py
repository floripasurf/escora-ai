"""Montador de projeto -- combina todos os outputs em um pacote.

Gera um arquivo ZIP contendo:
- Planta arquitetonica (DXF)
- Planta estrutural (DXF)
- Memorial de calculo (PDF)
- Lista de materiais (CSV)
"""

import logging
import zipfile
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def assemble_project(
    output_dir: str,
    project_name: str,
    files: Dict[str, str],
) -> str:
    """Monta pacote ZIP com todos os arquivos do projeto.

    Args:
        output_dir: Diretorio de saida
        project_name: Nome do projeto (para o arquivo ZIP)
        files: Dict de {tipo: caminho_do_arquivo}
            Tipos: 'arch_dxf', 'struct_dxf', 'memorial_pdf', 'bom_csv'

    Returns:
        Caminho do arquivo ZIP
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = str(out_dir / f"{project_name}_projeto.zip")

    label_map = {
        "arch_dxf": f"{project_name}_planta_arquitetonica.dxf",
        "struct_dxf": f"{project_name}_planta_estrutural.dxf",
        "memorial_pdf": f"{project_name}_memorial_calculo.pdf",
        "bom_csv": f"{project_name}_lista_materiais.csv",
        "relatorio_pdf": f"{project_name}_relatorio.pdf",
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_type, file_path in files.items():
            if file_path and Path(file_path).exists():
                arcname = label_map.get(file_type, Path(file_path).name)
                zf.write(file_path, arcname)
                logger.info(f"Adicionado ao ZIP: {arcname}")
            else:
                logger.warning(f"Arquivo nao encontrado: {file_type} -> {file_path}")

    logger.info(f"Projeto montado: {zip_path}")
    return zip_path
