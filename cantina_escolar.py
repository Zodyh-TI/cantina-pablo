from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, date
import json
import uuid

APP_VERSION = "1.0.0"
HOST = "127.0.0.1"
PORT = 8000
DATA_FILE = Path(__file__).with_name("cantina_data.json")

DEFAULT_DATA = {
    "customers": [
        {"id": "aluno-1", "name": "Mateus", "role": "Aluno", "wallet": 50.0, "dailyLimit": 15.0},
        {"id": "prof-1", "name": "Professora Ana", "role": "Professor", "wallet": 35.0, "dailyLimit": 40.0},
    ],
    "products": [
        {"id": "coxinha", "name": "Coxinha da Casa", "category": "Salgados", "description": "Frango cremoso, massa crocante e retirada rapida no intervalo.", "price": 6.5, "stock": 12, "lowThreshold": 5, "tags": ["Contem gluten", "Contem lactose"]},
        {"id": "pastel", "name": "Pastel de Queijo", "category": "Salgados", "description": "Queijo derretido e massa sequinha.", "price": 7.0, "stock": 8, "lowThreshold": 5, "tags": ["Vegetariano", "Contem gluten", "Contem lactose"]},
        {"id": "wrap", "name": "Wrap Natural", "category": "Salgados", "description": "Lanche leve com salada, cenoura e molho da cantina.", "price": 9.9, "stock": 6, "lowThreshold": 4, "tags": ["Opcao vegana", "Sem lactose"]},
        {"id": "brownie", "name": "Brownie", "category": "Doces", "description": "Chocolate intenso com casquinha fina.", "price": 5.5, "stock": 18, "lowThreshold": 6, "tags": ["Contem gluten", "Contem lactose"]},
        {"id": "fruta", "name": "Copo de Frutas", "category": "Doces", "description": "Frutas frescas picadas, sem acucar adicionado.", "price": 6.0, "stock": 10, "lowThreshold": 5, "tags": ["Sem lactose", "Opcao vegana", "Sem gluten"]},
        {"id": "suco", "name": "Suco Natural", "category": "Bebidas", "description": "Sabores do dia: laranja, uva e maracuja.", "price": 4.5, "stock": 22, "lowThreshold": 8, "tags": ["Sem lactose", "Opcao vegana", "Sem gluten"]},
        {"id": "agua", "name": "Agua Mineral", "category": "Bebidas", "description": "Garrafa gelada para retirar direto no balcao.", "price": 3.0, "stock": 30, "lowThreshold": 10, "tags": ["Sem lactose", "Opcao vegana", "Sem gluten"]},
    ],
    "orders": [],
    "scheduled": []
}


def now():
    return datetime.now().replace(microsecond=0).isoformat()


def today():
    return date.today().isoformat()


def money(value):
    return round(float(value), 2)


def load_data():
    if DATA_FILE.exists():
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        for key, value in DEFAULT_DATA.items():
            data.setdefault(key, value)
        return data
    save_data(DEFAULT_DATA)
    return json.loads(json.dumps(DEFAULT_DATA))


def save_data(data):
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def find(items, item_id):
    return next((item for item in items if item.get("id") == item_id), None)


def spent_today(data, customer_id):
    total = 0
    for order in data["orders"]:
        if order["customerId"] == customer_id and order["createdAt"].startswith(today()) and order["status"] != "Cancelado":
            total += float(order["total"])
    return money(total)


def report(data):
    orders = [order for order in data["orders"] if order["createdAt"].startswith(today()) and order["status"] != "Cancelado"]
    payments = {"wallet": 0, "card": 0, "cash": 0}
    products = {}
    for order in orders:
        payments[order["payment"]] += float(order["total"])
        for item in order["items"]:
            products[item["name"]] = products.get(item["name"], 0) + int(item["qty"])
    best = sorted(({"name": name, "qty": qty} for name, qty in products.items()), key=lambda item: item["qty"], reverse=True)
    revenue = money(sum(float(order["total"]) for order in orders))
    return {"date": today(), "orders": len(orders), "revenue": revenue, "payments": {key: money(value) for key, value in payments.items()}, "bestSellers": best[:5]}


def state(data):
    return {
        "version": APP_VERSION,
        "customers": data["customers"],
        "products": data["products"],
        "orders": sorted(data["orders"], key=lambda order: order["createdAt"], reverse=True),
        "scheduled": sorted(data["scheduled"], key=lambda item: item["createdAt"], reverse=True),
        "report": report(data),
        "spentToday": {customer["id"]: spent_today(data, customer["id"]) for customer in data["customers"]},
    }


