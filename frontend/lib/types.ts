export interface Perfil {
  rendimento_mensal: number;
  cotacao_dolar: number;
  valor_milheiro_padrao: number;
}

export interface Cartao {
  id: number;
  nome: string;
  pontos_por_dolar: number;
  cashback_pct: number;
}

export interface Produto {
  id: number;
  nome: string;
  categoria: string | null;
  orcamento: number | null;
  preco_alvo: number | null;
  status: "comprar" | "esperar" | "comprado";
  criado_em: string | null;
  melhor_preco_efetivo: number | null;
  melhor_loja: string | null;
}

export interface ResultadoCalculo {
  valor_pontos_pix: number;
  cashback_valor_pix: number;
  preco_efetivo_pix: number;
  rendimento_parcelamento: number;
  valor_pontos_cartao: number;
  cashback_valor_cartao: number;
  preco_efetivo_cartao: number;
  melhor_forma_pagamento: string;
  preco_efetivo: number;
  economia_vs_anunciado: number;
}

export interface Oferta {
  id: number;
  produto_id: number;
  loja: string;
  tipo: string;
  preco_pix: number;
  preco_cartao: number;
  parcelas: number;
  pontos_por_real: number;
  pontos_por_dolar_cartao: number;
  percentual_bonus_transferencia: number;
  valor_milheiro: number;
  cashback_pct: number;
  frete: number;
  cupom: number;
  observacoes: string | null;
  validade: string | null;
  confianca: string;
  preco_efetivo: number | null;
  url_produto: string | null;
  atualizada_em: string | null;
  criado_em: string | null;
  resultado: ResultadoCalculo;
}

export interface OfertaPayload {
  loja: string;
  tipo: string;
  preco_pix: number;
  preco_cartao: number;
  parcelas: number;
  pontos_por_real: number;
  pontos_por_dolar_cartao: number;
  percentual_bonus_transferencia: number;
  valor_milheiro: number;
  cashback_pct: number;
  frete: number;
  cupom: number;
  observacoes: string;
  validade: string;
  confianca: string;
}

export interface ResultadoAutomatico {
  loja: string;
  tipo: string;
  preco_pix: number;
  preco_cartao: number;
  parcelas: number;
  pontos_por_real: number;
  parceiro_encontrado: boolean;
  parceiro_nome: string | null;
  confianca_pix_cartao: boolean;
  url_produto: string;
  resultado: ResultadoCalculo;
}

export interface HistoricoItem {
  id: number;
  produto_id: number;
  loja: string;
  preco_anunciado: number | null;
  preco_efetivo: number | null;
  registrado_em: string | null;
}

export interface ParcelaSimulada {
  parcelas: number;
  custo_efetivo: number;
}

export interface ParceiroLivelo {
  nome: string;
  alias: string;
  pontos_padrao: number;
}