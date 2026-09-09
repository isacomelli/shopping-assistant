"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { api } from "@/lib/api";
import { formatarMoeda } from "@/lib/format";
import type { Cartao, Perfil } from "@/lib/types";

export default function PaginaPerfil() {
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [cartoes, setCartoes] = useState<Cartao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);

  const [novoCartaoNome, setNovoCartaoNome] = useState("");
  const [novoCartaoPontos, setNovoCartaoPontos] = useState(0);
  const [novoCartaoCashback, setNovoCartaoCashback] = useState(0);

  async function carregarTudo() {
    const [perfilAtual, cartoesAtuais] = await Promise.all([
      api.obterPerfil(),
      api.listarCartoes(),
    ]);
    setPerfil(perfilAtual);
    setCartoes(cartoesAtuais);
    setCarregando(false);
  }

  useEffect(() => {
    carregarTudo();
  }, []);

  useEffect(() => {
    api.obterCotacaoDolar().then((resultado) => {
      if (resultado.encontrada && resultado.cotacao_dolar) {
        setPerfil((atual) => (atual ? { ...atual, cotacao_dolar: resultado.cotacao_dolar! } : atual));
      }
    });
  }, []);

  async function salvarPerfil() {
    if (!perfil) return;
    setSalvando(true);
    setMensagem(null);
    try {
      const atualizado = await api.salvarPerfil(perfil);
      setPerfil(atualizado);
      setMensagem("Perfil salvo com sucesso.");
    } finally {
      setSalvando(false);
    }
  }

  async function adicionarCartao() {
    if (!novoCartaoNome.trim()) return;
    const lista = await api.adicionarCartao({
      nome: novoCartaoNome.trim(),
      pontos_por_dolar: novoCartaoPontos,
      cashback_pct: novoCartaoCashback,
    });
    setCartoes(lista);
    setNovoCartaoNome("");
    setNovoCartaoPontos(0);
    setNovoCartaoCashback(0);
  }

  async function removerCartao(cartaoId: number) {
    const lista = await api.removerCartao(cartaoId);
    setCartoes(lista);
  }

  if (carregando || !perfil) {
    return <p className="text-sm text-ink-500">Carregando perfil.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          Assistente de Compras da Reforma
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Perfil financeiro usado em todos os cálculos de custo efetivo.
        </p>
      </div>

      <Card
        title="Perfil financeiro"
        subtitle="Rendimento mensal líquido, cotação do dólar e valor padrão do milheiro."
      >
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="field-label">Rendimento mensal líquido (%)</label>
            <input
              type="number"
              step="0.01"
              className="field-input"
              value={perfil.rendimento_mensal}
              onChange={(e) => setPerfil({ ...perfil, rendimento_mensal: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="field-label">Cotação do dólar (R$)</label>
            <input
              type="number"
              step="0.01"
              className="field-input"
              value={perfil.cotacao_dolar}
              onChange={(e) => setPerfil({ ...perfil, cotacao_dolar: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="field-label">Valor padrão do milheiro (R$)</label>
            <input
              type="number"
              step="1"
              className="field-input"
              value={perfil.valor_milheiro_padrao}
              onChange={(e) =>
                setPerfil({ ...perfil, valor_milheiro_padrao: Number(e.target.value) })
              }
            />
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <button className="btn-primary" onClick={salvarPerfil} disabled={salvando}>
            {salvando ? "Salvando." : "Salvar perfil"}
          </button>
          {mensagem && <span className="text-sm text-brand-700">{mensagem}</span>}
        </div>
      </Card>

      <Card
        title="Cartões cadastrados"
        subtitle="Usados para sugerir pontos por dólar e cashback ao cadastrar uma oferta."
      >
        {cartoes.length === 0 ? (
          <p className="text-sm text-ink-500">Nenhum cartão cadastrado ainda.</p>
        ) : (
          <table className="mb-5 w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-ink-500">
                <th className="pb-2 font-medium">Cartão</th>
                <th className="pb-2 font-medium">Pontos por dólar</th>
                <th className="pb-2 font-medium">Cashback</th>
                <th className="pb-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {cartoes.map((cartao) => (
                <tr key={cartao.id} className="border-t border-ink-300/20">
                  <td className="py-2.5">{cartao.nome}</td>
                  <td className="py-2.5">{cartao.pontos_por_dolar.toFixed(1)}</td>
                  <td className="py-2.5">{cartao.cashback_pct.toFixed(1)}%</td>
                  <td className="py-2.5 text-right">
                    <button
                      className="btn-ghost-danger"
                      onClick={() => removerCartao(cartao.id)}
                    >
                      Remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="grid grid-cols-4 items-end gap-3 border-t border-ink-300/20 pt-4">
          <div className="col-span-2">
            <label className="field-label">Nome do cartão</label>
            <input
              className="field-input"
              value={novoCartaoNome}
              onChange={(e) => setNovoCartaoNome(e.target.value)}
              placeholder="XP Visa Infinite"
            />
          </div>
          <div>
            <label className="field-label">Pontos por dólar</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={novoCartaoPontos}
              onChange={(e) => setNovoCartaoPontos(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Cashback (%)</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={novoCartaoCashback}
              onChange={(e) => setNovoCartaoCashback(Number(e.target.value))}
            />
          </div>
          <div className="col-span-4">
            <button className="btn-secondary" onClick={adicionarCartao}>
              Adicionar cartão
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}