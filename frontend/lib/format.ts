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
