from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.api.types import is_integer_dtype, is_numeric_dtype, is_string_dtype


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_FILE = PROJECT_ROOT / "dados_processados" / "finbra_consolidado.parquet"
EXPECTED_COLUMNS = [
    "ano",
    "Instituição",
    "Cod.IBGE",
    "UF",
    "População",
    "Coluna",
    "Conta",
    "tipo_conta",
    "codigo_conta",
    "nome_conta",
    "codigo_funcao",
    "nome_funcao",
    "codigo_subfuncao",
    "nome_subfuncao",
    "Identificador da Conta",
    "Valor",
]
EXPECTED_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
EXPECTED_CAPITALS_BY_YEAR = {
    2020: 26,
    2021: 26,
    2022: 26,
    2023: 26,
    2024: 26,
    2025: 11,
}
EXPECTED_ACCOUNT_TYPES = {
    "função",
    "subfunção",
    "demais_subfunções",
    "total",
}
REQUIRED_NOT_NULL_COLUMNS = [
    "ano",
    "Instituição",
    "Cod.IBGE",
    "UF",
    "População",
    "Coluna",
    "Conta",
    "tipo_conta",
    "nome_conta",
    "Identificador da Conta",
    "Valor",
]
STRING_COLUMNS = [
    "Instituição",
    "Cod.IBGE",
    "UF",
    "Coluna",
    "Conta",
    "tipo_conta",
    "codigo_conta",
    "nome_conta",
    "codigo_funcao",
    "nome_funcao",
    "codigo_subfuncao",
    "nome_subfuncao",
    "Identificador da Conta",
]


class ValidationError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida a base consolidada do FINBRA/Siconfi."
    )
    parser.add_argument(
        "--arquivo",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=(
            "Arquivo consolidado que será validado. "
            "Padrão: dados_processados/finbra_consolidado.parquet"
        ),
    )
    return parser.parse_args()


