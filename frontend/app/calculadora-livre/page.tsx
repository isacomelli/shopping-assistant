"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { OfertaForm } from "@/components/OfertaForm";
import { ResultadoDetalhado } from "@/components/ResultadoDetalhado";
import { api } from "@/lib/api";
import type { Cartao, OfertaPayload, Perfil, ResultadoCalculo } from "@/lib/types";

export default function PaginaCalculadoraLivre() {
  const [cartoes, setCartoes] = useState<Cartao[]>([]);
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [ultimoPayload, setUltimoPayload] = useState<OfertaPayload | null>(null);
  const [resultado, setResultado] = useState<ResultadoCalculo | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listarCartoes(), api.obterPerfil()]).then(([listaCartoes, perfilAtual]) => {
      setCartoes(listaCartoes);
      setPerfil(perfilAtual);
      setCarregando(false);
    });
  }, []);

  async function calcular(payload: OfertaPayload) {
    setErro(null);
    try {
      const calculo = await api.calcularLivre(payload);
      setUltimoPayload(payload);
      setResultado(calculo.resultado);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível calcular agora.");
    }
  }

  if (carregando) {
    return <p className="text-sm text-ink-500">Carregando.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Calculadora livre</h1>
        <p className="mt-1 text-sm text-ink-500">
          Simule o custo efetivo de qualquer compra do dia a dia, sem precisar cadastrar um produto na
          wishlist e sem gravar nada no histórico.
        </p>
      </div>

      <Card title="Dados da compra">
        <OfertaForm
          cartoes={cartoes}
          perfil={perfil ?? undefined}
          exigirLoja={false}
          rotuloBotao="Calcular custo efetivo"
          aoSalvar={calcular}
        />
        {erro && <p className="mt-3 text-sm text-red-600">{erro}</p>}
      </Card>

      {resultado && ultimoPayload && (
        <Card title="Resultado" subtitle="Custo efetivo considerando pontos, cashback e rendimento do parcelamento.">
          <ResultadoDetalhado
            precoPix={ultimoPayload.preco_pix}
            precoCartao={ultimoPayload.preco_cartao}
            parcelas={ultimoPayload.parcelas}
            resultado={resultado}
          />
          <p className="mt-4 text-sm">
            Melhor forma de pagamento,{" "}
            <span className="font-semibold text-brand-700">{resultado.melhor_forma_pagamento}</span>
          </p>
        </Card>
      )}
    </div>
  );
}
