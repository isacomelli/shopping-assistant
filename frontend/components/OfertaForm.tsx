"use client";

import { useState } from "react";

import type { Cartao, OfertaPayload } from "@/lib/types";

const TIPOS_OFERTA = ["online", "parceiro de pontos", "loja física", "negociação"];
const NIVEIS_CONFIANCA = ["confirmada", "até domingo", "expirada"];

const VAZIO: OfertaPayload = {
  loja: "",
  tipo: "online",
  preco_pix: 0,
  preco_cartao: 0,
  parcelas: 6,
  pontos_por_real: 0,
  pontos_por_dolar_cartao: 0,
  percentual_bonus_transferencia: 80,
  valor_milheiro: 15,
  cashback_pct: 0,
  frete: 0,
  cupom: 0,
  observacoes: "",
  validade: "",
  confianca: "confirmada",
};

export function OfertaForm({
  valorInicial,
  cartoes,
  aoSalvar,
  aoCancelar,
  rotuloBotao = "Calcular e salvar oferta",
}: {
  valorInicial?: Partial<OfertaPayload>;
  cartoes: Cartao[];
  aoSalvar: (payload: OfertaPayload) => Promise<void>;
  aoCancelar?: () => void;
  rotuloBotao?: string;
}) {
  const [dados, setDados] = useState<OfertaPayload>({ ...VAZIO, ...valorInicial });
  const [cartaoSelecionado, setCartaoSelecionado] = useState("nenhum");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function atualizar<K extends keyof OfertaPayload>(campo: K, valor: OfertaPayload[K]) {
    setDados((atual) => ({ ...atual, [campo]: valor }));
  }

  function selecionarCartao(nome: string) {
    setCartaoSelecionado(nome);
    if (nome === "nenhum") return;
    const cartao = cartoes.find((item) => item.nome === nome);
    if (cartao) {
      atualizar("pontos_por_dolar_cartao", cartao.pontos_por_dolar);
      atualizar("cashback_pct", cartao.cashback_pct);
    }
  }

  async function enviar() {
    if (!dados.loja.trim() || dados.preco_pix <= 0 || dados.preco_cartao <= 0) {
      setErro("Preencha ao menos a loja, o preço no Pix e o preço no cartão.");
      return;
    }
    setErro(null);
    setSalvando(true);
    try {
      await aoSalvar({ ...dados, loja: dados.loja.trim() });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="field-label">Loja</label>
          <input
            className="field-input"
            value={dados.loja}
            onChange={(e) => atualizar("loja", e.target.value)}
          />
        </div>
        <div>
          <label className="field-label">Tipo de oferta</label>
          <select
            className="field-input"
            value={dados.tipo}
            onChange={(e) => atualizar("tipo", e.target.value)}
          >
            {TIPOS_OFERTA.map((tipo) => (
              <option key={tipo} value={tipo}>
                {tipo}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label">Número de parcelas</label>
          <input
            type="number"
            min={1}
            max={24}
            className="field-input"
            value={dados.parcelas}
            onChange={(e) => atualizar("parcelas", Number(e.target.value))}
          />
        </div>

        <div>
          <label className="field-label">Preço no Pix (R$)</label>
          <input
            type="number"
            step="10"
            className="field-input"
            value={dados.preco_pix}
            onChange={(e) => atualizar("preco_pix", Number(e.target.value))}
          />
        </div>
        <div>
          <label className="field-label">Preço no cartão (R$)</label>
          <input
            type="number"
            step="10"
            className="field-input"
            value={dados.preco_cartao}
            onChange={(e) => atualizar("preco_cartao", Number(e.target.value))}
          />
        </div>
        <div>
          <label className="field-label">Frete (R$)</label>
          <input
            type="number"
            step="10"
            className="field-input"
            value={dados.frete}
            onChange={(e) => atualizar("frete", Number(e.target.value))}
          />
        </div>
      </div>

      <div className="border-t border-ink-300/20 pt-4">
        <p className="mb-3 text-xs uppercase tracking-wide text-ink-500">Pontos e milhas</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="field-label">Pontos Livelo ou Esfera por real</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={dados.pontos_por_real}
              onChange={(e) => atualizar("pontos_por_real", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Cartão usado na compra</label>
            <select
              className="field-input"
              value={cartaoSelecionado}
              onChange={(e) => selecionarCartao(e.target.value)}
            >
              <option value="nenhum">nenhum</option>
              {cartoes.map((cartao) => (
                <option key={cartao.id} value={cartao.nome}>
                  {cartao.nome}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field-label">Bônus de transferência (%)</label>
            <input
              type="number"
              step="5"
              className="field-input"
              value={dados.percentual_bonus_transferencia}
              onChange={(e) => atualizar("percentual_bonus_transferencia", Number(e.target.value))}
            />
          </div>

          <div>
            <label className="field-label">Pontos por dólar no cartão</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={dados.pontos_por_dolar_cartao}
              onChange={(e) => atualizar("pontos_por_dolar_cartao", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Cashback (%)</label>
            <input
              type="number"
              step="0.5"
              className="field-input"
              value={dados.cashback_pct}
              onChange={(e) => atualizar("cashback_pct", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Valor do milheiro (R$)</label>
            <input
              type="number"
              step="1"
              className="field-input"
              value={dados.valor_milheiro}
              onChange={(e) => atualizar("valor_milheiro", Number(e.target.value))}
            />
          </div>
        </div>
      </div>

      <div className="border-t border-ink-300/20 pt-4">
        <p className="mb-3 text-xs uppercase tracking-wide text-ink-500">Detalhes extras</p>
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            <label className="field-label">Observações</label>
            <textarea
              className="field-input"
              rows={2}
              value={dados.observacoes}
              onChange={(e) => atualizar("observacoes", e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Cupom de desconto (R$)</label>
            <input
              type="number"
              step="10"
              className="field-input"
              value={dados.cupom}
              onChange={(e) => atualizar("cupom", Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label">Validade da oferta</label>
            <input
              className="field-input"
              value={dados.validade}
              onChange={(e) => atualizar("validade", e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">Confiança</label>
            <select
              className="field-input"
              value={dados.confianca}
              onChange={(e) => atualizar("confianca", e.target.value)}
            >
              {NIVEIS_CONFIANCA.map((nivel) => (
                <option key={nivel} value={nivel}>
                  {nivel}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {erro && <p className="text-sm text-red-600">{erro}</p>}

      <div className="flex items-center justify-end gap-3 border-t border-ink-300/20 pt-4">
        {aoCancelar && (
          <button type="button" className="btn-secondary" onClick={aoCancelar}>
            Cancelar
          </button>
        )}
        <button type="button" className="btn-primary" onClick={enviar} disabled={salvando}>
          {salvando ? "Salvando..." : rotuloBotao}
        </button>
      </div>
    </div>
  );
}
