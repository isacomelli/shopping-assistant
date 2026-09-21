"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { api } from "@/lib/api";
import type { Cartao, Perfil } from "@/lib/types";

const PERFIL_VAZIO: Perfil = {
  rendimento_mensal: 1.1,
  cotacao_dolar: 5.4,
  valor_milheiro_padrao: 30,
  percentual_bonus_transferencia_padrao: 80,
  parcelas_padrao: 6,
};

export default function PaginaPerfil() {
  const [perfil, setPerfil] = useState<Perfil>(PERFIL_VAZIO);
  const [cartoes, setCartoes] = useState<Cartao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [buscandoCotacao, setBuscandoCotacao] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [nomeCartao, setNomeCartao] = useState("");
  const [pontosPorDolarCartao, setPontosPorDolarCartao] = useState(0);
  const [cashbackCartao, setCashbackCartao] = useState(0);

  async function carregar() {
    const [perfilAtual, listaCartoes] = await Promise.all([api.obterPerfil(), api.listarCartoes()]);
    setPerfil(perfilAtual);
    setCartoes(listaCartoes);
    setCarregando(false);
  }

  useEffect(() => {
    carregar();
  }, []);

  function atualizar<K extends keyof Perfil>(campo: K, valor: Perfil[K]) {
    setPerfil((atual) => ({ ...atual, [campo]: valor }));
  }

  async function salvarPerfil() {
    setErro(null);
    setMensagem(null);
    setSalvando(true);
    try {
      const perfilSalvo = await api.salvarPerfil(perfil);
      setPerfil(perfilSalvo);
      setMensagem("Perfil salvo com sucesso.");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar o perfil agora.");
    } finally {
      setSalvando(false);
    }
  }

  async function buscarCotacaoAtual() {
    setBuscandoCotacao(true);
    setErro(null);
    try {
      const resposta = await api.obterCotacaoDolar();
      if (resposta.encontrada && resposta.cotacao_dolar !== null) {
        atualizar("cotacao_dolar", resposta.cotacao_dolar);
        setMensagem("Cotação do dólar atualizada, lembre de salvar o perfil.");
      } else {
        setErro("Não foi possível consultar a cotação agora, mantendo o valor já salvo.");
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível consultar a cotação agora.");
    } finally {
      setBuscandoCotacao(false);
    }
  }

  async function adicionarCartao() {
    if (!nomeCartao.trim()) return;
    const listaAtualizada = await api.adicionarCartao({
      nome: nomeCartao.trim(),
      pontos_por_dolar: pontosPorDolarCartao,
      cashback_pct: cashbackCartao,
    });
    setCartoes(listaAtualizada);
    setNomeCartao("");
    setPontosPorDolarCartao(0);
    setCashbackCartao(0);
  }

  async function removerCartao(cartaoId: number) {
    const listaAtualizada = await api.removerCartao(cartaoId);
    setCartoes(listaAtualizada);
  }

  if (carregando) {
    return <p className="text-sm text-ink-500">Carregando.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Perfil</h1>
        <p className="mt-1 text-sm text-ink-500">
          Rendimento, cotação do dólar e valores padrão usados nos cálculos de custo efetivo.
        </p>
      </div>

      <Card
        title="Dados financeiros"
        subtitle="Usados para comparar Pix com parcelamento e para valorizar pontos e milhas."
      >
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="field-label">Rendimento mensal líquido (%)</label>
            <input
              type="number"
              step="0.1"
              className="field-input"
              value={perfil.rendimento_mensal}
              onChange={(e) => atualizar("rendimento_mensal", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Cotação do dólar (R$)</label>
            <div className="flex gap-2">
              <input
                type="number"
                step="0.1"
                className="field-input"
                value={perfil.cotacao_dolar}
                onChange={(e) => atualizar("cotacao_dolar", Number(e.target.value))}
              />
              <button
                type="button"
                className="btn-secondary shrink-0"
                onClick={buscarCotacaoAtual}
                disabled={buscandoCotacao}
              >
                {buscandoCotacao ? "Buscando." : "Buscar atual"}
              </button>
            </div>
          </div>
          <div>
            <label className="field-label">Valor do milheiro padrão (R$)</label>
            <input
              type="number"
              step="1"
              className="field-input"
              value={perfil.valor_milheiro_padrao}
              onChange={(e) => atualizar("valor_milheiro_padrao", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Bônus de transferência padrão (%)</label>
            <input
              type="number"
              step="5"
              className="field-input"
              value={perfil.percentual_bonus_transferencia_padrao}
              onChange={(e) => atualizar("percentual_bonus_transferencia_padrao", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Número de parcelas padrão</label>
            <input
              type="number"
              min={1}
              max={24}
              className="field-input"
              value={perfil.parcelas_padrao}
              onChange={(e) => atualizar("parcelas_padrao", Number(e.target.value))}
            />
          </div>
        </div>

        {mensagem && <p className="mt-3 text-sm text-brand-700">{mensagem}</p>}
        {erro && <p className="mt-3 text-sm text-red-600">{erro}</p>}

        <button className="btn-primary mt-4" onClick={salvarPerfil} disabled={salvando}>
          {salvando ? "Salvando." : "Salvar perfil"}
        </button>
      </Card>

      <Card
        title="Cartões de crédito"
        subtitle="Pontos por dólar e cashback de cada cartão, usados na calculadora e na pesquisa automática."
      >
        <div className="grid grid-cols-4 items-end gap-4">
          <div>
            <label className="field-label">Nome do cartão</label>
            <input
              className="field-input"
              value={nomeCartao}
              onChange={(e) => setNomeCartao(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Pontos por dólar</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={pontosPorDolarCartao}
              onChange={(e) => setPontosPorDolarCartao(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Cashback (%)</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={cashbackCartao}
              onChange={(e) => setCashbackCartao(Number(e.target.value))}
            />
          </div>
          <button className="btn-primary" onClick={adicionarCartao}>
            Adicionar cartão
          </button>
        </div>

        <div className="mt-5 flex flex-col gap-2">
          {cartoes.length === 0 ? (
            <p className="text-sm text-ink-500">Nenhum cartão cadastrado ainda.</p>
          ) : (
            cartoes.map((cartao) => (
              <div
                key={cartao.id}
                className="flex items-center justify-between rounded-lg border border-ink-300/30 px-4 py-2.5"
              >
                <div>
                  <p className="text-sm font-medium text-ink-900">{cartao.nome}</p>
                  <p className="text-xs text-ink-500">
                    {cartao.pontos_por_dolar} pontos por dólar · {cartao.cashback_pct}% de cashback
                  </p>
                </div>
                <button className="btn-ghost-danger" onClick={() => removerCartao(cartao.id)}>
                  Remover
                </button>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
