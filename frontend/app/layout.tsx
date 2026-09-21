import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Assistente de Compras da Reforma",
  description: "Custo efetivo de compra, considerando Pix, cartão, pontos e cashback.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="flex">
        <Sidebar />
        <main className="min-h-screen flex-1 px-10 py-8">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
      </body>
    </html>
  );
}
