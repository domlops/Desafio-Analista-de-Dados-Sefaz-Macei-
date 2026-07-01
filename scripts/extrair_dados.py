from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "dados_compactos"
DEFAULT_TARGET_DIR = PROJECT_ROOT / "dados_extraidos"
SOURCE_ENCODING = "latin-1"
TARGET_ENCODING = "utf-8"
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


@dataclass(frozen=True)
class ExtractionResult:
    year: str
    source_zip: Path
    target_csv: Path
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extrai os arquivos finbra.csv dos ZIPs do FINBRA/Siconfi, "
            "organizando a saída por ano e convertendo o texto para UTF-8."
        )
    )
    parser.add_argument(
        "--origem",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Pasta onde estão os ZIPs originais. Padrão: dados_compactos/",
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=DEFAULT_TARGET_DIR,
        help="Pasta onde os CSVs serão extraídos. Padrão: dados_extraidos/",
    )
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        help="Substitui CSVs que já tenham sido extraídos anteriormente.",
    )
    return parser.parse_args()


def find_zip_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Pasta de origem não encontrada: {source_dir}")

    zip_files = sorted(source_dir.rglob("*.zip"))
    if not zip_files:
        raise FileNotFoundError(f"Nenhum arquivo ZIP encontrado em: {source_dir}")

    return zip_files


def infer_year(zip_path: Path) -> str:
    year = zip_path.parent.name
    if not year.isdigit() or len(year) != 4:
        raise ValueError(
            f"Não foi possível identificar o ano a partir da pasta: {zip_path}"
        )
    return year


def find_finbra_member(zip_file: ZipFile) -> str:
    candidates = [
        member
        for member in zip_file.namelist()
        if Path(member).name.lower() == "finbra.csv" and not member.endswith("/")
    ]

    if not candidates:
        raise FileNotFoundError("O arquivo finbra.csv não foi encontrado no ZIP.")

    if len(candidates) > 1:
        raise ValueError("Mais de um arquivo finbra.csv foi encontrado no ZIP.")

    return candidates[0]


def decode_finbra_csv(raw_content: bytes, zip_path: Path) -> str:
    try:
        return raw_content.decode(SOURCE_ENCODING)
    except UnicodeDecodeError as exc:
        raise UnicodeDecodeError(
            exc.encoding,
            exc.object,
            exc.start,
            exc.end,
            f"Não foi possível ler {zip_path} como {SOURCE_ENCODING}: {exc.reason}",
        ) from exc


def validate_finbra_header(csv_content: str, zip_path: Path) -> None:
    lines = csv_content.splitlines()
    if len(lines) < 4:
        raise ValueError(
            f"CSV sem linhas suficientes para validar o cabeçalho: {zip_path}"
        )

    columns = lines[3].split(";")
    if columns != EXPECTED_COLUMNS:
        expected = ";".join(EXPECTED_COLUMNS)
        received = lines[3]
        raise ValueError(
            "Cabeçalho inesperado no CSV extraído de "
            f"{zip_path}.\nEsperado: {expected}\nRecebido: {received}"
        )


def is_valid_extracted_csv(csv_path: Path) -> bool:
    try:
        csv_content = csv_path.read_text(encoding=TARGET_ENCODING)
        validate_finbra_header(csv_content, csv_path)
    except (OSError, UnicodeDecodeError, ValueError):
        return False

    return True


def extract_zip(
    zip_path: Path,
    target_dir: Path,
    overwrite: bool = False,
) -> ExtractionResult:
    year = infer_year(zip_path)
    year_dir = target_dir / year
    target_csv = year_dir / "finbra.csv"
    target_exists = target_csv.exists()

    if target_exists and not overwrite and is_valid_extracted_csv(target_csv):
        return ExtractionResult(
            year=year,
            source_zip=zip_path,
            target_csv=target_csv,
            status="ignorado",
        )

    try:
        with ZipFile(zip_path) as zip_file:
            finbra_member = find_finbra_member(zip_file)
            year_dir.mkdir(parents=True, exist_ok=True)

            raw_content = zip_file.read(finbra_member)
            csv_content = decode_finbra_csv(raw_content, zip_path)
            validate_finbra_header(csv_content, zip_path)
            target_csv.write_text(csv_content, encoding=TARGET_ENCODING)
    except BadZipFile as exc:
        raise BadZipFile(f"Arquivo ZIP inválido: {zip_path}") from exc

    return ExtractionResult(
        year=year,
        source_zip=zip_path,
        target_csv=target_csv,
        status="atualizado" if target_exists and not overwrite else "extraído",
    )


def display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return path


def print_result(result: ExtractionResult) -> None:
    relative_source = display_path(result.source_zip)
    relative_target = display_path(result.target_csv)

    if result.status == "ignorado":
        print(f"[{result.year}] já existia em UTF-8, ignorado: {relative_target}")
        return

    if result.status == "atualizado":
        print(
            f"[{result.year}] reextraído em UTF-8: "
            f"{relative_source} -> {relative_target}"
        )
        return

    print(
        f"[{result.year}] extraído em UTF-8: "
        f"{relative_source} -> {relative_target}"
    )


def main() -> None:
    args = parse_args()

    zip_files = find_zip_files(args.origem)
    results = [
        extract_zip(zip_path, args.destino, overwrite=args.sobrescrever)
        for zip_path in zip_files
    ]

    for result in results:
        print_result(result)

    extracted = sum(result.status == "extraído" for result in results)
    updated = sum(result.status == "atualizado" for result in results)
    skipped = sum(result.status == "ignorado" for result in results)
    print(
        f"\nConcluído: {extracted} extraído(s), "
        f"{updated} atualizado(s), {skipped} ignorado(s)."
    )


if __name__ == "__main__":
    main()
