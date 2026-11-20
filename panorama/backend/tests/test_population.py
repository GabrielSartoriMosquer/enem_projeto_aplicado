"""Área "Quem faz o ENEM": motor e rotas sobre um resumo do perfil gerado no teste."""

import duckdb
import pytest
from app.api.routes import population_dep
from app.core.config import Settings
from app.main import app
from app.services.population import PopulationEngine, get_population, reset_population
from fastapi.testclient import TestClient

# (ano, uf, indicador, categoria, recorte, grupo do recorte, n)
LINHAS = [
    (2020, "SC", "internet", "sim", None, None, 90),
    (2020, "SC", "internet", "nao", None, None, 10),
    (2020, "AM", "internet", "sim", None, None, 30),
    (2020, "AM", "internet", "nao", None, None, 70),
    (2024, "SC", "internet", "sim", None, None, 95),
    (2024, "SC", "internet", "nao", None, None, 5),
    (2024, "SC", "renda_propria", "sim", None, None, 40),
    (2024, "SC", "renda_propria", "nao", None, None, 60),
    (2020, "SC", "computador", "nenhum", None, None, 25),
    (2020, "SC", "computador", "um", None, None, 75),
    (2020, "AM", "computador", "nenhum", None, None, 75),
    (2020, "AM", "computador", "dois_mais", None, None, 25),
    (2020, None, "computador", "nenhum", "renda", "ate_1", 80),
    (2020, None, "computador", "um", "renda", "ate_1", 20),
    (2020, None, "computador", "nenhum", "renda", "mais_10", 2),
    (2020, None, "computador", "dois_mais", "renda", "mais_10", 98),
    (2020, "SC", "sexo", "feminino", None, None, 60),
    (2020, "SC", "sexo", "masculino", None, None, 40),
    (2020, "AM", "sexo", "feminino", None, None, 55),
    (2020, "AM", "sexo", "masculino", None, None, 45),
]


@pytest.fixture
def resumo(tmp_path):
    caminho = tmp_path / "enem_perfil_resumo.parquet"
    con = duckdb.connect()
    con.execute("""CREATE TABLE r (NU_ANO USMALLINT, SG_UF_PROVA VARCHAR, INDICADOR VARCHAR,
                   CATEGORIA VARCHAR,
                   RECORTE VARCHAR, RECORTE_CATEGORIA VARCHAR, N UINTEGER)""")
    con.executemany("INSERT INTO r VALUES (?, ?, ?, ?, ?, ?, ?)", LINHAS)
    con.execute(f"COPY r TO '{caminho}' (FORMAT parquet)")
    return caminho


@pytest.fixture
def engine(resumo):
    return PopulationEngine(resumo)


@pytest.fixture
def client(engine):
    app.dependency_overrides[population_dep] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.pop(population_dep, None)


def test_indicador_soma_as_ufs_e_calcula_o_destaque(engine):
    data = engine.indicator(2020, "internet")
    assert data["national"]["total"] == 200
    assert data["national"]["highlight_pct"] == 40.0  # "nao" = sem internet: 80 de 200
    estados = {s["uf"]: s["highlight_pct"] for s in data["states"]}
    assert estados == {"AM": 70.0, "SC": 10.0}
    assert data["notes"] == []  # o aviso do wi-fi só vale de 2024 em diante
    assert engine.indicator(2024, "internet")["notes"]


def test_indicador_que_nao_existe_no_ano(engine):
    data = engine.indicator(2020, "renda_propria")
    assert data["available"] is False
    assert data["national"]["total"] == 0
    assert engine.indicator_years("renda_propria") == [2024]


def test_evolucao_marca_a_mudanca_da_pergunta(engine):
    data = engine.trend("internet")
    pontos = {p["year"]: p["highlight_pct"] for p in data["points"]}
    assert pontos == {2020: 40.0, 2024: 5.0}
    assert data["breaks"][0]["year"] == 2024


def test_cruzamento_por_renda(engine):
    grupos = {
        g["code"]: g["highlight_pct"]
        for g in engine.crosstab(2020, "computador", "renda")["groups"]
    }
    assert grupos == {"ate_1": 80.0, "mais_10": 2.0}


def test_destaques_trazem_numero_e_frase(engine):
    data = engine.highlights(2020)
    fatos = {f["id"]: f for f in data["facts"]}
    assert data["participants"] == 200
    assert fatos["computador"]["value"] == 50.0
    assert "80,0%" in fatos["computador"]["detail"] and "2,0%" in fatos["computador"]["detail"]
    assert fatos["internet"]["detail"] == "Vai de 10,0% em Santa Catarina a 70,0% em Amazonas."
    assert fatos["mulheres"]["value"] == 57.5
    assert "renda" not in fatos  # sem dados de renda neste resumo


def test_erros_de_entrada(engine):
    with pytest.raises(KeyError):
        engine.indicator(2021, "internet")  # edição fora do resumo
    with pytest.raises(KeyError):
        engine.indicator(2020, "inexistente")
    with pytest.raises(KeyError):
        engine.crosstab(2020, "computador", "inexistente")


def test_rotas(client):
    assert client.get("/api/v1/population/catalog").json()["years"] == [2020, 2024]
    body = client.get(
        "/api/v1/population/indicator", params={"year": 2020, "id": "internet"}
    ).json()
    assert body["national"]["highlight_pct"] == 40.0
    assert client.get("/api/v1/population/trend", params={"id": "internet"}).status_code == 200
    assert (
        client.get(
            "/api/v1/population/crosstab",
            params={"year": 2020, "id": "computador", "recorte": "renda"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/population/highlights", params={"year": 2020}).status_code == 200
    assert (
        client.get("/api/v1/population/indicator", params={"year": 2020, "id": "x"}).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/population/indicator", params={"year": 2030, "id": "internet"}
        ).status_code
        == 422
    )


def test_area_indisponivel_sem_o_resumo(tmp_path):
    reset_population()
    sem_arquivo = Settings(
        data_mode="official", population_path=str(tmp_path / "nao_existe.parquet")
    )
    assert get_population(sem_arquivo) is None
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/v1/population/catalog")
    assert response.status_code == 503  # os testes rodam em modo demo
    reset_population()
