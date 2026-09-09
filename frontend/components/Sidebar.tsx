"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITENS_NAV = [
  { href: "/", rotulo: "Perfil", descricao: "CDI, dólar e cartões" },
  { href: "/calculadora", rotulo: "Calculadora", descricao: "Pesquisa e ranking" },
  { href: "/wishlist", rotulo: "Wishlist", descricao: "Itens da reforma" },
  { href: "/historico", rotulo: "Histórico", descricao: "Evolução de preços" },
];

export function Sidebar() {
  const caminhoAtual = usePathname();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-ink-300/30 bg-surface px-5 py-6">
      <div className="mb-8 px-1">
        <p className="text-sm font-semibold tracking-tight text-ink-900">
          Assistente de Compras
        </p>
        <p className="text-xs text-ink-500">Reforma do apartamento</p>
      </div>

      <nav className="flex flex-col gap-1">
        {ITENS_NAV.map((item) => {
          const ativo =
            item.href === "/" ? caminhoAtual === "/" : caminhoAtual.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-lg px-3 py-2.5 text-sm transition ${
                ativo
                  ? "bg-brand-50 font-medium text-brand-700"
                  : "text-ink-700 hover:bg-ink-900/[0.03]"
              }`}
            >
              <span className="block">{item.rotulo}</span>
              <span className="block text-xs text-ink-500">{item.descricao}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto px-1 text-xs text-ink-300">
        Uso pessoal, dados salvos localmente.
      </div>
    </aside>
  );
}