def create_order(data, body):
    customer = find(data["customers"], body.get("customerId"))
    if not customer:
        return {"error": "Cliente nao encontrado."}, 404
    lines = []
    total = 0
    for entry in body.get("items", []):
        product = find(data["products"], entry.get("id"))
        qty = int(entry.get("qty", 0))
        if not product or qty <= 0:
            return {"error": "Item invalido."}, 400
        if int(product["stock"]) < qty:
            return {"error": f"Estoque insuficiente para {product['name']}."}, 409
        line_total = money(product["price"] * qty)
        total += line_total
        lines.append({"id": product["id"], "name": product["name"], "qty": qty, "price": product["price"], "lineTotal": line_total})
    if not lines:
        return {"error": "Escolha pelo menos um item."}, 400
    total = money(total)
    if spent_today(data, customer["id"]) + total > float(customer.get("dailyLimit", 999999)):
        return {"error": "Limite diario atingido para este cliente."}, 409
    payment = body.get("payment", "wallet")
    if payment not in ["wallet", "card", "cash"]:
        return {"error": "Forma de pagamento invalida."}, 400
    if payment == "wallet":
        if float(customer["wallet"]) < total:
            return {"error": "Saldo insuficiente."}, 409
        customer["wallet"] = money(customer["wallet"] - total)
    for line in lines:
        product = find(data["products"], line["id"])
        product["stock"] = int(product["stock"]) - int(line["qty"])
    order = {"id": str(uuid.uuid4())[:8].upper(), "customerId": customer["id"], "customerName": customer["name"], "items": lines, "total": total, "payment": payment, "pickupTime": body.get("pickupTime") or "Proximo intervalo", "status": "Recebido", "createdAt": now(), "readyAt": None}
    data["orders"].append(order)
    save_data(data)
    return order, 201


HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cantina Escolar</title>
<style>
:root{--bg:#f4f7fb;--card:#fff;--soft:#eaf1f7;--text:#18222d;--muted:#607080;--line:#d8e2ea;--primary:#1769aa;--green:#00a676;--yellow:#ffb703;--red:#d64045;--shadow:0 16px 34px rgba(20,35,50,.12)}
body.dark{--bg:#101820;--card:#172635;--soft:#223545;--text:#f4f8fb;--muted:#adbbc8;--line:#34495c;--primary:#58a6ff;--green:#2bd88f;--yellow:#ffd166;--red:#ff6b6b;--shadow:0 18px 36px rgba(0,0,0,.28)}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,rgba(23,105,170,.12),transparent 270px),var(--bg);color:var(--text);font-family:Inter,system-ui,Segoe UI,sans-serif}button,input,select{font:inherit}button{border:0;cursor:pointer}.wrap{width:min(1180px,calc(100% - 26px));margin:auto;padding:18px 0 34px}.top{display:flex;justify-content:space-between;gap:14px;align-items:center}.brand{display:flex;gap:12px;align-items:center}.logo{width:48px;height:48px;border-radius:8px;background:linear-gradient(135deg,var(--primary),var(--green));color:#fff;display:grid;place-items:center;font-weight:900;box-shadow:var(--shadow)}h1,h2,h3,p{margin:0}.brand p,.muted{color:var(--muted)}.actions{display:flex;gap:8px;flex-wrap:wrap}.btn,.ghost,.icon{min-height:40px;border-radius:8px;padding:0 13px;background:var(--card);color:var(--text);border:1px solid var(--line);box-shadow:0 8px 20px rgba(0,0,0,.06);font-weight:800}.btn{background:var(--primary);border-color:var(--primary);color:#fff}.ghost{background:transparent;box-shadow:none}.icon{width:42px;padding:0}.layout{display:grid;grid-template-columns:1fr 360px;gap:18px;margin-top:16px}.tabs,.panel,.card{background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}.tabs{display:flex;gap:7px;padding:6px;margin-bottom:15px}.tab{flex:1;min-height:38px;border-radius:7px;background:transparent;color:var(--muted);font-weight:900}.tab.active{background:var(--primary);color:#fff}.view{display:none}.view.active{display:block}.panel{padding:16px;margin-bottom:15px}.title{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.filters{display:grid;grid-template-columns:1fr 210px;gap:10px}.search,select,input{width:100%;min-height:41px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--text);padding:0 10px}.chips{display:flex;gap:8px;overflow:auto;margin-top:10px}.chip{white-space:nowrap;min-height:34px;border-radius:999px;padding:0 12px;background:var(--soft);color:var(--muted);border:1px solid var(--line);font-weight:900}.chip.active{background:var(--green);border-color:var(--green);color:#fff}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.card{overflow:hidden}.art{height:122px;display:grid;place-items:center;background:linear-gradient(135deg,rgba(255,183,3,.24),rgba(0,166,118,.18));font-size:48px}.body{padding:12px;display:grid;gap:9px}.row{display:flex;justify-content:space-between;gap:10px;align-items:center}.price{font-weight:950;color:var(--primary)}.tags{display:flex;flex-wrap:wrap;gap:6px}.tag{font-size:.72rem;background:var(--soft);border:1px solid var(--line);color:var(--muted);border-radius:999px;padding:4px 8px;font-weight:800}.low{color:var(--red);font-weight:900}.side{position:sticky;top:12px}.wallet{background:linear-gradient(135deg,var(--primary),#264653 62%,var(--green));color:#fff;border:0}.wallet .muted{color:rgba(255,255,255,.76)}.wallet strong{font-size:2rem}.list{display:grid;gap:10px}.item,.metric,.lane,.report{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:10px}.qty{display:flex;gap:6px;align-items:center}.qty button{width:30px;height:30px;border-radius:7px;background:var(--card);color:var(--text);border:1px solid var(--line);font-weight:900}.total{border-top:1px solid var(--line);padding-top:12px;margin-top:12px;display:grid;gap:9px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric span{color:var(--muted);font-size:.8rem;font-weight:900}.metric strong{display:block;margin-top:8px;font-size:1.25rem}.kanban{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.order{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px;margin-top:10px}.mini{min-height:30px;border-radius:7px;padding:0 9px;background:var(--soft);border:1px solid var(--line);color:var(--text);font-weight:800}.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}.toast{position:fixed;right:18px;bottom:18px;display:grid;gap:8px;max-width:min(420px,calc(100% - 36px));z-index:10}.toast div{background:#17212b;color:#fff;border-left:5px solid var(--yellow);padding:12px;border-radius:8px;box-shadow:var(--shadow)}footer{text-align:center;color:var(--muted);font-size:.88rem;margin-top:20px}@media(max-width:980px){.layout{grid-template-columns:1fr}.side{position:static}.grid,.metrics,.kanban{grid-template-columns:repeat(2,1fr)}}@media(max-width:640px){.top{align-items:start;flex-direction:column}.actions{width:100%}.actions button{flex:1}.filters,.grid,.metrics,.kanban,.split{grid-template-columns:1fr}.wrap{width:calc(100% - 18px)}}
</style>
</head>
<body>
<div class="wrap">
<header class="top"><div class="brand"><div class="logo">CE</div><div><h1>Cantina Escolar</h1><p>Pedidos antecipados, saldo virtual e painel da cantina.</p></div></div><div class="actions"><button class="icon" id="theme">◐</button><button class="ghost" id="reload">Atualizar</button><button class="btn" id="topCheckout">Finalizar pedido</button></div></header>
<main class="layout"><section><nav class="tabs"><button class="tab active" data-tab="cliente">Cliente</button><button class="tab" data-tab="pedidos">Pedidos</button><button class="tab" data-tab="admin">Admin</button><button class="tab" data-tab="pais">Pais</button></nav>
<section class="view active" id="cliente"><div class="panel"><div class="title"><div><h2>Cardapio digital</h2><p class="muted" id="clientLine"></p></div></div><div class="filters"><input class="search" id="search" placeholder="Buscar produto, categoria ou tag"><select id="customer"></select></div><div class="chips" id="chips"></div></div><div class="grid" id="products"></div></section>
<section class="view" id="pedidos"><div class="panel"><div class="title"><h2>Status dos pedidos</h2><span class="muted">Atualizacao local em tempo real</span></div><div class="kanban" id="kanban"></div></div></section>
<section class="view" id="admin"><div class="panel"><div class="title"><h2>Painel de controle</h2><button class="btn" id="closeReport">Gerar fechamento</button></div><div class="metrics" id="metrics"></div></div><div class="split"><div class="panel"><div class="title"><h3>Mais vendidos</h3></div><div class="list" id="best"></div></div><div class="panel"><div class="title"><h3>Estoque inteligente</h3></div><div class="list" id="stock"></div></div></div><div class="panel"><div class="title"><h3>Fechamento de caixa</h3><span class="muted" id="reportDate"></span></div><div class="list" id="payments"></div></div></section>
<section class="view" id="pais"><div class="split"><div class="panel"><div class="title"><h2>Controle dos pais</h2></div><label>Limite diario</label><input type="number" id="limit" min="0" step="0.5"><button class="btn" id="saveLimit" style="margin-top:10px">Salvar limite</button></div><div class="panel"><div class="title"><h2>Agendar lanche</h2></div><label>Data</label><input type="date" id="date"><label>Produto</label><select id="scheduleProduct"></select><div class="split" style="margin-top:10px"><button class="btn" id="scheduleDay">Agendar dia</button><button class="ghost" id="scheduleWeek">Agendar semana</button></div></div></div><div class="panel"><div class="title"><h2>Historico de compras</h2><span class="muted" id="month"></span></div><div class="list" id="history"></div></div><div class="panel"><div class="title"><h2>Lanches agendados</h2></div><div class="list" id="scheduled"></div></div></section>
</section><aside class="side"><div class="panel wallet"><div class="title"><h2>Carteira virtual</h2><span id="daily"></span></div><p class="muted">Saldo disponivel</p><strong id="wallet">R$ 0,00</strong><div class="split" style="margin-top:12px"><input type="number" id="topup" min="1" placeholder="Valor"><button class="btn" id="topupBtn" style="background:#fff;color:#17212b;border-color:#fff">Carregar</button></div></div><div class="panel"><div class="title"><h2>Pedido</h2><button class="ghost" id="clear">Limpar</button></div><div class="list" id="cart"></div><div class="total"><label>Retirada</label><input type="time" id="pickup"><label>Pagamento</label><select id="payment"><option value="wallet">Saldo do sistema</option><option value="card">Cartao</option><option value="cash">Dinheiro</option></select><div class="row"><span>Total</span><strong id="total">R$ 0,00</strong></div><button class="btn" id="checkout">Finalizar pedido</button></div></div></aside></main><footer>Projeto em Python, HTML, CSS e JavaScript em arquivo unico. Versao __VERSION__.</footer></div><div class="toast" id="toast"></div>
<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)], brl=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});
const app={state:null,cart:{},tag:'Todos',search:'',customer:localStorage.getItem('cantina.customer')||'aluno-1',ready:new Set(JSON.parse(localStorage.getItem('cantina.ready')||'[]'))};
function toast(msg){const el=document.createElement('div');el.textContent=msg;$('#toast').appendChild(el);setTimeout(()=>el.remove(),4200)}
async function api(path,body){const res=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});const data=await res.json();if(!res.ok)throw new Error(data.error||'Erro na acao.');return data}
async function load(silent=true){app.state=await api('/api/state');render();notify();if(!silent)toast('Sistema atualizado.')}
function customer(){return app.state.customers.find(c=>c.id===app.customer)||app.state.customers[0]}
function cartItems(){return Object.entries(app.cart).map(([id,qty])=>{const p=app.state.products.find(x=>x.id===id);return p?{...p,qty}:null}).filter(Boolean)}
function cartTotal(){return cartItems().reduce((s,i)=>s+i.price*i.qty,0)}
function render(){renderCustomer();renderChips();renderProducts();renderCart();renderOrders();renderAdmin();renderParents()}
function renderCustomer(){const c=customer();$('#customer').innerHTML=app.state.customers.map(x=>`<option value="${x.id}" ${x.id===app.customer?'selected':''}>${x.name} - ${x.role}</option>`).join('');$('#clientLine').textContent=`${c.name} tem ${brl.format(c.wallet)} de saldo`;$('#wallet').textContent=brl.format(c.wallet);$('#daily').textContent=`Limite ${brl.format(c.dailyLimit)}`;$('#limit').value=c.dailyLimit}
function renderChips(){const tags=['Todos',...new Set(app.state.products.flatMap(p=>[p.category,...p.tags]))];$('#chips').innerHTML=tags.map(t=>`<button class="chip ${t===app.tag?'active':''}" data-chip="${t}">${t}</button>`).join('')}
function filtered(){const q=app.search.toLowerCase();return app.state.products.filter(p=>(app.tag==='Todos'||p.category===app.tag||p.tags.includes(app.tag))&&(!q||[p.name,p.category,p.description,...p.tags].join(' ').toLowerCase().includes(q)))}
function emoji(p){return {coxinha:'🥟',pastel:'🧀',wrap:'🌯',brownie:'🍫',fruta:'🍓',suco:'🧃',agua:'💧'}[p.id]||'🍽️'}
function renderProducts(){const list=filtered();$('#products').innerHTML=list.length?list.map(p=>`<article class="card"><div class="art">${emoji(p)}</div><div class="body"><div class="row"><h3>${p.name}</h3><span class="price">${brl.format(p.price)}</span></div><p class="muted">${p.description}</p><div class="tags">${p.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</div><div class="row"><span class="${p.stock<=p.lowThreshold?'low':'muted'}">${p.stock<=p.lowThreshold?'Estoque baixo: ':'Estoque: '}${p.stock}</span><button class="btn" data-add="${p.id}" ${p.stock<=0?'disabled':''}>Adicionar</button></div></div></article>`).join(''):'<div class="item">Nenhum produto encontrado.</div>'}
function renderCart(){const items=cartItems();$('#cart').innerHTML=items.length?items.map(i=>`<div class="item row"><div><strong>${i.name}</strong><p class="muted">${brl.format(i.price)} cada</p></div><div class="qty"><button data-dec="${i.id}">-</button><strong>${i.qty}</strong><button data-inc="${i.id}">+</button></div></div>`).join(''):'<div class="item muted">Seu pedido esta vazio.</div>';$('#total').textContent=brl.format(cartTotal())}
function orderCard(o){const next=o.status==='Recebido'?'Em preparo':o.status==='Em preparo'?'Pronto':'';return `<div class="order"><div class="row"><strong>#${o.id}</strong><span>${brl.format(o.total)}</span></div><strong>${o.customerName}</strong><p class="muted">${o.items.map(i=>`${i.qty}x ${i.name}`).join(', ')}</p><p class="muted">Retirada: ${o.pickupTime}</p><div class="actions" style="margin-top:8px">${next?`<button class="mini" data-status="${o.id}" data-next="${next}">${next}</button>`:''}<button class="mini" data-status="${o.id}" data-next="Cancelado">Cancelar</button></div></div>`}
function renderOrders(){const st=['Recebido','Em preparo','Pronto'];$('#kanban').innerHTML=st.map(s=>{const os=app.state.orders.filter(o=>o.status===s);return `<div class="lane"><h3>${s}</h3>${os.length?os.map(orderCard).join(''):'<div class="item muted">Sem pedidos.</div>'}</div>`}).join('')}
function renderAdmin(){const r=app.state.report, low=app.state.products.filter(p=>p.stock<=p.lowThreshold).length;$('#metrics').innerHTML=`<div class="metric"><span>Faturamento</span><strong>${brl.format(r.revenue)}</strong></div><div class="metric"><span>Pedidos</span><strong>${r.orders}</strong></div><div class="metric"><span>Alertas</span><strong>${low}</strong></div><div class="metric"><span>Ticket medio</span><strong>${brl.format(r.orders?r.revenue/r.orders:0)}</strong></div>`;$('#best').innerHTML=r.bestSellers.length?r.bestSellers.map(x=>`<div class="item row"><strong>${x.name}</strong><span>${x.qty}</span></div>`).join(''):'<div class="item muted">As vendas do dia aparecem aqui.</div>';$('#stock').innerHTML=app.state.products.map(p=>`<div class="item row"><div><strong>${p.name}</strong><p class="${p.stock<=p.lowThreshold?'low':'muted'}">${p.stock<=p.lowThreshold?'Atencao: estoque baixo':'Estoque ok'}</p></div><input type="number" min="0" value="${p.stock}" data-stock="${p.id}"></div>`).join('');$('#reportDate').textContent=r.date;$('#payments').innerHTML=`<div class="report row"><strong>Saldo do sistema</strong><span>${brl.format(r.payments.wallet)}</span></div><div class="report row"><strong>Cartao</strong><span>${brl.format(r.payments.card)}</span></div><div class="report row"><strong>Dinheiro</strong><span>${brl.format(r.payments.cash)}</span></div><div class="report row"><strong>Total vendido</strong><span>${brl.format(r.revenue)}</span></div>`}
function renderParents(){const c=customer(), month=new Date().toISOString().slice(0,7), hist=app.state.orders.filter(o=>o.customerId===c.id);const total=hist.filter(o=>o.createdAt.slice(0,7)===month&&o.status!=='Cancelado').reduce((s,o)=>s+o.total,0);$('#month').textContent=`Gasto no mes: ${brl.format(total)}`;$('#history').innerHTML=hist.length?hist.map(o=>`<div class="item"><div class="row"><strong>#${o.id} - ${o.status}</strong><span>${brl.format(o.total)}</span></div><p class="muted">${new Date(o.createdAt).toLocaleString('pt-BR')}</p><p class="muted">${o.items.map(i=>`${i.qty}x ${i.name}`).join(', ')}</p></div>`).join(''):'<div class="item muted">Nenhuma compra registrada.</div>';$('#scheduleProduct').innerHTML=app.state.products.map(p=>`<option value="${p.id}">${p.name} - ${brl.format(p.price)}</option>`).join('');const sc=app.state.scheduled.filter(x=>x.customerId===c.id);$('#scheduled').innerHTML=sc.length?sc.map(x=>`<div class="item row"><strong>${x.productName}</strong><span>${x.date}</span></div>`).join(''):'<div class="item muted">Nenhum lanche agendado.</div>'}
function add(id){const p=app.state.products.find(x=>x.id===id), q=app.cart[id]||0;if(!p||q>=p.stock)return toast('Nao ha estoque suficiente.');app.cart[id]=q+1;renderCart()}
async function checkout(){const items=cartItems().map(i=>({id:i.id,qty:i.qty}));if(!items.length)return toast('Escolha pelo menos um item.');try{const o=await api('/api/order',{customerId:app.customer,items,payment:$('#payment').value,pickupTime:$('#pickup').value||'Proximo intervalo'});app.cart={};toast(`Pedido #${o.id} recebido pela cantina.`);await load(true);setTab('pedidos')}catch(e){toast(e.message)}}
async function setStatus(id,status){try{await api('/api/status',{orderId:id,status});await load(true)}catch(e){toast(e.message)}}
async function post(path,body,msg){try{await api(path,body);toast(msg);await load(true)}catch(e){toast(e.message)}}
function notify(){app.state.orders.filter(o=>o.customerId===app.customer&&o.status==='Pronto'&&!app.ready.has(o.id)).forEach(o=>{app.ready.add(o.id);toast(`Pedido #${o.id} esta pronto para retirada.`)});localStorage.setItem('cantina.ready',JSON.stringify([...app.ready]))}
function setTab(name){$$('.tab').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));$$('.view').forEach(v=>v.classList.toggle('active',v.id===name))}
function week(start){const dates=[], d=new Date(`${start}T12:00:00`);while(dates.length<5){if(d.getDay()!==0&&d.getDay()!==6)dates.push(d.toISOString().slice(0,10));d.setDate(d.getDate()+1)}return dates}
document.addEventListener('click',e=>{const addBtn=e.target.closest('[data-add]'), inc=e.target.closest('[data-inc]'), dec=e.target.closest('[data-dec]'), chip=e.target.closest('[data-chip]'), tab=e.target.closest('[data-tab]'), status=e.target.closest('[data-status]');if(addBtn)add(addBtn.dataset.add);if(inc)add(inc.dataset.inc);if(dec){const id=dec.dataset.dec;app.cart[id]=Math.max(0,(app.cart[id]||0)-1);if(!app.cart[id])delete app.cart[id];renderCart()}if(chip){app.tag=chip.dataset.chip;renderChips();renderProducts()}if(tab)setTab(tab.dataset.tab);if(status)setStatus(status.dataset.status,status.dataset.next)});
$('#search').oninput=e=>{app.search=e.target.value;renderProducts()};$('#customer').onchange=e=>{app.customer=e.target.value;localStorage.setItem('cantina.customer',app.customer);app.cart={};render()};$('#checkout').onclick=checkout;$('#topCheckout').onclick=checkout;$('#clear').onclick=()=>{app.cart={};renderCart()};$('#reload').onclick=()=>load(false);$('#theme').onclick=()=>{document.body.classList.toggle('dark');localStorage.setItem('cantina.theme',document.body.classList.contains('dark')?'dark':'light')};$('#topupBtn').onclick=()=>post('/api/topup',{customerId:app.customer,amount:Number($('#topup').value)},'Saldo carregado.');$('#saveLimit').onclick=()=>post('/api/limit',{customerId:app.customer,dailyLimit:Number($('#limit').value)},'Limite diario atualizado.');$('#scheduleDay').onclick=()=>post('/api/schedule',{customerId:app.customer,productId:$('#scheduleProduct').value,date:$('#date').value},'Lanche agendado.');$('#scheduleWeek').onclick=async()=>{if(!$('#date').value)return toast('Escolha a data inicial.');for(const d of week($('#date').value))await api('/api/schedule',{customerId:app.customer,productId:$('#scheduleProduct').value,date:d});toast('Semana de lanches agendada.');await load(true)};$('#closeReport').onclick=()=>{const r=app.state.report;toast(`Fechamento: ${brl.format(r.revenue)} em ${r.orders} pedidos.`)};document.addEventListener('change',e=>{const s=e.target.closest('[data-stock]');if(s)post('/api/stock',{productId:s.dataset.stock,stock:Number(s.value)},'Estoque atualizado.')});if(localStorage.getItem('cantina.theme')==='dark')document.body.classList.add('dark');$('#date').value=new Date().toISOString().slice(0,10);setInterval(()=>load(true),8000);load(true).catch(e=>toast(e.message));
</script>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size).decode("utf-8") or "{}") if size else {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            raw = HTML.replace("__VERSION__", APP_VERSION).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/state":
            self.json(state(load_data()))
        else:
            self.json({"error": "Rota nao encontrada."}, 404)

    def do_POST(self):
        try:
            data = load_data()
            body = self.body()
            path = urlparse(self.path).path
            if path == "/api/order":
                payload, status = create_order(data, body)
                return self.json(payload, status)
            if path == "/api/status":
                order = find(data["orders"], body.get("orderId"))
                status = body.get("status")
                if not order or status not in ["Recebido", "Em preparo", "Pronto", "Cancelado"]:
                    return self.json({"error": "Pedido ou status invalido."}, 400)
                if order["status"] == "Cancelado" and status != "Cancelado":
                    return self.json({"error": "Pedido cancelado nao pode ser reaberto."}, 409)
                if status == "Cancelado" and order["status"] != "Cancelado":
                    for item in order["items"]:
                        product = find(data["products"], item["id"])
                        if product:
                            product["stock"] = int(product["stock"]) + int(item["qty"])
                    if order["payment"] == "wallet":
                        customer = find(data["customers"], order["customerId"])
                        if customer:
                            customer["wallet"] = money(customer["wallet"] + order["total"])
                order["status"] = status
                if status == "Pronto":
                    order["readyAt"] = now()
                save_data(data)
                return self.json(order)
            if path == "/api/topup":
                customer = find(data["customers"], body.get("customerId"))
                amount = money(body.get("amount", 0))
                if not customer or amount <= 0:
                    return self.json({"error": "Cliente ou valor invalido."}, 400)
                customer["wallet"] = money(customer["wallet"] + amount)
                save_data(data)
                return self.json(customer)
            if path == "/api/limit":
                customer = find(data["customers"], body.get("customerId"))
                limit = money(body.get("dailyLimit", 0))
                if not customer or limit < 0:
                    return self.json({"error": "Cliente ou limite invalido."}, 400)
                customer["dailyLimit"] = limit
                save_data(data)
                return self.json(customer)
            if path == "/api/stock":
                product = find(data["products"], body.get("productId"))
                stock = int(body.get("stock", -1))
                if not product or stock < 0:
                    return self.json({"error": "Produto ou estoque invalido."}, 400)
                product["stock"] = stock
                save_data(data)
                return self.json(product)
            if path == "/api/schedule":
                customer = find(data["customers"], body.get("customerId"))
                product = find(data["products"], body.get("productId"))
                if not customer or not product or not body.get("date"):
                    return self.json({"error": "Dados do agendamento invalidos."}, 400)
                item = {"id": str(uuid.uuid4())[:8].upper(), "customerId": customer["id"], "customerName": customer["name"], "productId": product["id"], "productName": product["name"], "date": body["date"], "createdAt": now()}
                data["scheduled"].append(item)
                save_data(data)
                return self.json(item, 201)
            self.json({"error": "Rota nao encontrada."}, 404)
        except Exception as exc:
            self.json({"error": f"Erro interno: {exc}"}, 500)


def main():
    load_data()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Cantina Escolar v{APP_VERSION} rodando em http://{HOST}:{PORT}")
    print("Pressione Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
