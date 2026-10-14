import zipfile
import shutil
import subprocess
from pathlib import Path

from enem_pja3.config import ANOS, DATA_DIR


def extrair_csvs(ano:int) -> list[Path]:
    """Extrai os CSVs da pasta DADOS/ do zip de um ano para bronze/csv/ano=AAAA"""
    zip_path = DATA_DIR / "bronze" / "zips" / f"microdados_enem_{ano}.zip"
    destino = DATA_DIR / "bronze" / "csv" / f"ano={ano}"
    destino.mkdir(parents=True, exist_ok=True)

    extraidos = []
    with zipfile.ZipFile(zip_path) as zf:
        for membro in zf.infolist():

            nome_no_zip = membro.filename
            # Em alguns anos é DADOS/arquivo.csv e em outros microdados_enem_AAAA/DADOS/arquivo.csv
            if not nome_no_zip.endswith(".csv") or "DADOS/" not in nome_no_zip:
                continue

            caminho = destino / Path(nome_no_zip).name

            if caminho.exists() and caminho.stat().st_size == membro.file_size:
                print(f"[pulado] {caminho} já existe")
                extraidos.append(caminho)
                continue

            print(f"[extraindo] {caminho}")
            if membro.compress_type == 9:
                # O RESULTADOS_2025.csv vem compactado em Deflate64 (tipo 9), que o zipfile do Python
                # não consegue abrir. Nesse caso usamos o programa unzip do sistema.
                with open(caminho, "wb") as saida:
                    subprocess.run(["unzip", "-p", str(zip_path), nome_no_zip], stdout=saida, check=True)
            else:
                with zf.open(membro) as origem, open(caminho, "wb") as saida:
                    shutil.copyfileobj(origem, saida)
            extraidos.append(caminho)
    return extraidos


if __name__ == "__main__":
    for ano in ANOS:
        for caminho in extrair_csvs(ano):
            print(caminho)
