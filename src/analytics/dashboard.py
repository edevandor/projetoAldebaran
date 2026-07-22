"""Dashboard HTML local derivado exclusivamente do Parquet publicado."""

# ruff: noqa: E501 -- HTML/CSS/JavaScript embutido permanece legível como artefato único.

import json
from pathlib import Path

import pandas as pd


def build_dashboard(parquet_path: str | Path, output_path: str | Path) -> Path:
    """Gera uma visão executiva local, portátil e independente de ferramenta BI."""
    origem = Path(parquet_path)
    df = pd.read_parquet(origem)
    datas = pd.to_datetime(df["data_emissao"], errors="coerce")
    base = df.assign(mes=datas.dt.to_period("M").astype("string"))
    mensal = (
        base.dropna(subset=["mes"])
        .groupby(["sistema_origem", "mes"], as_index=False)["valor_total_venda_centavos"]
        .sum()
        .to_dict(orient="records")
    )
    produtos = (
        base.groupby(
            ["sistema_origem", "codigo_produto", "descricao_produto"],
            dropna=False,
            as_index=False,
        )["valor_total_venda_centavos"]
        .sum()
        .sort_values("valor_total_venda_centavos", ascending=False)
        .to_dict(orient="records")
    )
    resumo_sistemas = (
        base.groupby("sistema_origem", as_index=False)
        .agg(
            faturamento_centavos=("valor_total_venda_centavos", "sum"),
            vendas=("id_venda", "nunique"),
            itens=("id_venda", "size"),
        )
        .to_dict(orient="records")
    )
    resumo = [
        {
            "sistema_origem": "TODOS",
            "faturamento_centavos": int(base["valor_total_venda_centavos"].sum()),
            "vendas": int(base["id_venda"].nunique()),
            "itens": len(base),
        },
        *resumo_sistemas,
    ]
    payload = json.dumps(
        {"resumo": resumo, "mensal": mensal, "produtos": produtos},
        ensure_ascii=False,
        default=str,
    ).replace("</", "<\\/")
    run_id = str(df["id_execucao"].iloc[0]) if not df.empty else "sem execução"
    html = f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Aldebaran — visão executiva</title><style>
body{{font:16px system-ui;margin:0;background:#f5f7fa;color:#18212f}}main{{max-width:1100px;margin:auto;padding:32px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card,section{{background:white;padding:20px;border-radius:12px;margin:16px 0}}
.value{{font-size:2rem;font-weight:700}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #ddd}}
.bar{{height:14px;background:#315d86;border-radius:4px}}@media(max-width:700px){{.cards{{grid-template-columns:1fr}}}}
</style><main><h1>Visão executiva do histórico comercial</h1>
<label>Sistema <select id='sistema'><option value='TODOS'>Todos</option></select></label>
<div class='cards'><div class='card'><div>Faturamento</div><div class='value' id='fat'></div></div>
<div class='card'><div>Vendas</div><div class='value' id='vendas'></div></div>
<div class='card'><div>Itens</div><div class='value' id='itens'></div></div></div>
<section><h2>Evolução mensal</h2><table><tbody id='mensal'></tbody></table></section>
<section><h2>Produtos por faturamento</h2><table><tbody id='produtos'></tbody></table></section>
<p>Fonte: {origem.name} · execução {run_id}. Valores observados; sem metas ou causalidade inferida.</p>
<script>const d={payload};const s=document.querySelector('#sistema');
d.resumo.filter(x=>x.sistema_origem!=='TODOS').map(x=>x.sistema_origem).sort().forEach(x=>s.add(new Option(x,x)));
const brl=x=>(x/100).toLocaleString('pt-BR',{{style:'currency',currency:'BRL'}});
function draw(){{const f=s.value==='TODOS'?()=>true:x=>x.sistema_origem===s.value;const r=d.resumo.find(x=>x.sistema_origem===s.value);
fat.textContent=brl(r.faturamento_centavos);vendas.textContent=Number(r.vendas).toLocaleString('pt-BR');itens.textContent=Number(r.itens).toLocaleString('pt-BR');
const m=d.mensal.filter(f), mm=Math.max(1,...m.map(x=>Number(x.valor_total_venda_centavos)));mensal.innerHTML=m.map(x=>`<tr><td>${{x.mes}}</td><td>${{brl(x.valor_total_venda_centavos)}}</td><td><div class='bar' style='width:${{100*x.valor_total_venda_centavos/mm}}%'></div></td></tr>`).join('');
const p=d.produtos.filter(f).slice(0,10);produtos.innerHTML=p.map(x=>`<tr><td>${{x.codigo_produto||'—'}}</td><td>${{x.descricao_produto}}</td><td>${{brl(x.valor_total_venda_centavos)}}</td></tr>`).join('');}}
s.onchange=draw;draw();</script></main></html>"""
    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino.resolve()
