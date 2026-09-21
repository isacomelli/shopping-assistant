"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/Card";
import { HistoricoChart } from "@/components/HistoricoChart";
import { api } from "@/lib/api";
import { formatarData, formatarMoeda } from "@/lib/format";
import type { HistoricoItem, Produto } from "@/lib/types";

type ChaveOrdenacao = "data" | "loja" | "anunciado" | "efetivo";

function menorPrecoPorDia(historico: HistoricoItem[]) {
  const menores = new Map<string, number>();
  for (const linha of historico) {
    if (linha.preco_efetivo === null || !linha.registrado_em) continue;
    const dia = linha.registrado_em.split(" ")[0];
    const atual = menores.get(dia);
    if (atual === undefined || linha.preco_efetivo < atual) {
      menores.set(dia, linha.preco_efetivo);
    }
  }
  return Array.from(menores.entries())
    .sort(([diaA], [diaB]) => diaA.localeCompare(diaB))
    .map(([dia, preco]) => ({ data: formatarData(dia), preco }));
}

export default function PaginaHistorico() {
  const router = useRouter();
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [produtoId, setProdutoId] = useState<number | null>(null);
  const [historico, setHistorico] = useState<HistoricoItem[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [ordenacao, setOrdenacao] = useState<ChaveOrdenacao>("data");
  const [reversa, setReversa] = useState(true);

  useEffect(() => {
    api.listarProdutos().then((lista) => {
      setProdutos(lista);
      if (lista.length > 0) setProdutoId(lista[0].id);
      setCarregando(false);
    });
  }, []);

  useEffect(() => {
    if (produtoId !== null) {
      api.listarHistorico(produtoId).then(setHistorico);
    }
  }, [produtoId]);

  const precos = useMemo(
    () => historico.map((linha) => linha.preco_efetivo).filter((p): p is number => p !== null),
    [historico],
  );

  const precosRecentes = useMemo(() => {
    const limite = Date.now() - 30 * 24 * 60 * 60 * 1000;
    return historico
      .filter((linha) => linha.preco_efetivo !== null && linha.registrado_em)
      .filter((linha) => new Date(linha.registrado_em!.replace(" ", "T")).getTime() >= limite)
      .map((linha) => linha.preco_efetivo as number);
  }, [historico]);

  const menorPreco = precos.length > 0 ? Math.min(...precos) : null;
  const listaParaMedia = precosRecentes.length > 0 ? precosRecentes : precos;
  const mediaRecente =
    listaParaMedia.length > 0 ? listaParaMedia.reduce((a, b) => a + b, 0) / listaParaMedia.length : null;
  const menorRecente = listaParaMedia.length > 0 ? Math.min(...listaParaMedia) : null;

  const grafico = useMemo(() => menorPrecoPorDia(historico), [historico]);

  function alternarOrdenacao(chave: ChaveOrdenacao) {
    if (ordenacao === chave) {
      setReversa((atual) => !atual);
    } else {
      setOrdenacao(chave);
      setReversa(false);
    }
  }

  const historicoOrdenado = useMemo(() => {
    const funcoes: Record<ChaveOrdenacao, (linha: HistoricoItem) => number | string> = {
      data: (linha) => linha.registrado_em || "",
      loja: (linha) => (linha.loja || "").toLowerCase(),
      anunciado: (linha) => linha.preco_anunciado || 0,
      efetivo: (linha) => linha.preco_efetivo || 0,
    };
    const copia = [...historico].sort((a, b) => {
      const va = funcoes[ordenacao](a);
      const vb = funcoes[ordenacao](b);
      if (va < vb) return -1;
      if (va > vb) return 1;
      return 0;
    });
    return reversa ? copia.reverse() : copia;
  }, [historico, ordenacao, reversa]);

  async function excluir(registroId: number) {
    if (produtoId === null) return;
    await api.excluirHistorico(produtoId, registroId);
    setHistorico(await api.listarHistorico(produtoId));
  }

  async function editar(registroId: number) {
    if (produtoId === null) return;
    const oferta = await api.obterOfertaDoHistorico(produtoId, registroId);
    router.push(`/calculadora?produtoId=${produtoId}&ofertaId=${oferta.id}`);
  }

  if (carregando) {
    return <p className="text-sm text-ink-500">Carregando.</p>;
  }

  if (produtos.length === 0) {
    return (
      <Card title="Histórico de preços">
        <p className="text-sm text-ink-500">Nenhum produto cadastrado ainda.</p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Histórico de Preços</h1>
        <p className="mt-1 text-sm text-ink-500">
          Evolução do preço efetivo de cada produto ao longo das pesquisas.
        </p>
      </div>

      <Card>
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
      </Card>

      {historico.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-500">
            Ainda não há histórico registrado para este produto, cadastre ofertas na Calculadora.
          </p>
        </Card>
      ) : (
        <>
          <Card title="Menor preço efetivo por dia">
            <HistoricoChart pontos={grafico} />
          </Card>

          <div className="grid grid-cols-3 gap-4">
            <Card>
              <p className="field-label">Menor preço já encontrado</p>
              <p className="text-xl font-semibold text-ink-900">{formatarMoeda(menorPreco)}</p>
            </Card>
            <Card>
              <p className="field-label">Média dos últimos 30 dias</p>
              <p className="text-xl font-semibold text-ink-900">{formatarMoeda(mediaRecente)}</p>
            </Card>
            <Card>
              <p className="field-label">Menor preço dos últimos 30 dias</p>
              <p className="text-xl font-semibold text-ink-900">{formatarMoeda(menorRecente)}</p>
            </Card>
          </div>

          {menorRecente !== null && mediaRecente !== null && (
            <p className="text-sm">
              {menorRecente < mediaRecente ? (
                <span className="text-brand-700">
                  Vale comprar agora, está {((1 - menorRecente / mediaRecente) * 100).toFixed(1)}% abaixo da média dos últimos 30 dias.
                </span>
              ) : menorRecente > mediaRecente ? (
                <span className="text-alert-500">
                  Está {((menorRecente / mediaRecente - 1) * 100).toFixed(1)}% acima da média dos últimos 30 dias, talvez valha esperar.
                </span>
              ) : (
                <span className="text-ink-500">Preço atual está na média dos últimos 30 dias.</span>
              )}
            </p>
          )}

          <Card title="Todas as pesquisas registradas">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-ink-500">
                  <ColunaOrdenavel rotulo="Data" chave="data" ativa={ordenacao} reversa={reversa} aoClicar={alternarOrdenacao} />
                  <ColunaOrdenavel rotulo="Loja" chave="loja" ativa={ordenacao} reversa={reversa} aoClicar={alternarOrdenacao} />
                  <ColunaOrdenavel rotulo="Anunciado" chave="anunciado" ativa={ordenacao} reversa={reversa} aoClicar={alternarOrdenacao} />
                  <ColunaOrdenavel rotulo="Efetivo" chave="efetivo" ativa={ordenacao} reversa={reversa} aoClicar={alternarOrdenacao} />
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {historicoOrdenado.map((linha) => (
                  <tr key={linha.id} className="border-t border-ink-300/20">
                    <td className="py-2.5">{formatarData(linha.registrado_em)}</td>
                    <td className="py-2.5">{linha.loja}</td>
                    <td className="py-2.5">{formatarMoeda(linha.preco_anunciado)}</td>
                    <td className="py-2.5">{formatarMoeda(linha.preco_efetivo)}</td>
                    <td className="py-2.5 text-right">
                      <button className="btn-secondary mr-2 px-2.5 py-1 text-xs" onClick={() => editar(linha.id)}>
                        Editar
                      </button>
                      <button className="btn-ghost-danger" onClick={() => excluir(linha.id)}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}

function ColunaOrdenavel({
  rotulo,
  chave,
  ativa,
  reversa,
  aoClicar,
}: {
  rotulo: string;
  chave: ChaveOrdenacao;
  ativa: ChaveOrdenacao;
  reversa: boolean;
  aoClicar: (chave: ChaveOrdenacao) => void;
}) {
  const indicador = ativa === chave ? (reversa ? " ↓" : " ↑") : "";
  return (
    <th className="pb-2 font-medium">
      <button onClick={() => aoClicar(chave)} className="hover:text-ink-900">
        {rotulo}
        {indicador}
      </button>
    </th>
  );
}
