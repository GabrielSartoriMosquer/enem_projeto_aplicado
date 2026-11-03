import zipfile

from enem_pja3.extract.extract_zips import extrair_csvs


def criar_zip(dados, ano, arquivos):
    caminho = dados / "bronze/zips" / f"microdados_enem_{ano}.zip"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in arquivos.items():
            zf.writestr(nome, conteudo)


def test_extrai_so_csvs_da_pasta_dados(dados):
    # Em 2018 a pasta DADOS/ fica na raiz do zip; em 2023 fica dentro de outra pasta
    criar_zip(dados, 2018, {
        "DADOS/MICRODADOS_ENEM_2018.csv": "a;b\n1;2\n",
        "DADOS/dicionario.xlsx": "não é csv",
        "LEIA-ME/leia_me.pdf": "pdf",
    })
    criar_zip(dados, 2023, {
        "microdados_enem_2023/DADOS/MICRODADOS_ENEM_2023.csv": "a;b\n1;2\n",
        "microdados_enem_2023/INPUTS/input.csv": "fora da pasta DADOS",
    })

    assert [c.name for c in extrair_csvs(2018)] == ["MICRODADOS_ENEM_2018.csv"]
    assert [c.name for c in extrair_csvs(2023)] == ["MICRODADOS_ENEM_2023.csv"]
    assert (dados / "bronze/csv/ano=2023/MICRODADOS_ENEM_2023.csv").read_text() == "a;b\n1;2\n"


def test_nao_extrai_de_novo(dados, capsys):
    criar_zip(dados, 2018, {"DADOS/MICRODADOS_ENEM_2018.csv": "a;b\n1;2\n"})
    extrair_csvs(2018)
    extrair_csvs(2018)
    assert "[pulado]" in capsys.readouterr().out
