import { formatarMoeda } from "@/lib/format";
import type { ResultadoCalculo } from "@/lib/types";

/**
 * grade com o detalhamento de pix e cartao de um resultado de calculo, extraida de RankingCard para tambem servir a calculadora livre, ver frontend/app/calculadora-livre/page.tsx. as duas telas mostram exatamente o mesmo formato, so muda de onde vem o preco_pix, o preco_cartao, o numero de parcelas e o resultado calculado.
 */
export function ResultadoDetalhado({
  precoPix,
  precoCartao,
  parcelas,
  resultado,
}: {
  precoPix: number;
  precoCartao: number;
  parcelas: number;
  resultado: ResultadoCalculo;
}) {
  return (
    <div className="grid grid-cols-2 gap-4 text-sm">
      <div className="rounded-lg bg-canvas p-4">
        <p className="mb-2 font-medium text-ink-900">Pix</p>
        <Linha rotulo="Preço" valor={formatarMoeda(precoPix)} />
        <Linha rotulo="Valor dos pontos" valor={formatarMoeda(resultado.valor_pontos_pix)} />
        <Linha rotulo="Cashback" valor={formatarMoeda(resultado.cashback_valor_pix)} />
        <Linha rotulo="Preço efetivo" valor={formatarMoeda(resultado.preco_efetivo_pix)} destaque />
      </div>
      <div className="rounded-lg bg-canvas p-4">
        <p className="mb-2 font-medium text-ink-900">Cartão {parcelas}x</p>
        <Linha rotulo="Preço" valor={formatarMoeda(precoCartao)} />
        <Linha rotulo="Rendimento do parcelamento" valor={formatarMoeda(resultado.rendimento_parcelamento)} />
        <Linha rotulo="Valor dos pontos" valor={formatarMoeda(resultado.valor_pontos_cartao)} />
        <Linha rotulo="Cashback" valor={formatarMoeda(resultado.cashback_valor_cartao)} />
        <Linha rotulo="Preço efetivo" valor={formatarMoeda(resultado.preco_efetivo_cartao)} destaque />
      </div>
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
