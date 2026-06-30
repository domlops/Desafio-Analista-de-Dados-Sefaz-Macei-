# Plano de ação do desafio

Este arquivo é o meu ponto de partida para organizar o desafio. A ideia aqui não
é tentar resolver tudo de uma vez, mas dividir o trabalho em etapas menores,
entender os dados com calma e deixar esse caminho visível nos commits.

Como o desafio avalia tanto o resultado quanto o processo, quero usar este plano
como uma espécie de guia: o que preciso fazer, quais cuidados já percebi e em
que ordem faz sentido avançar.

## Objetivo do desafio

O desafio usa dados do FINBRA/Siconfi sobre despesas das capitais brasileiras no
relatório "Despesas por Função (Anexo I-E)". O objetivo principal é comparar
como as capitais gastam por área de governo, olhando principalmente para a
diferença entre o que foi empenhado e o que foi pago.

Em outras palavras, quero responder perguntas como:

- quanto cada capital comprometeu de gasto em cada função;
- quanto desse valor foi realmente pago dentro do ano;
- em quais funções a diferença entre empenhado e pago é maior;
- como Maceió aparece quando comparada com as outras capitais.

O indicador central da análise será a taxa de execução financeira:

```text
taxa de execução = despesas pagas / despesas empenhadas
```

Além dos valores totais, também pretendo olhar alguns números per capita. Isso é
importante porque comparar São Paulo e Vitória, por exemplo, só pelo valor total
não seria muito justo.

## Critérios que preciso atender

Pelo README do desafio, os principais pontos de avaliação são:

- ler os arquivos corretamente, respeitando encoding, separador, casas decimais
  e linhas iniciais de metadados;
- descompactar os dados por código, sem fazer essa parte manualmente;
- juntar os CSVs em uma única base;
- criar algum formato mais eficiente para consulta, como Parquet;
- organizar o código de um jeito que outra pessoa consiga rodar;
- mostrar cuidado com dados incompletos, principalmente em 2025;
- fazer análises que tenham sentido e não sejam apenas tabelas soltas;
- comunicar as conclusões de forma clara, incluindo limitações;
- manter commits frequentes, para mostrar a evolução do trabalho.

## Decisões iniciais

Vou seguir com Python, principalmente porque é uma escolha bem comum para esse
tipo de análise e também por ser a linguagem de programação que mais domino.

As primeiras decisões são:

- usar `pandas` para ler, tratar e consolidar os dados;
- salvar a base consolidada em Parquet, para não precisar reler todos os CSVs a
  cada nova análise;
- manter os arquivos originais em `dados_compactos/`, já que eles são a fonte
  bruta do desafio;
- gerar os CSVs extraídos em `dados_extraidos/`, mas sem versionar esses
  arquivos no git;
- gerar a base final em `dados_processados/`, também como saída reproduzível;
- usar `notebooks/` para exploração e análise;
- guardar tabelas e gráficos finais em `outputs/`;
- começar pela análise por função antes de entrar em subfunções, para não abrir
  o escopo demais logo no início;
- dar uma atenção especial a Maceió na etapa de interpretação dos resultados;
- manter o `README.md` original do desafio por enquanto. A ideia é reescrevê-lo
  mais para o final, quando já houver scripts, análises e resultados reais para
  documentar.

## Riscos e cuidados

O primeiro cuidado importante é o ano de 2025. Fiz uma checagem inicial da
quantidade de capitais por ano e o resultado foi:

```text
2020: 26 capitais
2021: 26 capitais
2022: 26 capitais
2023: 26 capitais
2024: 26 capitais
2025: 11 capitais
```

Então, para comparar evolução ao longo do tempo, o caminho mais seguro é usar
2020 a 2024. O ano de 2025 pode aparecer no projeto, mas como dado parcial, não
como se fosse diretamente comparável aos anos completos.

Outros cuidados que preciso manter no radar:

- a coluna `Conta` mistura funções, subfunções e totais. Se eu somar tudo sem
  separar, posso contar o mesmo valor mais de uma vez;
- os CSVs usam padrão brasileiro: encoding `latin-1`, separador `;`, decimal
  com vírgula e três linhas de metadados antes da tabela;
- valores absolutos podem gerar comparações injustas entre capitais de tamanhos
  muito diferentes;
- a taxa de execução precisa tratar casos em que o valor empenhado seja zero ou
  muito baixo;
- é melhor assumir poucas análises bem explicadas do que tentar cobrir todas as
  possibilidades e acabar deixando tudo superficial.

## Etapas planejadas

Quero que cada etapa abaixo vire um commit separado ou, pelo menos, um bloco bem
claro de commits. A ideia é construir o projeto aos poucos.

1. `docs: estruturação do repositório e registrar plano inicial`

   Criar este plano, preparar a estrutura básica do projeto e manter o README
   original como referência do enunciado por enquanto.

2. `feat: extrair arquivos compactados por código`

   Criar um script para encontrar os ZIPs em `dados_compactos/` e extrair cada
   `finbra.csv` para uma pasta separada por ano.

3. `feat: consolidar arquivos finbra em uma base única`

   Ler todos os CSVs com as configurações corretas, adicionar a coluna `ano` e
   juntar tudo em um único DataFrame.

4. `feat: classificar contas da despesa`

   Criar uma classificação para diferenciar função, subfunção, totais e linhas
   especiais como `FUxx - Demais Subfunções`.

5. `feat: gerar base consolidada em parquet`

   Salvar a base tratada em `dados_processados/finbra_consolidado.parquet` e
   deixar anotado no plano que essa decisão deverá aparecer na documentação
   final.

6. `test: adicionar validações básicas dos dados`

   Conferir colunas obrigatórias, tipos, anos disponíveis, quantidade de
   capitais por ano e possíveis problemas de valores nulos.

7. `analysis: diagnosticar estrutura e completude dos dados`

   Criar um notebook inicial para entender o tamanho da base, os anos, as
   capitais, os estágios da despesa e os tipos de conta.

8. `analysis: calcular taxa de execução por função`

   Comparar despesas empenhadas e pagas por ano, capital e função. Essa etapa
   deve gerar os primeiros rankings e tabelas úteis.

9. `analysis: comparar saúde educação e Maceió`

   Aprofundar a análise em Saúde e Educação, olhando valores absolutos, valores
   per capita e taxa de execução. Também quero posicionar Maceió em relação às
   demais capitais.

10. `docs: consolidar conclusões e limitações`

    Reescrever o README com base no que foi realmente feito, incluindo
    metodologia, principais achados, limitações e instruções para reproduzir o
    projeto.

## Resultado que quero entregar

No fim, quero que o repositório conte uma história simples:

1. recebi os dados brutos;
2. entendi as principais pegadinhas do formato;
3. criei um pipeline para extrair e consolidar a base;
4. validei se os dados estavam completos o suficiente para análise;
5. calculei indicadores comparáveis entre capitais;
6. destaquei achados relevantes, especialmente para Maceió;
7. deixei claro o que dá para concluir e o que precisa ser visto com cautela.
