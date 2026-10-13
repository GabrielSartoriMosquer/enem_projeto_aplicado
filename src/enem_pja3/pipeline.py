import sys
import time

from enem_pja3.config import ANOS
from enem_pja3.extract.download_zips import criar_sessao, baixar_zip
from enem_pja3.extract.extract_zips import extrair_csvs
from enem_pja3.transform.transform import transformar
from enem_pja3.load.load import carregar_notas, carregar_perfil
from enem_pja3.volumetria import gerar_volumetria


def main() -> None:
    """Roda o pipeline completo. Também dá para escolher os anos: enem-pja3 2023 2024"""
    anos = [int(ano) for ano in sys.argv[1:]] or ANOS
    inicio = time.time()

    sessao = criar_sessao()
    for ano in anos:
        print(f"===== {ano}")
        baixar_zip(ano, sessao)
        extrair_csvs(ano)
        transformar(ano)
        print(f"ok ({time.time() - inicio:.0f} s desde o início)")

    print("===== gold")
    carregar_notas()
    carregar_perfil()

    print(gerar_volumetria())
    print(f"Tempo total: {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    main()
