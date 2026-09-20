import type {
  Cartao,
  CalculoLivre,
  HistoricoItem,
  Oferta,
  OfertaPayload,
  ParceiroLivelo,
  ParcelaSimulada,
  Perfil,
  PesquisaAutomaticaResultado,
  Produto,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ErroApi extends Error {
  status: number;

  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
  }
}

async function requisitar<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const resposta = await fetch(`${BASE_URL}${caminho}`, {
    ...opcoes,
    headers: {
      "Content-Type": "application/json",
      ...opcoes.headers,
    },
    cache: "no-store",
  });

  if (!resposta.ok) {
    let detalhe = resposta.statusText;
    try {
      const corpo = await resposta.json();
      detalhe = corpo.detail || detalhe;
    } catch {
      // corpo sem json, mantem o statusText
    }
    throw new ErroApi(resposta.status, detalhe);
  }

  if (resposta.status === 204) {
    return undefined as T;
  }

  return resposta.json() as Promise<T>;
}

export const api = {
  // perfil
  obterPerfil: () => requisitar<Perfil>("/perfil"),
  salvarPerfil: (payload: Perfil) =>
    requisitar<Perfil>("/perfil", { method: "PUT", body: JSON.stringify(payload) }),
  obterCotacaoDolar: () =>
    requisitar<{ cotacao_dolar: number | null; encontrada: boolean }>("/perfil/cotacao-dolar"),

  // cartoes
  listarCartoes: () => requisitar<Cartao[]>("/perfil/cartoes"),
  adicionarCartao: (payload: { nome: string; pontos_por_dolar: number; cashback_pct: number }) =>
    requisitar<Cartao[]>("/perfil/cartoes", { method: "POST", body: JSON.stringify(payload) }),
  removerCartao: (cartaoId: number) =>
    requisitar<Cartao[]>(`/perfil/cartoes/${cartaoId}`, { method: "DELETE" }),

  // produtos, a wishlist
  listarProdutos: () => requisitar<Produto[]>("/produtos"),
  obterProduto: (produtoId: number) => requisitar<Produto>(`/produtos/${produtoId}`),
  criarProduto: (payload: { nome: string; categoria: string; orcamento: number; preco_alvo: number }) =>
    requisitar<Produto>("/produtos", { method: "POST", body: JSON.stringify(payload) }),
  atualizarProduto: (
    produtoId: number,
    payload: { nome: string; categoria: string; orcamento: number; preco_alvo: number },
  ) => requisitar<Produto>(`/produtos/${produtoId}`, { method: "PUT", body: JSON.stringify(payload) }),
  atualizarStatusProduto: (produtoId: number, status: string) =>
    requisitar<Produto>(`/produtos/${produtoId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),
  excluirProduto: (produtoId: number) =>
    requisitar<void>(`/produtos/${produtoId}`, { method: "DELETE" }),

  // ofertas
  listarOfertas: (produtoId: number) => requisitar<Oferta[]>(`/produtos/${produtoId}/ofertas`),
  criarOferta: (produtoId: number, payload: OfertaPayload) =>
    requisitar<Oferta>(`/produtos/${produtoId}/ofertas`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  atualizarOferta: (produtoId: number, ofertaId: number, payload: OfertaPayload) =>
    requisitar<Oferta>(`/produtos/${produtoId}/ofertas/${ofertaId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  excluirOferta: (produtoId: number, ofertaId: number) =>
    requisitar<void>(`/produtos/${produtoId}/ofertas/${ofertaId}`, { method: "DELETE" }),
  // atualizarCache, quando true, ignora o cache local de pesquisas e forca uma nova consulta ao google shopping e ao buscape, ver database/db.py, obter_cache_pesquisa e salvar_cache_pesquisa
  pesquisarAutomaticamente: (produtoId: number, atualizarCache = false) =>
    requisitar<PesquisaAutomaticaResultado>(
      `/produtos/${produtoId}/pesquisar?atualizar=${atualizarCache}`,
      { method: "POST" },
    ),

  // parceiros livelo ou esfera
  listarParceirosLivelo: () => requisitar<ParceiroLivelo[]>("/parceiros-livelo"),
  atualizarParceirosLivelo: () =>
    requisitar<ParceiroLivelo[]>("/parceiros-livelo/atualizar", { method: "POST" }),
  simularParcelamento: (payload: {
    preco_pix: number;
    preco_cartao: number;
    rendimento_mensal: number;
    max_parcelas?: number;
  }) =>
    requisitar<ParcelaSimulada[]>("/simular-parcelamento", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // historico
  listarHistorico: (produtoId: number) =>
    requisitar<HistoricoItem[]>(`/produtos/${produtoId}/historico`),
  excluirHistorico: (produtoId: number, registroId: number) =>
    requisitar<void>(`/produtos/${produtoId}/historico/${registroId}`, { method: "DELETE" }),
  obterOfertaDoHistorico: (produtoId: number, registroId: number) =>
    requisitar<Oferta>(`/produtos/${produtoId}/historico/${registroId}/oferta`),

  // calculadora livre, sem produto e sem gravar nada no banco
  calcularLivre: (payload: OfertaPayload) =>
    requisitar<CalculoLivre>("/calculadora/calcular", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export { ErroApi };
