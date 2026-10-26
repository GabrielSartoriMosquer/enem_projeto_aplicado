import sys
import time

from enem_pja3 import lake
from enem_pja3.config import ANOS, DATA_DIR
from enem_pja3.extract.download_zips import criar_sessao, baixar_zip
from enem_pja3.extract.extract_zips import extrair_csvs
from enem_pja3.transform.transform import transformar
from enem_pja3.load.load import carregar_notas, carregar_perfil
from enem_pja3.volumetria import gerar_volumetria


def main() -> None:
    """Roda o pipeline completo. Também dá para escolher os anos: enem-pja3 2023 2024"""
    anos = [int(ano) for ano in sys.argv[1:]] or ANOS
    inicio = time.time()
    if lake.ativo():
        print("Usando o data lake no Azure")

    sessao = criar_sessao()
    for ano in anos:
        print(f"===== {ano}")
        # No lake a bronze guarda só o zip: os CSVs são recriados a partir dele
        lake.enviar(baixar_zip(ano, sessao))
        extrair_csvs(ano)
        for parquet in transformar(ano):
            lake.enviar(parquet)
        print(f"ok ({time.time() - inicio:.0f} s desde o início)")

    print("===== gold")
    # A gold junta todos os anos da silver, não só os desta execução. Por isso a silver local é
    # sincronizada com o lake antes: assim entram também os anos processados em outra máquina.
    lake.sincronizar(DATA_DIR / "silver")
    for parquet in (carregar_notas(), carregar_perfil()):
        lake.enviar(parquet)

    print(gerar_volumetria())
    print(f"Tempo total: {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    main()