def load_dataset(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(file_path)

    if suffix == ".csv":
        dtypes = {column: "string" for column in STRING_COLUMNS}
        return pd.read_csv(file_path, dtype=dtypes)

    raise ValueError("Formato não suportado. Use um arquivo .parquet ou .csv.")


def validate_columns(df: pd.DataFrame) -> None:
    columns = list(df.columns)
    if columns != EXPECTED_COLUMNS:
        raise ValidationError(
            "Colunas diferentes do esperado.\n"
            f"Esperado: {EXPECTED_COLUMNS}\nRecebido: {columns}"
        )


def validate_types(df: pd.DataFrame) -> None:
    errors: list[str] = []

    if not is_integer_dtype(df["ano"]):
        errors.append("A coluna `ano` deveria ser inteira.")

    if not is_integer_dtype(df["População"]):
        errors.append("A coluna `População` deveria ser inteira.")

    if not is_numeric_dtype(df["Valor"]):
        errors.append("A coluna `Valor` deveria ser numérica.")

    for column in STRING_COLUMNS:
        if not is_string_dtype(df[column]):
            errors.append(f"A coluna `{column}` deveria ser textual.")

    if errors:
        raise ValidationError("\n".join(errors))


def validate_years(df: pd.DataFrame) -> None:
    years = sorted(df["ano"].dropna().unique().tolist())
    if years != EXPECTED_YEARS:
        raise ValidationError(
            f"Anos diferentes do esperado. Esperado: {EXPECTED_YEARS}. Recebido: {years}."
        )


def validate_capitals_by_year(df: pd.DataFrame) -> pd.Series:
    capitals_by_year = df.groupby("ano", sort=True)["Cod.IBGE"].nunique()
    received = capitals_by_year.to_dict()

    if received != EXPECTED_CAPITALS_BY_YEAR:
        raise ValidationError(
            "Quantidade de capitais por ano diferente do esperado.\n"
            f"Esperado: {EXPECTED_CAPITALS_BY_YEAR}\nRecebido: {received}"
        )

    return capitals_by_year


def validate_required_nulls(df: pd.DataFrame) -> None:
    null_counts = df[REQUIRED_NOT_NULL_COLUMNS].isna().sum()
    unexpected_nulls = null_counts[null_counts > 0]

    if not unexpected_nulls.empty:
        raise ValidationError(
            "Foram encontrados nulos em colunas obrigatórias:\n"
            f"{unexpected_nulls.to_string()}"
        )


def validate_account_types(df: pd.DataFrame) -> None:
    received = set(df["tipo_conta"].dropna().unique())
    unexpected = received - EXPECTED_ACCOUNT_TYPES
    missing = EXPECTED_ACCOUNT_TYPES - received

    if unexpected or missing:
        raise ValidationError(
            "Tipos de conta inesperados.\n"
            f"Não esperados: {sorted(unexpected)}\nAusentes: {sorted(missing)}"
        )


def validate_classification_nulls(df: pd.DataFrame) -> None:
    total_rows = df["tipo_conta"] == "total"
    function_related_rows = df["tipo_conta"].isin(
        ["função", "subfunção", "demais_subfunções"]
    )
    subfunction_rows = df["tipo_conta"] == "subfunção"
    non_subfunction_rows = df["tipo_conta"] != "subfunção"

    checks = {
        "`codigo_conta` só pode ser nulo em totais": df.loc[
            ~total_rows, "codigo_conta"
        ].isna(),
        "`codigo_funcao` só pode ser nulo em totais": df.loc[
            function_related_rows, "codigo_funcao"
        ].isna(),
        "`nome_funcao` só pode ser nulo em totais": df.loc[
            function_related_rows, "nome_funcao"
        ].isna(),
        "`codigo_subfuncao` deve existir em subfunções": df.loc[
            subfunction_rows, "codigo_subfuncao"
        ].isna(),
        "`nome_subfuncao` deve existir em subfunções": df.loc[
            subfunction_rows, "nome_subfuncao"
        ].isna(),
        "`codigo_subfuncao` deve ser nulo fora de subfunções": df.loc[
            non_subfunction_rows, "codigo_subfuncao"
        ].notna(),
        "`nome_subfuncao` deve ser nulo fora de subfunções": df.loc[
            non_subfunction_rows, "nome_subfuncao"
        ].notna(),
    }

    errors = [message for message, failed in checks.items() if failed.any()]
    if errors:
        raise ValidationError("\n".join(errors))


def validate_replacement_characters(df: pd.DataFrame) -> None:
    text_columns = df.select_dtypes(include=["string", "object"]).columns
    columns_with_problem = []

    for column in text_columns:
        has_replacement_character = df[column].astype("string").str.contains("�").any()
        if has_replacement_character:
            columns_with_problem.append(column)

    if columns_with_problem:
        raise ValidationError(
            "Foram encontrados caracteres quebrados nas colunas: "
            f"{', '.join(columns_with_problem)}"
        )


def print_success(message: str) -> None:
    print(f"[ok] {message}")


def print_summary(df: pd.DataFrame, capitals_by_year: pd.Series) -> None:
    print("\nResumo da base:")
    print(f"- linhas: {len(df):,}".replace(",", "."))
    print(f"- colunas: {len(df.columns)}")
    print(f"- anos: {', '.join(map(str, sorted(df['ano'].unique())))}")

    print("\nCapitais por ano:")
    for year, total in capitals_by_year.items():
        note = " (ano parcial)" if year == 2025 else ""
        print(f"- {year}: {total} capitais{note}")

    print("\nNulos por coluna:")
    null_counts = df.isna().sum()
    for column, total in null_counts[null_counts > 0].items():
        print(f"- {column}: {total:,}".replace(",", "."))


def run_validations(df: pd.DataFrame) -> pd.Series:
    validate_columns(df)
    print_success("colunas obrigatórias conferidas")

    validate_types(df)
    print_success("tipos principais conferidos")

    validate_years(df)
    print_success("anos disponíveis conferidos")

    capitals_by_year = validate_capitals_by_year(df)
    print_success("quantidade de capitais por ano conferida")

    validate_required_nulls(df)
    print_success("colunas obrigatórias sem nulos")

    validate_account_types(df)
    print_success("tipos de conta conferidos")

    validate_classification_nulls(df)
    print_success("nulos da classificação conferidos")

    validate_replacement_characters(df)
    print_success("nenhum caractere quebrado encontrado")

    return capitals_by_year


def main() -> None:
    args = parse_args()
    df = load_dataset(args.arquivo)
    capitals_by_year = run_validations(df)
    print_summary(df, capitals_by_year)
    print("\nValidação concluída sem erros.")


if __name__ == "__main__":
    main()
