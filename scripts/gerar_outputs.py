from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_FILE = PROJECT_ROOT / "dados_processados" / "finbra_consolidado.parquet"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
ANOS_COMPLETOS = [2020, 2021, 2022, 2023, 2024]
ANO_REFERENCIA = 2024
FUNCOES_PRIORITARIAS = ["Saúde", "Educação"]
MACEIO_PATTERN = "Maceió"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gera tabelas e gráficos finais da análise de execução financeira "
            "das capitais."
        )
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="Base consolidada em Parquet. Padrão: dados_processados/finbra_consolidado.parquet",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Pasta onde os arquivos finais serão salvos. Padrão: outputs/",
    )
    return parser.parse_args()


def format_percent(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%".replace(".", ",")


def percent_axis(value: float, _position: int) -> str:
    return format_percent(value, decimals=0)


def format_currency_br(value: float) -> str:
    formatted = f"R$ {value:,.0f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def currency_axis(value: float, _position: int) -> str:
    return format_currency_br(value)


def add_capital_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["capital"] = df["Instituição"].str.replace(
        r"^Prefeitura Municipal (?:de |do |da )", "", regex=True
    )
    return df


def load_dataset(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_file}")

    return add_capital_column(pd.read_parquet(input_file))


def build_function_execution(df: pd.DataFrame) -> pd.DataFrame:
    base_funcoes = df[
        (df["tipo_conta"] == "função")
        & (df["Coluna"].isin(["Despesas Empenhadas", "Despesas Pagas"]))
    ].copy()

    index_columns = [
        "ano",
        "Instituição",
        "capital",
        "Cod.IBGE",
        "UF",
        "População",
        "codigo_funcao",
        "nome_funcao",
    ]

    execution = (
        base_funcoes.pivot_table(
            index=index_columns,
            columns="Coluna",
            values="Valor",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename(
            columns={
                "Despesas Empenhadas": "valor_empenhado",
                "Despesas Pagas": "valor_pago",
            }
        )
    )

    for column in ["valor_empenhado", "valor_pago"]:
        if column not in execution.columns:
            execution[column] = 0.0

    execution["taxa_execucao"] = np.where(
        execution["valor_empenhado"] > 0,
        execution["valor_pago"] / execution["valor_empenhado"],
        np.nan,
    )
    execution["taxa_execucao_percentual"] = execution["taxa_execucao"] * 100
    execution["diferenca_empenhado_pago"] = (
        execution["valor_empenhado"] - execution["valor_pago"]
    )
    execution["valor_pago_per_capita"] = (
        execution["valor_pago"] / execution["População"]
    )
    execution["ano_parcial"] = ~execution["ano"].isin(ANOS_COMPLETOS)

    return execution


def build_capital_ranking(execution: pd.DataFrame) -> pd.DataFrame:
    ranking = (
        execution[execution["ano"] == ANO_REFERENCIA]
        .groupby(["capital", "UF", "Cod.IBGE"], as_index=False)
        .agg(
            populacao=("População", "first"),
            valor_empenhado=("valor_empenhado", "sum"),
            valor_pago=("valor_pago", "sum"),
        )
    )

    ranking["taxa_execucao"] = ranking["valor_pago"] / ranking["valor_empenhado"]
    ranking["taxa_execucao_percentual"] = ranking["taxa_execucao"] * 100
    ranking["valor_pago_per_capita"] = ranking["valor_pago"] / ranking["populacao"]
    ranking = ranking.sort_values("taxa_execucao", ascending=False).reset_index(
        drop=True
    )
    ranking.insert(0, "rank_taxa_execucao", ranking.index + 1)
    return ranking


def build_function_ranking(execution: pd.DataFrame) -> pd.DataFrame:
    ranking = (
        execution[execution["ano"] == ANO_REFERENCIA]
        .groupby(["codigo_funcao", "nome_funcao"], as_index=False)
        .agg(
            capitais=("Cod.IBGE", "nunique"),
            populacao_base=("População", "sum"),
            valor_empenhado=("valor_empenhado", "sum"),
            valor_pago=("valor_pago", "sum"),
        )
    )

    ranking["taxa_execucao"] = ranking["valor_pago"] / ranking["valor_empenhado"]
    ranking["taxa_execucao_percentual"] = ranking["taxa_execucao"] * 100
    ranking["valor_pago_per_capita"] = (
        ranking["valor_pago"] / ranking["populacao_base"]
    )
    ranking = ranking.sort_values("taxa_execucao", ascending=True).reset_index(
        drop=True
    )
    ranking.insert(0, "rank_menor_taxa_execucao", ranking.index + 1)
    return ranking


def build_maceio_comparison(execution: pd.DataFrame) -> pd.DataFrame:
    selected = execution[
        execution["ano"].isin(ANOS_COMPLETOS)
        & execution["nome_funcao"].isin(FUNCOES_PRIORITARIAS)
    ].copy()

    maceio = selected[
        selected["capital"].str.contains(MACEIO_PATTERN, case=False, na=False)
    ].copy()
    other_capitals = selected[
        ~selected["capital"].str.contains(MACEIO_PATTERN, case=False, na=False)
    ].copy()

    reference = (
        other_capitals.groupby(["ano", "nome_funcao"], as_index=False)
        .agg(
            taxa_mediana_capitais=("taxa_execucao", "median"),
            taxa_media_capitais=("taxa_execucao", "mean"),
            pago_pc_mediana_capitais=("valor_pago_per_capita", "median"),
            pago_pc_media_capitais=("valor_pago_per_capita", "mean"),
        )
    )

    comparison = maceio.merge(reference, on=["ano", "nome_funcao"], how="left")
    comparison["taxa_execucao_percentual"] = comparison["taxa_execucao"] * 100
    comparison["taxa_mediana_capitais_percentual"] = (
        comparison["taxa_mediana_capitais"] * 100
    )
    comparison["dif_taxa_vs_mediana_pontos"] = (
        comparison["taxa_execucao"] - comparison["taxa_mediana_capitais"]
    ) * 100
    comparison["dif_pago_pc_vs_mediana"] = (
        comparison["valor_pago_per_capita"]
        - comparison["pago_pc_mediana_capitais"]
    )

    columns = [
        "ano",
        "capital",
        "UF",
        "nome_funcao",
        "valor_empenhado",
        "valor_pago",
        "taxa_execucao_percentual",
        "taxa_mediana_capitais_percentual",
        "dif_taxa_vs_mediana_pontos",
        "valor_pago_per_capita",
        "pago_pc_mediana_capitais",
        "dif_pago_pc_vs_mediana",
    ]
    return comparison[columns].sort_values(["nome_funcao", "ano"]).reset_index(
        drop=True
    )


def build_maceio_positions(execution: pd.DataFrame) -> pd.DataFrame:
    selected = execution[
        (execution["ano"] == ANO_REFERENCIA)
        & execution["nome_funcao"].isin(FUNCOES_PRIORITARIAS)
    ].copy()

    selected["rank_taxa_execucao"] = (
        selected.groupby("nome_funcao")["taxa_execucao"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    selected["rank_pago_per_capita"] = (
        selected.groupby("nome_funcao")["valor_pago_per_capita"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    selected["total_capitais"] = selected.groupby("nome_funcao")[
        "Cod.IBGE"
    ].transform("nunique")
    selected["taxa_execucao_percentual"] = selected["taxa_execucao"] * 100

    columns = [
        "ano",
        "capital",
        "nome_funcao",
        "taxa_execucao_percentual",
        "rank_taxa_execucao",
        "valor_pago_per_capita",
        "rank_pago_per_capita",
        "total_capitais",
    ]
    return selected[
        selected["capital"].str.contains(MACEIO_PATTERN, case=False, na=False)
    ][columns].sort_values("nome_funcao")


def build_maceio_subfunctions(df: pd.DataFrame, execution: pd.DataFrame) -> pd.DataFrame:
    paid_function_totals = execution[
        (execution["ano"] == ANO_REFERENCIA)
        & execution["capital"].str.contains(MACEIO_PATTERN, case=False, na=False)
        & execution["nome_funcao"].isin(FUNCOES_PRIORITARIAS)
    ][["codigo_funcao", "nome_funcao", "valor_pago"]].rename(
        columns={"valor_pago": "valor_pago_funcao"}
    )

    base = df[
        (df["ano"] == ANO_REFERENCIA)
        & df["capital"].str.contains(MACEIO_PATTERN, case=False, na=False)
        & df["nome_funcao"].isin(FUNCOES_PRIORITARIAS)
        & df["tipo_conta"].isin(["subfunção", "demais_subfunções"])
        & (df["Coluna"] == "Despesas Pagas")
    ].copy()

    subfunctions = (
        base.groupby(
            [
                "codigo_funcao",
                "nome_funcao",
                "tipo_conta",
                "codigo_conta",
                "nome_conta",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(valor_pago=("Valor", "sum"))
        .merge(paid_function_totals, on=["codigo_funcao", "nome_funcao"], how="left")
    )
    subfunctions["participacao_no_pago_funcao_percentual"] = (
        subfunctions["valor_pago"] / subfunctions["valor_pago_funcao"] * 100
    )
    return subfunctions.sort_values(
        ["nome_funcao", "valor_pago"], ascending=[True, False]
    ).reset_index(drop=True)


def save_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, sep=";", decimal=",", encoding="utf-8")


def plot_capital_ranking(ranking: pd.DataFrame, path: Path) -> None:
    plot_data = ranking.sort_values("taxa_execucao_percentual", ascending=True)
    colors = np.where(
        plot_data["capital"].str.contains(MACEIO_PATTERN, case=False, na=False),
        "#c8553d",
        "#3a7ca5",
    )

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.hlines(
        y=plot_data["capital"],
        xmin=plot_data["taxa_execucao_percentual"].min() - 1,
        xmax=plot_data["taxa_execucao_percentual"],
        color="#d8dee4",
        linewidth=1,
    )
    ax.scatter(
        plot_data["taxa_execucao_percentual"],
        plot_data["capital"],
        color=colors,
        s=46,
        zorder=3,
    )
    ax.axvline(
        ranking["taxa_execucao_percentual"].median(),
        color="#555555",
        linestyle="--",
        linewidth=1,
        label="Mediana das capitais",
    )
    ax.set_title(f"Taxa de execução financeira por capital em {ANO_REFERENCIA}")
    ax.set_xlabel("Despesas pagas / despesas empenhadas")
    ax.set_ylabel("")
    ax.xaxis.set_major_formatter(FuncFormatter(percent_axis))
    ax.grid(axis="x", alpha=0.2)
    ax.legend(loc="lower right")
    sns.despine(left=True, bottom=False)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_maceio_vs_median(comparison: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    handles = None
    labels = None

    for ax, function_name in zip(axes, FUNCOES_PRIORITARIAS):
        data = comparison[comparison["nome_funcao"] == function_name].sort_values(
            "ano"
        )
        maceio_line = ax.plot(
            data["ano"],
            data["taxa_execucao_percentual"],
            marker="o",
            linewidth=2,
            label="Maceió",
            color="#c8553d",
        )
        median_line = ax.plot(
            data["ano"],
            data["taxa_mediana_capitais_percentual"],
            marker="o",
            linewidth=2,
            label="Mediana das demais capitais",
            color="#3a7ca5",
        )
        ax.set_title(function_name)
        ax.set_xlabel("Ano")
        ax.set_xticks(ANOS_COMPLETOS)
        ax.grid(axis="y", alpha=0.2)
        ax.yaxis.set_major_formatter(FuncFormatter(percent_axis))
        handles = [maceio_line[0], median_line[0]]
        labels = ["Maceió", "Mediana das demais capitais"]

    axes[0].set_ylabel("Taxa de execução financeira")
    if handles and labels:
        fig.legend(
            handles,
            labels,
            loc="lower center",
            ncol=2,
            frameon=False,
            bbox_to_anchor=(0.5, -0.02),
        )
    fig.suptitle("Maceió versus mediana das demais capitais", y=1.03)
    sns.despine()
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_maceio_positions(
    comparison: pd.DataFrame,
    positions: pd.DataFrame,
    path: Path,
) -> None:
    comparison_2024 = comparison[comparison["ano"] == ANO_REFERENCIA].merge(
        positions[
            [
                "nome_funcao",
                "rank_taxa_execucao",
                "rank_pago_per_capita",
                "total_capitais",
            ]
        ],
        on="nome_funcao",
        how="left",
    )
    comparison_2024["nome_funcao"] = pd.Categorical(
        comparison_2024["nome_funcao"],
        categories=FUNCOES_PRIORITARIAS,
        ordered=True,
    )
    comparison_2024 = comparison_2024.sort_values("nome_funcao")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    x = np.arange(len(comparison_2024))
    width = 0.34

    panels = [
        {
            "ax": axes[0],
            "title": "Taxa de execução",
            "maceio": "taxa_execucao_percentual",
            "median": "taxa_mediana_capitais_percentual",
            "rank": "rank_taxa_execucao",
            "formatter": lambda value: format_percent(value, decimals=1),
            "axis_formatter": FuncFormatter(percent_axis),
            "ylabel": "Despesas pagas / despesas empenhadas",
            "ylim": (0, 112),
        },
        {
            "ax": axes[1],
            "title": "Valor pago per capita",
            "maceio": "valor_pago_per_capita",
            "median": "pago_pc_mediana_capitais",
            "rank": "rank_pago_per_capita",
            "formatter": format_currency_br,
            "axis_formatter": FuncFormatter(currency_axis),
            "ylabel": "Valor pago por habitante",
            "ylim": (0, 1600),
        },
    ]

    for panel in panels:
        ax = panel["ax"]
        maceio_values = comparison_2024[panel["maceio"]].to_numpy()
        median_values = comparison_2024[panel["median"]].to_numpy()

        maceio_bars = ax.bar(
            x - width / 2,
            maceio_values,
            width,
            label="Maceió",
            color="#c8553d",
        )
        median_bars = ax.bar(
            x + width / 2,
            median_values,
            width,
            label="Mediana das demais capitais",
            color="#3a7ca5",
        )

        maceio_labels = []
        median_labels = []
        for row in comparison_2024.itertuples(index=False):
            rank = int(getattr(row, panel["rank"]))
            total_capitals = int(row.total_capitais)
            maceio_value = getattr(row, panel["maceio"])
            median_value = getattr(row, panel["median"])
            maceio_labels.append(
                f"{panel['formatter'](maceio_value)}\n{rank}º/{total_capitals}"
            )
            median_labels.append(panel["formatter"](median_value))

        ax.bar_label(
            maceio_bars,
            labels=maceio_labels,
            padding=4,
            fontsize=9,
            fontweight="bold",
        )
        ax.bar_label(
            median_bars,
            labels=median_labels,
            padding=4,
            fontsize=9,
        )

        ax.set_title(panel["title"])
        ax.set_ylabel(panel["ylabel"])
        ax.set_xticks(x)
        ax.set_xticklabels(comparison_2024["nome_funcao"])
        ax.set_ylim(*panel["ylim"])
        ax.yaxis.set_major_formatter(panel["axis_formatter"])
        ax.grid(axis="y", alpha=0.2)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle(
        f"Maceió versus mediana das demais capitais em {ANO_REFERENCIA}",
        y=1.02,
    )
    sns.despine()
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def gerar_outputs(
    input_file: Path = DEFAULT_INPUT_FILE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    sns.set_theme(style="whitegrid", context="notebook")

    df = load_dataset(input_file)
    execution = build_function_execution(df)
    ranking_capitals = build_capital_ranking(execution)
    ranking_functions = build_function_ranking(execution)
    maceio_comparison = build_maceio_comparison(execution)
    maceio_positions = build_maceio_positions(execution)
    maceio_subfunctions = build_maceio_subfunctions(df, execution)

    tables_dir = output_dir / "tabelas"
    figures_dir = output_dir / "figuras"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    generated_files = {
        "ranking_capitais_2024": tables_dir / "ranking_capitais_2024.csv",
        "ranking_funcoes_2024": tables_dir / "ranking_funcoes_2024.csv",
        "maceio_saude_educacao_2020_2024": tables_dir
        / "maceio_saude_educacao_2020_2024.csv",
        "maceio_subfuncoes_saude_educacao_2024": tables_dir
        / "maceio_subfuncoes_saude_educacao_2024.csv",
        "fig_ranking_capitais_2024": figures_dir
        / "ranking_capitais_taxa_execucao_2024.png",
        "fig_maceio_vs_mediana": figures_dir
        / "maceio_vs_mediana_taxa_execucao_saude_educacao.png",
        "fig_posicao_maceio": figures_dir
        / "posicao_maceio_saude_educacao_2024.png",
    }

    save_table(ranking_capitals, generated_files["ranking_capitais_2024"])
    save_table(ranking_functions, generated_files["ranking_funcoes_2024"])
    save_table(
        maceio_comparison, generated_files["maceio_saude_educacao_2020_2024"]
    )
    save_table(
        maceio_subfunctions,
        generated_files["maceio_subfuncoes_saude_educacao_2024"],
    )

    plot_capital_ranking(
        ranking_capitals, generated_files["fig_ranking_capitais_2024"]
    )
    plot_maceio_vs_median(maceio_comparison, generated_files["fig_maceio_vs_mediana"])
    plot_maceio_positions(
        maceio_comparison,
        maceio_positions,
        generated_files["fig_posicao_maceio"],
    )

    return generated_files


def display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return path


def main() -> None:
    args = parse_args()
    generated_files = gerar_outputs(args.entrada, args.saida)

    print("Arquivos gerados:")
    for path in generated_files.values():
        print(f"- {display_path(path)}")


if __name__ == "__main__":
    main()
