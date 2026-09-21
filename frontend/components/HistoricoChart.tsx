"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";
import { formatarMoeda } from "@/lib/format";

export function HistoricoChart({ pontos }: { pontos: { data: string; preco: number }[] }) {
  if (pontos.length === 0) {
    return null;
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={pontos} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e1" vertical={false} />
          <XAxis dataKey="data" tick={{ fontSize: 12, fill: "#6b6b63" }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fontSize: 12, fill: "#6b6b63" }}
            axisLine={false}
            tickLine={false}
            width={72}
            tickFormatter={(valor) => formatarMoeda(valor)}
          />
          <Tooltip
            formatter={(valor: number) => formatarMoeda(valor)}
            contentStyle={{ borderRadius: 10, borderColor: "#e5e5e1", fontSize: 13 }}
          />
          <Line
            type="monotone"
            dataKey="preco"
            stroke="#256641"
            strokeWidth={2}
            dot={{ r: 3, fill: "#256641" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
