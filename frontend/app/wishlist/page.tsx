"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Card } from "@/components/Card";
import { api } from "@/lib/api";
import { formatarMoeda } from "@/lib/format";
import type { Produto } from "@/lib/types";

const ROTULOS_STATUS: Record<Produto["status"], string> = {
  comprar: "Comprar",
  esperar: "Esperar promoção",
  comprado: "Comprado",
};

export default function PaginaWishlist() {
  const router = useRouter();
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [editandoId, setEditandoId] = useState<number | null>(null);

  const [nome, setNome] = useState("");
  const [categoria, setCategoria] = useState("");
  const [precoAlvo, setPrecoAlvo] = useState(0);
  const [orcamento, setOrcamento] = useState(0);

  async function carregar() {
    const lista = await api.listarProdutos();
    setProdutos(lista);
    setCarregando(false);
  }

  useEffect(() => {
    carregar();
  }, []);

  async function criarProduto() {
    if (!nome.trim()) return;
    const produto = await api.criarProduto({
      nome: nome.trim(),
      categoria: categoria.trim(),
      orcamento,
      preco_alvo: precoAlvo,
    });
    setNome("");
    setCategoria("");
    setPrecoAlvo(0);
    setOrcamento(0);
    router.push("/calculadora");
    void produto;
  }

  async function mudarStatus(produtoId: number, status: string) {
    await api.atualizarStatusProduto(produtoId, status);
    carregar();
  }

  async function excluir(produtoId: number) {
    await api.excluirProduto(produtoId);
    carregar();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Wishlist</h1>
        <p className="mt-1 text-sm text-ink-500">
          Itens que faltam comprar para o apartamento, com orçamento e preço alvo.
        </p>
      </div>

      <Card title="Adicionar produto">
        <div className="grid grid-cols-4 items-end gap-4">
          <div>
            <label className="field-label">Nome do produto</label>
            <input className="field-input" value={nome} onChange={(e) => setNome(e.target.value)} />
          </div>
          <div>
            <label className="field-label">Categoria</label>
            <input
              className="field-input"
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Preço alvo (R$)</label>
            <input
              type="number"
              step="50"
              className="field-input"
              value={precoAlvo}
              onChange={(e) => setPrecoAlvo(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Orçamento máximo (R$)</label>
            <input
              type="number"
              step="50"
              className="field-input"
              value={orcamento}
              onChange={(e) => setOrcamento(Number(e.target.value))}
            />
          </div>
        </div>
        <button className="btn-primary mt-4" onClick={criarProduto}>
          Criar produto
        </button>
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-500">
          Itens da lista
        </h2>
        {carregando ? (
          <p className="text-sm text-ink-500">Carregando.</p>
        ) : produtos.length === 0 ? (
          <p className="text-sm text-ink-500">Nenhum produto cadastrado ainda.</p>
        ) : (
          produtos.map((produto) => (
            <div key={produto.id} className="rounded-xl2 border border-ink-300/30 bg-surface p-5 shadow-card">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-base font-semibold text-ink-900">{produto.nome}</p>
                  <p className="text-sm text-ink-500">{produto.categoria || "Sem categoria"}</p>
                </div>
                <select
                  className="field-input w-44"
                  value={produto.status}
                  onChange={(e) => mudarStatus(produto.id, e.target.value)}
                >
                  {Object.entries(ROTULOS_STATUS).map(([valor, rotulo]) => (
                    <option key={valor} value={valor}>
                      {rotulo}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-700">
                <span>Orçamento: {formatarMoeda(produto.orcamento)}</span>
                <span>Preço alvo: {formatarMoeda(produto.preco_alvo)}</span>
                {produto.melhor_preco_efetivo !== null ? (
                  <span className="font-medium text-brand-700">
                    Melhor preço: {formatarMoeda(produto.melhor_preco_efetivo)} ({produto.melhor_loja})
                  </span>
                ) : (
                  <span className="text-ink-500">Sem ofertas cadastradas</span>
                )}
              </div>

              <div className="mt-4 flex gap-2 border-t border-ink-300/20 pt-3">
                <button
                  className="btn-secondary"
                  onClick={() => router.push("/calculadora")}
                >
                  Ver na calculadora
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => setEditandoId(editandoId === produto.id ? null : produto.id)}
                >
                  {editandoId === produto.id ? "Fechar edição" : "Editar produto"}
                </button>
                <button className="btn-ghost-danger" onClick={() => excluir(produto.id)}>
                  Excluir produto
                </button>
              </div>

              {editandoId === produto.id && (
                <FormEdicaoProduto
                  produto={produto}
                  aoSalvar={async (payload) => {
                    await api.atualizarProduto(produto.id, payload);
                    setEditandoId(null);
                    carregar();
                  }}
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function FormEdicaoProduto({
  produto,
  aoSalvar,
}: {
  produto: Produto;
  aoSalvar: (payload: {
    nome: string;
    categoria: string;
    orcamento: number;
    preco_alvo: number;
  }) => Promise<void>;
}) {
  const [nome, setNome] = useState(produto.nome);
  const [categoria, setCategoria] = useState(produto.categoria || "");
  const [precoAlvo, setPrecoAlvo] = useState(produto.preco_alvo || 0);
  const [orcamento, setOrcamento] = useState(produto.orcamento || 0);

  return (
    <div className="mt-4 grid grid-cols-4 items-end gap-4 border-t border-ink-300/20 pt-4">
      <div>
        <label className="field-label">Nome</label>
        <input className="field-input" value={nome} onChange={(e) => setNome(e.target.value)} />
      </div>
      <div>
        <label className="field-label">Categoria</label>
        <input
          className="field-input"
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
        />
      </div>
      <div>
        <label className="field-label">Preço alvo (R$)</label>
        <input
          type="number"
          step="50"
          className="field-input"
          value={precoAlvo}
          onChange={(e) => setPrecoAlvo(Number(e.target.value))}
        />
      </div>
      <div>
        <label className="field-label">Orçamento (R$)</label>
        <input
          type="number"
          step="50"
          className="field-input"
          value={orcamento}
          onChange={(e) => setOrcamento(Number(e.target.value))}
        />
      </div>
      <div className="col-span-4">
        <button
          className="btn-primary"
          onClick={() => aoSalvar({ nome, categoria, orcamento, preco_alvo: precoAlvo })}
        >
          Salvar alterações
        </button>
      </div>
    </div>
  );
}