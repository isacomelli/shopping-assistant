export function formatarMoeda(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) {
    return "R$ 0,00";
  }
  return valor.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export function formatarData(texto: string | null | undefined): string {
  if (!texto) return "não informada";
  const [dataParte] = texto.split(" ");
  const [ano, mes, dia] = dataParte.split("-");
  if (!ano || !mes || !dia) return texto;
  return `${dia}/${mes}/${ano}`;
}

export function obterDominioDaOferta(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const { hostname } = new URL(url);
    return hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function obterLogoDaLoja(url: string | null | undefined): string | null {
  const dominio = obterDominioDaOferta(url);
  // links internos do Google Shopping não identificam a loja, então o favicon do Google seria enganoso
  if (!dominio || dominio.endsWith("google.com")) return null;
  return `https://www.google.com/s2/favicons?domain=${dominio}&sz=64`;
}

const ROTULOS_CONFIANCA_NOME: Record<string, string> = {
  informacao_extra: "Nome traz item a mais (kit, acessório)",
  parcial: "Nome bate parcialmente com a pesquisa",
  baixa: "Nome pouco parecido com a pesquisa",
};

export function rotuloConfiancaNome(confiancaNome: string | null | undefined): string | null {
  if (!confiancaNome || confiancaNome === "exato") return null;
  return ROTULOS_CONFIANCA_NOME[confiancaNome] ?? null;
}
