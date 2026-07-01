from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "dados_extraidos"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "dados_processados" / "finbra_consolidado.csv"
CSV_ENCODING = "utf-8"
EXPECTED_COLUMNS = [
    "Instituição",
    "Cod.IBGE",
    "UF",
    "População",
    "Coluna",
    "Conta",
    "Identificador da Conta",
    "Valor",
]
READ_DTYPES = {
    "Instituição": "string",
    "Cod.IBGE": "string",
    "UF": "string",
    "População": "Int64",
    "Coluna": "string",
    "Conta": "string",
    "Identificador da Conta": "string",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lê os CSVs extraídos do FINBRA/Siconfi e consolida tudo "
            "em uma única tabela."
        )
    )
    parser.add_argument(
        "--origem",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Pasta onde estão os CSVs extraídos. Padrão: dados_extraidos/",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=(
            "Arquivo CSV que receberá a base consolidada. "
            "Padrão: dados_processados/finbra_consolidado.csv"
        ),
    )
    parser.add_argument(
        "--sem-salvar",
        action="store_true",
        help="Apenas monta a base e mostra o resumo, sem gravar arquivo.",
    )
    return parser.parse_args()


def infer_year(csv_path: Path) -> int:
    year = csv_path.parent.name
    if not year.isdigit() or len(year) != 4:
        raise ValueError(
            f"Não foi possível identificar o ano a partir da pasta: {csv_path}"
        )
    return int(year)


def find_csv_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Pasta de origem não encontrada: {source_dir}")

    csv_files = sorted(source_dir.rglob("finbra.csv"), key=infer_year)
    if not csv_files:
        raise FileNotFoundError(f"Nenhum finbra.csv encontrado em: {source_dir}")

    return csv_files


def read_finbra_csv(csv_path: Path) -> pd.DataFrame:
    year = infer_year(csv_path)
    df = pd.read_csv(
        csv_path,
        sep=";",
        skiprows=3,
        encoding=CSV_ENCODING,
        decimal=",",
        thousands=".",
        dtype=READ_DTYPES,
    )
    validate_columns(df, csv_path)
    df.insert(0, "ano", year)
    return df


def validate_columns(df: pd.DataFrame, csv_path: Path) -> None:
    columns = list(df.columns)
    if columns != EXPECTED_COLUMNS:
        expected = ";".join(EXPECTED_COLUMNS)
        received = ";".join(columns)
        raise ValueError(
            "Colunas inesperadas no CSV "
            f"{csv_path}.\nEsperado: {expected}\nRecebido: {received}"
        )


def consolidate_csvs(csv_files: list[Path]) -> pd.DataFrame:
    dataframes = [read_finbra_csv(csv_path) for csv_path in csv_files]
    return pd.concat(dataframes, ignore_index=True)


def save_dataframe(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding=CSV_ENCODING)


def display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return path


def print_summary(df: pd.DataFrame, csv_files: list[Path]) -> None:
    print(f"Arquivos lidos: {len(csv_files)}")
    print(f"Linhas consolidadas: {len(df):,}".replace(",", "."))
    print(f"Colunas: {', '.join(df.columns)}")
    print("\nCapitais por ano:")

    capitals_by_year = (
        df.groupby("ano", sort=True)["Cod.IBGE"]
        .nunique()
        .rename("capitais")
        .reset_index()
    )

    for row in capitals_by_year.itertuples(index=False):
        print(f"- {row.ano}: {row.capitais} capitais")


def main() -> None:
    args = parse_args()

    csv_files = find_csv_files(args.origem)
    df = consolidate_csvs(csv_files)
    print_summary(df, csv_files)

    if args.sem_salvar:
        return

    save_dataframe(df, args.saida)
    print(f"\nBase consolidada salva em: {display_path(args.saida)}")


if __name__ == "__main__":
    main()
