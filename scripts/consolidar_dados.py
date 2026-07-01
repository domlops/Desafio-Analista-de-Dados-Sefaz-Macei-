from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "dados_extraidos"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "dados_processados" / "finbra_consolidado.parquet"
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
FUNCTION_PATTERN = re.compile(r"^(?P<codigo_funcao>\d{2}) - (?P<nome_funcao>.+)$")
SUBFUNCTION_PATTERN = re.compile(
    r"^(?P<codigo_funcao>\d{2})\.(?P<codigo_subfuncao>\d{3}) - "
    r"(?P<nome_subfuncao>.+)$"
)
OTHER_SUBFUNCTIONS_PATTERN = re.compile(
    r"^FU(?P<codigo_funcao>\d{2}) - (?P<nome_conta>.+)$"
)
TOTAL_ACCOUNTS = {
    "Despesas Exceto Intraorçamentárias",
    "Despesas Intraorçamentárias",
}
FUNCTION_NAMES = {
    "01": "Legislativa",
    "02": "Judiciária",
    "03": "Essencial à Justiça",
    "04": "Administração",
    "05": "Defesa Nacional",
    "06": "Segurança Pública",
    "07": "Relações Exteriores",
    "08": "Assistência Social",
    "09": "Previdência Social",
    "10": "Saúde",
    "11": "Trabalho",
    "12": "Educação",
    "13": "Cultura",
    "14": "Direitos da Cidadania",
    "15": "Urbanismo",
    "16": "Habitação",
    "17": "Saneamento",
    "18": "Gestão Ambiental",
    "19": "Ciência e Tecnologia",
    "20": "Agricultura",
    "22": "Indústria",
    "23": "Comércio e Serviços",
    "24": "Comunicações",
    "25": "Energia",
    "26": "Transporte",
    "27": "Desporto e Lazer",
    "28": "Encargos Especiais",
}
ACCOUNT_CLASSIFICATION_COLUMNS = [
    "tipo_conta",
    "codigo_conta",
    "nome_conta",
    "codigo_funcao",
    "nome_funcao",
    "codigo_subfuncao",
    "nome_subfuncao",
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
            "Arquivo que receberá a base consolidada. "
            "Use extensão .parquet ou .csv. "
            "Padrão: dados_processados/finbra_consolidado.parquet"
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


def empty_account_classification(account: str) -> dict[str, object]:
    return {
        "tipo_conta": "não_classificada",
        "codigo_conta": pd.NA,
        "nome_conta": account,
        "codigo_funcao": pd.NA,
        "nome_funcao": pd.NA,
        "codigo_subfuncao": pd.NA,
        "nome_subfuncao": pd.NA,
    }


def classify_account(account: str) -> dict[str, object]:
    if account in TOTAL_ACCOUNTS:
        return {
            "tipo_conta": "total",
            "codigo_conta": pd.NA,
            "nome_conta": account,
            "codigo_funcao": pd.NA,
            "nome_funcao": pd.NA,
            "codigo_subfuncao": pd.NA,
            "nome_subfuncao": pd.NA,
        }

    function_match = FUNCTION_PATTERN.match(account)
    if function_match:
        code = function_match.group("codigo_funcao")
        name = function_match.group("nome_funcao")
        return {
            "tipo_conta": "função",
            "codigo_conta": code,
            "nome_conta": name,
            "codigo_funcao": code,
            "nome_funcao": name,
            "codigo_subfuncao": pd.NA,
            "nome_subfuncao": pd.NA,
        }

    subfunction_match = SUBFUNCTION_PATTERN.match(account)
    if subfunction_match:
        function_code = subfunction_match.group("codigo_funcao")
        subfunction_code = subfunction_match.group("codigo_subfuncao")
        subfunction_name = subfunction_match.group("nome_subfuncao")
        return {
            "tipo_conta": "subfunção",
            "codigo_conta": f"{function_code}.{subfunction_code}",
            "nome_conta": subfunction_name,
            "codigo_funcao": function_code,
            "nome_funcao": FUNCTION_NAMES.get(function_code, pd.NA),
            "codigo_subfuncao": subfunction_code,
            "nome_subfuncao": subfunction_name,
        }

    other_subfunctions_match = OTHER_SUBFUNCTIONS_PATTERN.match(account)
    if other_subfunctions_match:
        function_code = other_subfunctions_match.group("codigo_funcao")
        name = other_subfunctions_match.group("nome_conta")
        return {
            "tipo_conta": "demais_subfunções",
            "codigo_conta": f"FU{function_code}",
            "nome_conta": name,
            "codigo_funcao": function_code,
            "nome_funcao": FUNCTION_NAMES.get(function_code, pd.NA),
            "codigo_subfuncao": pd.NA,
            "nome_subfuncao": pd.NA,
        }

    return empty_account_classification(account)


def add_account_classification(df: pd.DataFrame) -> pd.DataFrame:
    records = [classify_account(account) for account in df["Conta"]]
    classification = pd.DataFrame.from_records(records, index=df.index)

    for column in ACCOUNT_CLASSIFICATION_COLUMNS:
        classification[column] = classification[column].astype("string")

    insert_at = df.columns.get_loc("Conta") + 1
    df_with_classification = pd.concat(
        [
            df.iloc[:, :insert_at],
            classification,
            df.iloc[:, insert_at:],
        ],
        axis=1,
    )
    validate_account_classification(df_with_classification)
    return df_with_classification


def validate_account_classification(df: pd.DataFrame) -> None:
    unclassified = df[df["tipo_conta"] == "não_classificada"]
    if not unclassified.empty:
        examples = unclassified["Conta"].drop_duplicates().head(10).to_list()
        raise ValueError(
            "Existem contas sem classificação. Exemplos: "
            f"{', '.join(examples)}"
        )

    missing_function_names = df[
        df["tipo_conta"].isin(["função", "subfunção", "demais_subfunções"])
        & df["nome_funcao"].isna()
    ]
    if not missing_function_names.empty:
        examples = missing_function_names["Conta"].drop_duplicates().head(10).to_list()
        raise ValueError(
            "Existem contas com código de função desconhecido. Exemplos: "
            f"{', '.join(examples)}"
        )


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
    df = pd.concat(dataframes, ignore_index=True)
    return add_account_classification(df)


def save_dataframe(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_file.suffix.lower()

    if suffix == ".parquet":
        df.to_parquet(output_file, index=False)
        return

    if suffix == ".csv":
        df.to_csv(output_file, index=False, encoding=CSV_ENCODING)
        return

    raise ValueError(
        "Formato de saída não suportado. Use um arquivo com extensão .parquet ou .csv."
    )


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

    print("\nTipos de conta:")
    account_types = df["tipo_conta"].value_counts().sort_index()
    for account_type, total in account_types.items():
        print(f"- {account_type}: {total:,}".replace(",", "."))


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
