import json
import zipfile

import pytest
from app.core.config import Settings
from app.etl.transform import transform_year
from app.services.data_engine import build_engine


@pytest.fixture
def valid_enem_csv() -> str:
    rows = [
        "NU_ANO;SG_UF_PROVA;TP_ESCOLA;NU_NOTA_CN;NU_NOTA_CH;NU_NOTA_LC;NU_NOTA_MT;NU_NOTA_REDACAO;Q001;Q002;Q003;Q004;Q005;Q006;Q007;Q008;Q009;Q010;Q011;Q012;Q013;Q014;Q015;Q016;Q017;Q018;Q019;Q020;Q021;Q022;Q023;Q024;Q025\n",
        "2025;SP;1;500;620;700;760;800;A;B;A;B;D;G;A;B;C;D;E;F;G;H;A;B;C;D;E;F;G;H;A;B;C\n",
        "2025;RJ;2;430;540;660;720;720;C;D;E;F;G;H;A;B;C;D;E;F;G;H;A;B;C;D;E;F;G;H;A;B;C\n",
        "2025;MG;2;600;700;750;800;900;D;E;F;G;H;A;B;C;D;E;F;G;H;A;B;C;D;E;F;G;H;A;B;C\n",
    ]
    return "".join(rows)


def test_official_mode_requires_valid_dataset(tmp_path):
    settings = Settings(
        data_mode="official",
        gold_path=str(tmp_path / "gold" / "enem_notas.parquet"),
        parquet_glob=str(tmp_path / "parquet" / "ano=*" / "enem.parquet"),
        demo_csv=str(tmp_path / "demo.csv"),
    )
    with pytest.raises(FileNotFoundError):
        build_engine(settings)


def test_transform_year_creates_quality_report(tmp_path, valid_enem_csv):
    zip_path = tmp_path / "microdados_enem_2025.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("microdados_enem_2025.csv", valid_enem_csv)

    report = transform_year(zip_path, 2025, tmp_path / "parquet")

    assert report["year"] == 2025
    assert "quality" in report
    assert report["quality"]["records_valid"] >= 1
    quality_path = tmp_path / "parquet" / "ano=2025" / "quality_report.json"
    assert quality_path.exists()
    payload = json.loads(quality_path.read_text(encoding="utf-8"))
    assert payload["year"] == 2025
    assert "rejections" in payload
