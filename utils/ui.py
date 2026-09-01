"""
componentes de interface que nao dependem do pandas.

o motivo de existir este modulo, em alguns computadores com politica
de controle de aplicativo do windows, o pandas nao consegue nem ser
importado, porque uma dll interna dele e bloqueada pela politica. como
st.dataframe, st.table e st.line_chart importam pandas por baixo dos
panos, esses componentes prontos do streamlit quebram nessas maquinas,
mesmo sem nenhum motivo relacionado ao codigo deste projeto.

para nao depender disso, as telas do app usam as duas funcoes abaixo
no lugar de st.dataframe e st.line_chart, sem importar pandas em
nenhum momento.
"""

import html

import streamlit as st


def renderizar_tabela_html(linhas, colunas=None):
    """
    desenha uma tabela simples em html a partir de uma lista de
    dicionarios, sem passar em nenhum momento por pandas.

    linhas, lista de dicionarios com os dados a mostrar
    colunas, lista opcional no formato [(chave, rotulo), ...], com a
    ordem e o rotulo de cada coluna. se nao for informado, usa as
    chaves do primeiro dicionario, na ordem em que aparecem
    """
    if not linhas:
        st.info("nenhum dado para mostrar")
        return

    if colunas is None:
        colunas = [(chave, chave) for chave in linhas[0].keys()]

    cabecalho = "".join(f"<th>{html.escape(str(rotulo))}</th>" for _, rotulo in colunas)

    corpo = []
    for linha in linhas:
        celulas = "".join(
            f"<td>{html.escape(str(linha.get(chave, '')))}</td>" for chave, _ in colunas
        )
        corpo.append(f"<tr>{celulas}</tr>")

    tabela_html = f"""
    <div style="overflow-x:auto;">
    <table class="tabela-sem-pandas">
        <thead><tr>{cabecalho}</tr></thead>
        <tbody>{''.join(corpo)}</tbody>
    </table>
    </div>
    <style>
        .tabela-sem-pandas {{
            width: 100%;
            border-collapse: collapse;
        }}
        .tabela-sem-pandas th, .tabela-sem-pandas td {{
            border-bottom: 1px solid rgba(128, 128, 128, 0.3);
            padding: 6px 10px;
            text-align: left;
            font-size: 0.9rem;
        }}
        .tabela-sem-pandas th {{
            font-weight: 600;
        }}
    </style>
    """
    st.markdown(tabela_html, unsafe_allow_html=True)


def renderizar_grafico_linha_svg(rotulos, valores, altura=220, cor="#4c8bf5"):
    """
    desenha um grafico de linha simples em svg puro, sem pandas e sem
    altair, a partir de duas listas do mesmo tamanho, rotulos do eixo
    x e valores do eixo y.
    """
    if not valores or len(valores) != len(rotulos):
        st.info("sem dados suficientes para desenhar o grafico")
        return

    largura = 700
    margem_esquerda = 55
    margem_direita = 20
    margem_topo = 20
    margem_baixo = 30

    minimo = min(valores)
    maximo = max(valores)
    if minimo == maximo:
        minimo -= 1
        maximo += 1

    area_largura = largura - margem_esquerda - margem_direita
    area_altura = altura - margem_topo - margem_baixo

    n = len(valores)
    passo_x = area_largura / (n - 1) if n > 1 else 0

    pontos = []
    for indice, valor in enumerate(valores):
        x = margem_esquerda + indice * passo_x
        proporcao = (valor - minimo) / (maximo - minimo)
        y = margem_topo + area_altura - (proporcao * area_altura)
        pontos.append((x, y))

    linha_pontos = " ".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    circulos = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{cor}"></circle>' for x, y in pontos
    )

    passo_rotulo = max(1, n // 6)
    rotulos_x = "".join(
        f'<text x="{pontos[i][0]:.1f}" y="{altura - 8}" font-size="10" '
        f'text-anchor="middle" fill="currentColor" opacity="0.7">'
        f'{html.escape(str(rotulos[i]))}</text>'
        for i in range(0, n, passo_rotulo)
    )

    svg = f"""
    <svg viewBox="0 0 {largura} {altura}" width="100%" height="{altura}"
         xmlns="http://www.w3.org/2000/svg">
        <line x1="{margem_esquerda}" y1="{margem_topo}"
              x2="{margem_esquerda}" y2="{margem_topo + area_altura}"
              stroke="currentColor" opacity="0.3"></line>
        <line x1="{margem_esquerda}" y1="{margem_topo + area_altura}"
              x2="{largura - margem_direita}" y2="{margem_topo + area_altura}"
              stroke="currentColor" opacity="0.3"></line>
        <text x="5" y="{margem_topo + 5}" font-size="10" fill="currentColor" opacity="0.7">{maximo:.2f}</text>
        <text x="5" y="{margem_topo + area_altura}" font-size="10" fill="currentColor" opacity="0.7">{minimo:.2f}</text>
        <polyline points="{linha_pontos}" fill="none" stroke="{cor}" stroke-width="2"></polyline>
        {circulos}
        {rotulos_x}
    </svg>
    """
    st.markdown(svg, unsafe_allow_html=True)
