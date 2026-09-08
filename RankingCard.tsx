"use client";

import { useState } from "react";

import { OfertaForm } from "@/components/OfertaForm";
import { formatarData, formatarMoeda } from "@/lib/format";
import type { Cartao, Oferta, OfertaPayload } from "@/lib/types";

const MEDALHAS = ["1º lugar", "2º lugar", "3º lugar"];

export function RankingCard({
  oferta,
  posicao,
  cartoes,
  aoSalvarEdicao,
  aoExcluir,
}: {
  oferta: Oferta;
  posicao: number;
  cartoes: Cartao[];
  aoSalvarEdicao: (payload: OfertaPayload) => Promise<void>;
  aoExcluir: () => Promise<void>;
}) {
  const [aberto, setAberto] = useState(false);
  const [editando, setEditando] = useState(false);

  const rotulo = MEDALHAS[posicao] ?? `${posicao + 1}º lugar`;

  return (
    <div className="rounded-xl2 border border-ink-300/30 bg-surface shadow-card">
      <button
        className="flex w-full items-center justify-between px-5 py-4 text-left"
        onClick={() => setAberto((atual) => !atual)}
      >
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand-600">{rotulo}</p>
          <p className="text-base font-semibold text-ink-900">{oferta.loja}</p>
          <p className="text-sm text-ink-500">
            Melhor forma de pagamento, {oferta.resultado.melhor_forma_pagamento}
          </p>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold text-brand-700">
            {formatarMoeda(oferta.resultado.preco_efetivo)}
          </p>
          <p className="text-xs text-ink-500">
            economia de {formatarMoeda(oferta.resultado.economia_vs_anunciado)}
          </p>
        </div>
      </button>

      {aberto && (
        <div className="border-t border-ink-300/20 px-5 py-4">
          <p className="mb-3 text-xs text-ink-500">
            Oferta atualizada em {formatarData(oferta.atualizada_em || oferta.criado_em)}
          </p>

          <div className="mb-4 flex gap-2">
            <button className="btn-secondary" onClick={() => setEditando((atual) => !atual)}>
              {editando ? "Fechar edição" : "Editar oferta"}
            </button>
            <button className="btn-ghost-danger" onClick={aoExcluir}>
              Excluir oferta
            </button>
          </div>

          {editando ? (
            <OfertaForm
              cartoes={cartoes}
              rotuloBotao="Salvar edição"
              valorInicial={{
                loja: oferta.loja,
                tipo: oferta.tipo,
                preco_pix: oferta.preco_pix,
                preco_cartao: oferta.preco_cartao,
                parcelas: oferta.parcelas,
                pontos_por_real: oferta.pontos_por_real,
                pontos_por_dolar_cartao: oferta.pontos_por_dolar_cartao,
                percentual_bonus_transferencia: oferta.percentual_bonus_transferencia,
                valor_milheiro: oferta.valor_milheiro,
                cashback_pct: oferta.cashback_pct,
                frete: oferta.frete,
                cupom: oferta.cupom,
                observacoes: oferta.observacoes || "",
                validade: oferta.validade || "",
                confianca: oferta.confianca,
              }}
              aoSalvar={async (payload) => {
                await aoSalvarEdicao(payload);
                setEditando(false);
              }}
              aoCancelar={() => setEditando(false)}
            />
          ) : (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="rounded-lg bg-canvas p-4">
                <p className="mb-2 font-medium text-ink-900">Pix</p>
                <Linha rotulo="Preço" valor={formatarMoeda(oferta.preco_pix)} />
                <Linha rotulo="Valor dos pontos" valor={formatarMoeda(oferta.resultado.valor_pontos_pix)} />
                <Linha rotulo="Cashback" valor={formatarMoeda(oferta.resultado.cashback_valor_pix)} />
                <Linha
                  rotulo="Preço efetivo"
                  valor={formatarMoeda(oferta.resultado.preco_efetivo_pix)}
                  destaque
                />
              </div>
              <div className="rounded-lg bg-canvas p-4">
                <p className="mb-2 font-medium text-ink-900">Cartão {oferta.parcelas}x</p>
                <Linha rotulo="Preço" valor={formatarMoeda(oferta.preco_cartao)} />
                <Linha
                  rotulo="Rendimento do parcelamento"
                  valor={formatarMoeda(oferta.resultado.rendimento_parcelamento)}
                />
                <Linha rotulo="Valor dos pontos" valor={formatarMoeda(oferta.resultado.valor_pontos_cartao)} />
                <Linha rotulo="Cashback" valor={formatarMoeda(oferta.resultado.cashback_valor_cartao)} />
                <Linha
                  rotulo="Preço efetivo"
                  valor={formatarMoeda(oferta.resultado.preco_efetivo_cartao)}
                  destaque
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Linha({ rotulo, valor, destaque }: { rotulo: string; valor: string; destaque?: boolean }) {
  return (
    <div className="flex justify-between py-0.5">
      <span className="text-ink-500">{rotulo}</span>
      <span className={destaque ? "font-semibold text-ink-900" : "text-ink-700"}>{valor}</span>
    </div>
  );
}
