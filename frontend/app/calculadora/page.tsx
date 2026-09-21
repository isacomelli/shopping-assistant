"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card } from "@/components/Card";
import { OfertaForm } from "@/components/OfertaForm";
import { RankingCard } from "@/components/RankingCard";
import { api } from "@/lib/api";
import { formatarMoeda } from "@/lib/format";
import type { Cartao, Oferta, Perfil, Produto } from "@/lib/types";

const NOMES_FONTES: Record<string, string> = {
  google_shopping: "Google Shopping",
  buscape: "Buscapé",
};

export default function PaginaCalculadora() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-500">Carregando.</p>}>
      <ConteudoCalculadora />
    </Suspense>
  );
}

function ConteudoCalculadora() {
  const searchParams = useSearchParams();
  const produtoIdNaUrl = searchParams.get("produtoId");
  const ofertaIdParaEditar = searchParams.get("ofertaId");

  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [cartoes, setCartoes] = useState<Cartao[]>([]);
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [produtoId, setProdutoId] = useState<number | null>(
    produtoIdNaUrl ? Number(produtoIdNaUrl) : null,
  );
  const [ofertas, setOfertas] = useState<Oferta[]>([]);
  const [carregandoOfertas, setCarregandoOfertas] = useState(false);
  const [pesquisando, setPesquisando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listarProdutos(), api.listarCartoes(), api.obterPerfil()]).then(
      ([listaProdutos, listaCartoes, perfilAtual]) => {
        setProdutos(listaProdutos);
        setCartoes(listaCartoes);
        setPerfil(perfilAtual);
        if (produtoId === null && listaProdutos.length > 0) {
          setProdutoId(listaProdutos[0].id);
        }
      },
    );
  }, []);

  async function carregarOfertas(id: number) {
    setCarregandoOfertas(true);
    try {
      const lista = await api.listarOfertas(id);
      setOfertas(lista);
    } finally {
      setCarregandoOfertas(false);
    }
  }

  useEffect(() => {
    if (produtoId !== null) {
      carregarOfertas(produtoId);
    }
  }, [produtoId]);

  const produtoAtual = useMemo(
    () => produtos.find((produto) => produto.id === produtoId) ?? null,
    [produtos, produtoId],
  );

  const ranking = useMemo(() => {
    if (!produtoAtual?.preco_alvo) return ofertas;
    return ofertas.filter((oferta) => oferta.resultado.preco_efetivo <= produtoAtual.preco_alvo!);
  }, [ofertas, produtoAtual]);

  async function pesquisarAutomaticamente(forcarAtualizacao: boolean) {
    if (produtoId === null) return;
    setPesquisando(true);
    setErro(null);
    setMensagem(null);
    setAviso(null);
    try {
      const resposta = await api.pesquisarAutomaticamente(produtoId, forcarAtualizacao);
      await carregarOfertas(produtoId);

      const origemMensagem = resposta.veio_do_cache
        ? "resultado reaproveitado do cache local"
        : "ofertas atualizadas agora";
      const avisos = Object.entries(resposta.fontes_com_erro).map(
        ([fonte, detalhe]) => `${NOMES_FONTES[fonte] ?? fonte} sem resposta, ${detalhe}`,
      );

      setMensagem(`${resposta.resultados.length} oferta(s) encontrada(s), ${origemMensagem}.`);
      setAviso(avisos.length > 0 ? avisos.join(" ") : null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível pesquisar as ofertas agora.");
    } finally {
      setPesquisando(false);
    }
  }

  async function salvarNovaOferta(payload: Parameters<typeof api.criarOferta>[1]) {
    if (produtoId === null) return;
    await api.criarOferta(produtoId, payload);
    await carregarOfertas(produtoId);
  }

  async function salvarEdicao(ofertaId: number, payload: Parameters<typeof api.atualizarOferta>[2]) {
    if (produtoId === null) return;
    await api.atualizarOferta(produtoId, ofertaId, payload);
    await carregarOfertas(produtoId);
  }

  async function excluirOferta(ofertaId: number) {
    if (produtoId === null) return;
    await api.excluirOferta(produtoId, ofertaId);
    await carregarOfertas(produtoId);
  }

  if (produtos.length === 0) {
    return (
      <Card title="Calculadora de compra inteligente">
        <p className="text-sm text-ink-500">
          Nenhum produto cadastrado. Crie um produto na Wishlist antes de pesquisar preços.
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          Calculadora de Compra Inteligente
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Ranking de ofertas pelo custo efetivo, considerando Pix, cartão, pontos e cashback, a partir do Google Shopping, com o Buscapé como fonte complementar.
        </p>
      </div>

      <Card>
        <div className="flex items-end justify-between gap-4">
          <div className="flex-1">
            <label className="field-label">Produto</label>
            <select
              className="field-input"
              value={produtoId ?? ""}
              onChange={(e) => setProdutoId(Number(e.target.value))}
            >
              {produtos.map((produto) => (
                <option key={produto.id} value={produto.id}>
                  {produto.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button
              className="btn-secondary"
              onClick={() => pesquisarAutomaticamente(false)}
              disabled={pesquisando}
            >
              {pesquisando ? "Consultando." : "Pesquisar ofertas"}
            </button>
            <button
              className="btn-primary"
              onClick={() => pesquisarAutomaticamente(true)}
              disabled={pesquisando}
            >
              {pesquisando ? "Consultando." : "Forçar atualização"}
            </button>
          </div>
        </div>

        {produtoAtual && (
          <p className="mt-3 text-sm text-ink-500">
            Categoria: {produtoAtual.categoria || "sem categoria"} · Preço alvo:{" "}
            {formatarMoeda(produtoAtual.preco_alvo)} · Orçamento: {formatarMoeda(produtoAtual.orcamento)}
          </p>
        )}

        {mensagem && <p className="mt-3 text-sm text-brand-700">{mensagem}</p>}
        {aviso && <p className="mt-3 text-sm text-alert-500">{aviso}</p>}
        {erro && <p className="mt-3 text-sm text-red-600">{erro}</p>}
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-500">
          Ranking de ofertas
        </h2>
        {carregandoOfertas ? (
          <p className="text-sm text-ink-500">Carregando ofertas.</p>
        ) : ranking.length === 0 ? (
          <p className="text-sm text-ink-500">
            Nenhuma oferta cadastrada ainda para este produto.
          </p>
        ) : (
          ranking.map((oferta, indice) => (
            <RankingCard
              key={oferta.id}
              oferta={oferta}
              posicao={indice}
              cartoes={cartoes}
              perfil={perfil ?? undefined}
              aoSalvarEdicao={(payload) => salvarEdicao(oferta.id, payload)}
              aoExcluir={() => excluirOferta(oferta.id)}
              abrirEditando={ofertaIdParaEditar !== null && Number(ofertaIdParaEditar) === oferta.id}
            />
          ))
        )}
      </div>

      <Card
        title="Adicionar oferta manualmente"
        subtitle="Útil para preços de loja física, negociações ou promoções que a busca automática não encontra."
      >
        <OfertaForm cartoes={cartoes} perfil={perfil ?? undefined} aoSalvar={salvarNovaOferta} />
      </Card>
    </div>
  );
}
