import{LitElement,html,css}from"https://unpkg.com/lit-element@2.4.0/lit-element.js?module";
let _scanOk=false;const _s=document.createElement("script");_s.src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js";_s.onload=()=>{_scanOk=true};document.head.appendChild(_s);

const CATS=["","Ovoce a zelenina","Mléčné výrobky","Maso a ryby","Pečivo","Nápoje","Mražené","Konzervy","Sladkosti","Koření","Drogerie","Ostatní"];
const LOCS=["","Lednice","Mrazák","Spíž","Skříňka","Koupelna"];

class ShoppingListPanel extends LitElement{
static get properties(){return{hass:{type:Object},data:{type:Object},tab:{type:String},scan:{type:Boolean},search:{type:String},filterCat:{type:String},filterLoc:{type:String},editing:{type:String},editingReceipt:{type:String},toast:{type:String},uploadState:{type:String},uploadPreview:{type:String},uploadProgress:{type:Number},recipePortions:{type:Object},copyModalText:{type:String}};}
constructor(){super();this.data={inventory:{},pending_receipts:{},recipes:{},consumption_log:[]};this.tab="dashboard";this.scan=false;this.search="";this.filterCat="";this.filterLoc="";this.editing="";this.editingReceipt="";this.toast="";this._sc=null;this.uploadState="";this.uploadPreview="";this.uploadProgress=0;this.recipePortions={};this.copyModalText="";}
connectedCallback(){super.connectedCallback();this._fetch();this.hass?.connection?.subscribeEvents(()=>this._fetch(),"shopping_list_ocr_updated");}
async _fetch(){if(!this.hass)return;try{const r=await this.hass.fetchWithAuth("/api/shopping_list/data");if(r.ok)this.data=await r.json();}catch(e){}}
_t(m){this.toast=m;setTimeout(()=>{this.toast=""},3500);}
_svc(s,d){this.hass.callService("shopping_list_ocr",s,d);}

static get styles(){return css`
:host{--a:#6366f1;--g:#22c55e;--r:#ef4444;--w:#f59e0b;--bg:#0f172a;--card:#1e293b;--border:rgba(255,255,255,.08);--txt:#e2e8f0;--dim:#94a3b8;display:block;min-height:100vh;background:var(--primary-background-color,var(--bg));color:var(--primary-text-color,var(--txt));font-family:system-ui,-apple-system,sans-serif}
.p{padding:20px;max-width:1400px;margin:0 auto}
.hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px}
.hdr h1{font-size:1.8rem;font-weight:700;margin:0;display:flex;align-items:center;gap:8px}
.tabs{display:flex;gap:4px;background:var(--card-background-color,var(--card));border-radius:12px;padding:4px;margin-bottom:24px;flex-wrap:wrap;width:fit-content}
.tb{padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:600;font-size:.85rem;transition:.2s;color:var(--dim);white-space:nowrap;user-select:none}
.tb.on{background:var(--a);color:#fff;box-shadow:0 2px 10px rgba(99,102,241,.4)}
.tb .bdg{background:var(--r);color:#fff;font-size:.65rem;padding:1px 6px;border-radius:10px;margin-left:4px}
.gr{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.c{background:var(--card-background-color,var(--card));border-radius:12px;overflow:hidden;border:1px solid var(--border);transition:.2s;position:relative;display:flex;flex-direction:column}
.c:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(0,0,0,.3)}
.cb{padding:14px;display:flex;flex-direction:column;gap:6px;flex:1}
.ci{width:100%;height:130px;object-fit:cover;background:#334155}
.ct{font-weight:600;font-size:.95rem;margin:0}
.cm{font-size:.78rem;color:var(--dim)}
.cv{font-size:1.4rem;font-weight:700}
.cv small{font-size:.8rem;font-weight:400;opacity:.7}
.st{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.65);color:#fff;padding:2px 8px;border-radius:5px;font-size:.68rem;font-weight:700;text-transform:uppercase;backdrop-filter:blur(4px)}
.loc{font-size:.7rem;padding:2px 8px;border-radius:5px;background:rgba(99,102,241,.15);color:#a5b4fc;display:inline-block}
.cat{font-size:.7rem;padding:2px 8px;border-radius:5px;background:rgba(34,197,94,.12);color:#86efac;display:inline-block}
.exp-warn{font-size:.7rem;padding:2px 8px;border-radius:5px;background:rgba(245,158,11,.15);color:#fbbf24;display:inline-block}
.exp-bad{font-size:.7rem;padding:2px 8px;border-radius:5px;background:rgba(239,68,68,.15);color:#fca5a5;display:inline-block}
.low{font-size:.7rem;padding:2px 8px;border-radius:5px;background:rgba(239,68,68,.15);color:#fca5a5;display:inline-block}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:8px 16px;border:none;border-radius:8px;font-weight:600;font-size:.82rem;cursor:pointer;transition:.15s;text-decoration:none;white-space:nowrap}
.bp{background:var(--a);color:#fff}.bg{background:var(--g);color:#0f172a}.bo{background:transparent;border:1px solid var(--border);color:var(--txt)}
.bs{padding:6px 12px;font-size:.78rem}
.bw{width:100%}
.tbar{display:flex;gap:10px;align-items:center;margin-bottom:20px;flex-wrap:wrap;background:var(--card-background-color,var(--card));padding:12px 16px;border-radius:12px;border:1px solid var(--border)}
.tbar input[type=text],.tbar select{flex:1;min-width:120px;padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:rgba(255,255,255,.04);color:inherit;font-size:.85rem}
.tbar select{flex:0 0 auto;min-width:140px}
.qr{display:flex;gap:4px;margin-top:auto}
.qb{flex:1;padding:6px;border:1px solid var(--border);background:transparent;color:inherit;border-radius:6px;font-weight:700;font-size:.95rem;cursor:pointer;transition:.15s}
.qb:hover{background:rgba(255,255,255,.06)}
.ri{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border);font-size:.85rem}
.empty{text-align:center;padding:50px 20px;color:var(--dim)}
.empty p{margin:6px 0}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.9);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:10000;padding:20px}
#reader{width:100%;max-width:460px;border-radius:12px;overflow:hidden}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--card-background-color,var(--card));padding:10px 24px;border-radius:10px;font-size:.85rem;box-shadow:0 6px 24px rgba(0,0,0,.5);border:1px solid var(--border);z-index:10001;animation:fi .3s}
@keyframes fi{from{opacity:0;transform:translateX(-50%) translateY(16px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.stat{background:var(--card-background-color,var(--card));border-radius:12px;padding:20px;border:1px solid var(--border);text-align:center}
.stat-val{font-size:2rem;font-weight:800;margin:4px 0}
.stat-lbl{font-size:.8rem;color:var(--dim)}
.edit-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.edit-row select,.edit-row input{padding:6px 8px;border-radius:6px;border:1px solid var(--border);background:rgba(255,255,255,.04);color:inherit;font-size:.8rem;flex:1;min-width:80px}
.upl-card{background:var(--card-background-color,var(--card));border-radius:12px;border:1px solid var(--border);overflow:hidden;margin-bottom:20px}
.upl-preview{width:100%;max-height:200px;object-fit:cover;display:block}
.upl-body{padding:16px;display:flex;flex-direction:column;gap:10px}
.upl-status{font-size:.85rem;font-weight:600;display:flex;align-items:center;gap:8px}
.upl-bar-wrap{width:100%;height:8px;background:rgba(255,255,255,.08);border-radius:4px;overflow:hidden}
.upl-bar{height:100%;border-radius:4px;transition:width .4s ease;background:linear-gradient(90deg,var(--a),#818cf8)}
.upl-bar.done{background:var(--g)}
.upl-bar.err{background:var(--r)}
.upl-steps{display:flex;gap:4px;align-items:center;margin-top:4px}
.upl-step{flex:1;height:4px;border-radius:2px;background:rgba(255,255,255,.08)}
.upl-step.active{background:var(--a);animation:pulse 1.5s infinite}
.upl-step.done{background:var(--g)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
`;}
render(){const inv=Object.values(this.data.inventory||{});const pc=Object.keys(this.data.pending_receipts||{}).length;
return html`<div class="p">
<div class="hdr"><h1><ha-icon icon="mdi:cart-outline"></ha-icon> Nákupník</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap">
<button class="btn bp" @click=${this._toggleScan}><ha-icon icon="mdi:barcode-scan"></ha-icon> EAN</button>
</div></div>
<div class="tabs">
<div class="tb ${this.tab==='dashboard'?'on':''}" @click=${()=>this.tab='dashboard'}>Přehled</div>
<div class="tb ${this.tab==='inventory'?'on':''}" @click=${()=>this.tab='inventory'}>Sklad (${inv.length})</div>
<div class="tb ${this.tab==='receipts'?'on':''}" @click=${()=>this.tab='receipts'}>Účtenky${pc?html`<span class="bdg">${pc}</span>`:''}</div>
<div class="tb ${this.tab==='recipes'?'on':''}" @click=${()=>this.tab='recipes'}>Recepty</div>
</div>
${this.tab==='dashboard'?this._dash(inv):''}
${this.tab==='inventory'?this._inv(inv):''}
${this.tab==='receipts'?this._rec():''}
${this.tab==='recipes'?this._rcp():''}
${this.scan?html`<div class="modal"><div id="reader"></div><button class="btn bo" style="margin-top:16px" @click=${this._toggleScan}>Zavřít</button></div>`:''}
${this.copyModalText?html`<div class="modal" @click=${()=>this.copyModalText=""}><div class="c" style="width:100%;max-width:500px;padding:20px" @click=${e=>e.stopPropagation()}><h3 style="margin-top:0">Ingredience do nákupu</h3><p class="cm">Zkopírujte si seznam do nákupní aplikace:</p><textarea style="width:100%;height:300px;background:rgba(0,0,0,0.2);color:inherit;border:1px solid var(--border);border-radius:8px;padding:10px;font-family:monospace;font-size:0.9rem" readonly>${this.copyModalText}</textarea><button class="btn bp bw" style="margin-top:16px" @click=${()=>this.copyModalText=""}>Zavřít</button></div></div>`:''}
${this.toast?html`<div class="toast">${this.toast}</div>`:''}
</div>`;}

_dash(inv){
const now=new Date();const expSoon=inv.filter(i=>{if(!i.expiry_date)return false;const d=new Date(i.expiry_date);const diff=(d-now)/(1000*60*60*24);return diff>=0&&diff<=3;}).length;
const expired=inv.filter(i=>{if(!i.expiry_date)return false;return new Date(i.expiry_date)<now;}).length;
const low=inv.filter(i=>i.min_quantity>0&&i.quantity<=i.min_quantity).length;
const total=inv.reduce((s,i)=>s+(i.last_price||0)*(i.quantity||0),0);
const rc=Object.keys(this.data.recipes||{}).length;
return html`<section>
<div class="stats">
<div class="stat"><div class="stat-val" style="color:var(--a)">${inv.length}</div><div class="stat-lbl">Položek ve skladu</div></div>
<div class="stat"><div class="stat-val" style="color:var(--g)">${total.toFixed(0)} Kč</div><div class="stat-lbl">Hodnota skladu</div></div>
<div class="stat"><div class="stat-val" style="color:${low?'var(--r)':'var(--g)'}">${low}</div><div class="stat-lbl">Nízké zásoby</div></div>
<div class="stat"><div class="stat-val" style="color:${expSoon?'var(--w)':'var(--g)'}">${expSoon}</div><div class="stat-lbl">Brzy expiruje</div></div>
<div class="stat"><div class="stat-val" style="color:${expired?'var(--r)':'var(--g)'}">${expired}</div><div class="stat-lbl">Po expiraci</div></div>
<div class="stat"><div class="stat-val" style="color:var(--a)">${rc}</div><div class="stat-lbl">Receptů</div></div>
</div>
${low>0?html`<h3 style="margin:16px 0 8px">⚠️ Nízké zásoby</h3><div class="gr">${inv.filter(i=>i.min_quantity>0&&i.quantity<=i.min_quantity).map(i=>this._card(i))}</div>`:''}
${expSoon>0?html`<h3 style="margin:16px 0 8px">⏰ Brzy expiruje</h3><div class="gr">${inv.filter(i=>{if(!i.expiry_date)return false;const d=(new Date(i.expiry_date)-now)/(86400000);return d>=0&&d<=3;}).map(i=>this._card(i))}</div>`:''}
${expired>0?html`<h3 style="margin:16px 0 8px">❌ Po expiraci</h3><div class="gr">${inv.filter(i=>i.expiry_date&&new Date(i.expiry_date)<now).map(i=>this._card(i))}</div>`:''}
</section>`;}

_inv(inv){
let items=inv;
if(this.search){const s=this.search.toLowerCase();items=items.filter(i=>i.name.toLowerCase().includes(s));}
if(this.filterCat)items=items.filter(i=>i.category===this.filterCat);
if(this.filterLoc)items=items.filter(i=>i.location===this.filterLoc);
return html`<section>
<div class="tbar">
<input type="text" placeholder="Hledat…" .value=${this.search} @input=${e=>this.search=e.target.value}>
<select @change=${e=>this.filterCat=e.target.value}><option value="">Všechny kategorie</option>${CATS.filter(c=>c).map(c=>html`<option value=${c} ?selected=${this.filterCat===c}>${c}</option>`)}</select>
<select @change=${e=>this.filterLoc=e.target.value}><option value="">Všechna místa</option>${LOCS.filter(l=>l).map(l=>html`<option value=${l} ?selected=${this.filterLoc===l}>${l}</option>`)}</select>
<input id="ean-in" type="text" placeholder="EAN kód…" style="max-width:160px" @keyup=${e=>{if(e.key==='Enter')this._addEan();}}>
<button class="btn bp bs" @click=${this._addEan}>+EAN</button>
</div>
${items.length===0?html`<div class="empty"><p><strong>Žádné položky</strong></p></div>`:html`<div class="gr">${items.map(i=>this._card(i))}</div>`}
</section>`;}

_card(item){
const now=new Date();let expTag='';
if(item.expiry_date){const d=new Date(item.expiry_date);const diff=(d-now)/(86400000);
if(diff<0)expTag=html`<span class="exp-bad">Expirováno</span>`;
else if(diff<=3)expTag=html`<span class="exp-warn">Exp. ${d.toLocaleDateString("cs")}</span>`;
else expTag=html`<span class="cm">Exp. ${d.toLocaleDateString("cs")}</span>`;}
const isLow=item.min_quantity>0&&item.quantity<=item.min_quantity;
const isEditing=this.editing===item.name;
return html`<div class="c">
${item.image_url?html`<img class="ci" src="${item.image_url}" loading="lazy" onerror="this.style.display='none'">`:''} 
${item.store?html`<span class="st">${item.store}</span>`:''}
<div class="cb">
<h3 class="ct">${item.name}</h3>
<div style="display:flex;gap:4px;flex-wrap:wrap">
${item.category?html`<span class="cat">${item.category}</span>`:''}
${item.location?html`<span class="loc">${item.location}</span>`:''}
${expTag}
${isLow?html`<span class="low">Nízká zásoba!</span>`:''}
</div>
<div class="cv">${item.quantity} <small>${item.unit||'ks'}</small></div>
${item.last_price?html`<div class="cm">${item.last_price} Kč</div>`:''}
${isEditing?html`
<div class="edit-row">
<select id="ecat"><option value="">Kategorie</option>${CATS.filter(c=>c).map(c=>html`<option value=${c} ?selected=${item.category===c}>${c}</option>`)}</select>
<select id="eloc"><option value="">Místo</option>${LOCS.filter(l=>l).map(l=>html`<option value=${l} ?selected=${item.location===l}>${l}</option>`)}</select>
</div>
<div class="edit-row">
<input id="eexp" type="date" .value=${item.expiry_date||''} placeholder="Expirace">
<input id="emin" type="number" .value=${String(item.min_quantity||0)} placeholder="Min" style="max-width:60px">
</div>
<div style="display:flex;gap:4px">
<button class="btn bg bs bw" @click=${()=>this._saveEdit(item)}>Uložit</button>
<button class="btn bo bs" @click=${()=>{this.editing="";}}>×</button>
<button class="btn bs" style="background:var(--r);color:#fff" @click=${()=>this._del(item.name)}>Smazat</button>
</div>
`:html`
<div class="qr">
<button class="qb" @click=${()=>this._qty(item.name,-1)}>−</button>
<button class="qb" @click=${()=>this._qty(item.name,1)}>+</button>
<button class="qb" style="font-size:.7rem" @click=${()=>{this.editing=item.name;}}>✏️</button>
</div>
`}
</div></div>`;}

_rec(){const rr=Object.values(this.data.pending_receipts||{});
return html`<section>
<div class="tbar">
<input type="file" id="rf" accept="image/*" capture="environment" style="display:none" @change=${this._upload}>
<button class="btn bg" @click=${()=>this.shadowRoot.getElementById('rf').click()} ?disabled=${!!this.uploadState}><ha-icon icon="mdi:camera"></ha-icon> ${this.uploadState?'Zpracovávám…':'Nahrát účtenku'}</button>
<button class="btn bo" @click=${()=>{this._svc("scan_folder",{});this._t("Skenování…");setTimeout(()=>this._fetch(),4000);}}><ha-icon icon="mdi:folder-search-outline"></ha-icon> Složka</button>
</div>
${this.uploadState?html`
<div class="upl-card">
${this.uploadPreview?html`<img class="upl-preview" src="${this.uploadPreview}">`:''}
<div class="upl-body">
<div class="upl-status">
${this.uploadState==='uploading'?html`<ha-icon icon="mdi:cloud-upload"></ha-icon> Nahrávám fotku…`:''}
${this.uploadState==='processing'?html`<ha-icon icon="mdi:text-recognition"></ha-icon> OCR zpracování…`:''}
${this.uploadState==='done'?html`<ha-icon icon="mdi:check-circle" style="color:var(--g)"></ha-icon> <span style="color:var(--g)">Hotovo!</span>`:''}
${this.uploadState==='error'?html`<ha-icon icon="mdi:alert-circle" style="color:var(--r)"></ha-icon> <span style="color:var(--r)">Chyba zpracování</span>`:''}
</div>
<div class="upl-bar-wrap"><div class="upl-bar ${this.uploadState==='done'?'done':''} ${this.uploadState==='error'?'err':''}" style="width:${this.uploadProgress}%"></div></div>
<div class="upl-steps">
<div class="upl-step ${this.uploadProgress>=33?'done':this.uploadState==='uploading'?'active':''}"></div>
<div class="upl-step ${this.uploadProgress>=66?'done':this.uploadState==='processing'?'active':''}"></div>
<div class="upl-step ${this.uploadProgress>=100?'done':''}"></div>
</div>
<div class="cm">${this.uploadState==='uploading'?'Odesílám na server…':this.uploadState==='processing'?'Rozpoznávám text na účtence…':this.uploadState==='done'?'Účtenka byla úspěšně zpracována':this.uploadState==='error'?'Zkuste to znovu s lepší fotkou':''}  </div>
</div>
</div>`:''}
${rr.length===0&&!this.uploadState?html`<div class="empty"><p><strong>Žádné účtenky</strong></p><p>Nahrajte fotku účtenky tlačítkem výše.</p></div>`:html`<div class="gr">
${rr.map(r=>{
const isEd=this.editingReceipt===r.id;
return html`
<div class="c">${r.store?html`<span class="st">${r.store}</span>`:''}<div class="cb">
<div class="cm" style="display:flex;justify-content:space-between">
  <span>${new Date(r.date).toLocaleString("cs")}</span>
  <button class="btn bo bs" style="padding:2px 6px" @click=${()=>{this.editingReceipt=isEd?'':r.id}}>${isEd?'Zavřít':'Upravit'}</button>
</div>
${isEd?html`
<div style="display:flex;flex-direction:column;gap:8px;margin-top:8px">
  <input type="text" placeholder="Obchod" .value=${r.store||''} @input=${e=>r.store=e.target.value} style="padding:6px;border-radius:6px;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:inherit">
  ${r.items.map((i,idx)=>html`
    <div class="edit-row">
      <input type="text" .value=${i.name} @input=${e=>i.name=e.target.value} style="flex:2">
      <input type="number" .value=${String(i.price)} @input=${e=>i.price=parseFloat(e.target.value)} style="flex:1;max-width:60px">
      <button class="qb" style="color:var(--r)" @click=${()=>{r.items.splice(idx,1);this.requestUpdate();}}>×</button>
    </div>
  `)}
  <button class="btn bo bs" @click=${()=>{r.items.push({name:"",price:0,quantity:1});this.requestUpdate();}}>+ Položka</button>
  <div style="display:flex;gap:4px">
    <button class="btn bg bw" @click=${()=>this._saveRec(r)}>Uložit</button>
    <button class="btn bo" style="color:var(--r)" @click=${()=>this._delRec(r.id)}>Smazat</button>
  </div>
</div>
`:html`
${r.items.length===0?html`<div class="cm" style="margin:10px 0;text-align:center">Žádné rozpoznané položky.<br>Přidejte je ručně přes Upravit.</div>`:r.items.map(i=>html`<div class="ri"><span>${i.name}</span><span style="font-weight:600">${i.price} Kč</span></div>`)}
<div class="cm" style="margin-top:6px">Celkem: <strong>${r.items.reduce((s,i)=>s+i.price,0).toFixed(0)} Kč</strong></div>
<button class="btn bp bw" style="margin-top:8px" @click=${()=>{this._svc("confirm_receipt",{receipt_id:r.id});this._t("Přidáno do skladu");setTimeout(()=>this._fetch(),1000);}}>Potvrdit</button>
`}
</div></div>`})}
</div>`}
</section>`;}

_scaleIng(text, p, base){
if(p===base)return text;
const r=p/base;
const m=text.match(/^([\d.,]+(?:-[\d.,]+)?|[\d]+\/[\d]+)\s*(.*)/);
if(!m)return text;
let numStr=m[1].replace(',', '.');
let val=0;
if(numStr.includes('-')){const pts=numStr.split('-');val=(parseFloat(pts[0])+parseFloat(pts[1]))/2;}
else if(numStr.includes('/')){const pts=numStr.split('/');val=parseFloat(pts[0])/parseFloat(pts[1]);}
else{val=parseFloat(numStr);}
if(isNaN(val))return text;
let res=val*r;
let resStr=res%1===0?res.toString():res.toFixed(1).replace('.0','').replace('.',',');
return resStr+' '+m[2];
}

_rcp(){const rr=Object.entries(this.data.recipes||{});
return html`<section>
<div class="tbar">
<input id="rurl" type="text" placeholder="URL receptu…" @keyup=${e=>{if(e.key==='Enter')this._addRcp();}}>
<button class="btn bp" @click=${this._addRcp}><ha-icon icon="mdi:plus"></ha-icon> Přidat</button>
</div>
${rr.length===0?html`<div class="empty"><p><strong>Žádné recepty</strong></p></div>`:html`<div class="gr">${rr.map(([id,r])=>{
const base=4;const p=this.recipePortions[id]||base;
const ings=(r.ingredients||[]).map(i=>this._scaleIng(i, p, base));
return html`
<div class="c">${r.image_url?html`<img class="ci" src="${r.image_url}" loading="lazy" onerror="this.style.display='none'">`:''}
<div class="cb"><h3 class="ct">${r.title}</h3>
<div style="display:flex;align-items:center;gap:10px;margin:8px 0;background:rgba(255,255,255,0.05);padding:6px;border-radius:8px;width:fit-content">
<button class="qb" style="padding:2px 8px;flex:none;font-size:1.2rem" @click=${()=>{this.recipePortions={...this.recipePortions,[id]:Math.max(1, p-1)};}}>−</button>
<span style="font-weight:600;font-size:0.9rem">${p} porcí</span>
<button class="qb" style="padding:2px 8px;flex:none;font-size:1.2rem" @click=${()=>{this.recipePortions={...this.recipePortions,[id]:p+1};}}>+</button>
</div>
<div class="cm" style="max-height:120px;overflow-y:auto;padding-right:4px;margin-bottom:8px">
${ings.map(i=>html`<div style="margin-bottom:4px">• ${i}</div>`)}
</div>
<div style="display:flex;gap:6px;margin-top:auto">
<a href="${r.pdf_url}" target="_blank" class="btn bo" style="text-decoration:none;flex:1">PDF</a>
<button class="btn bp" style="flex:2" @click=${()=>{this.copyModalText=ings.join('\n');}}>Do nákupu</button>
</div>
</div></div>`})}</div>`}
</section>`;}

// --- Actions ---
async _upload(e){
const f=e.target.files?.[0];if(!f)return;
// Show preview
this.uploadPreview=URL.createObjectURL(f);
this.uploadState="uploading";this.uploadProgress=10;this.tab="receipts";
const fd=new FormData();fd.append("file",f);
// Animate upload progress
const pInt=setInterval(()=>{if(this.uploadProgress<30)this.uploadProgress+=4;},200);
try{
const r=await this.hass.fetchWithAuth("/api/shopping_list/upload",{method:"POST",body:fd});
clearInterval(pInt);
if(r.ok){
this.uploadState="processing";this.uploadProgress=40;
// Animate OCR processing
const oInt=setInterval(()=>{if(this.uploadProgress<85)this.uploadProgress+=3;},400);
// Poll for new receipts (OCR is async on backend)
const startCount=Object.keys(this.data.pending_receipts||{}).length;
let attempts=0;const maxAttempts=20;
const poll=setInterval(async()=>{
attempts++;
await this._fetch();
const newCount=Object.keys(this.data.pending_receipts||{}).length;
if(newCount>startCount||attempts>=maxAttempts){
clearInterval(oInt);clearInterval(poll);
if(newCount>startCount){this.uploadState="done";this.uploadProgress=100;
setTimeout(()=>{this.uploadState="";this.uploadPreview="";this.uploadProgress=0;},4000);
}else{this.uploadState="error";this.uploadProgress=100;
setTimeout(()=>{this.uploadState="";this.uploadPreview="";this.uploadProgress=0;},5000);
}}},2000);
}else{this.uploadState="error";this.uploadProgress=100;
setTimeout(()=>{this.uploadState="";this.uploadPreview="";this.uploadProgress=0;},5000);}
}catch(err){clearInterval(pInt);this.uploadState="error";this.uploadProgress=100;
setTimeout(()=>{this.uploadState="";this.uploadPreview="";this.uploadProgress=0;},5000);}
e.target.value="";}

_toggleScan(){this.scan=!this.scan;if(this.scan){if(!_scanOk){this._t("Skener se načítá…");this.scan=false;return;}setTimeout(()=>{try{this._sc=new Html5Qrcode("reader");this._sc.start({facingMode:"environment"},{fps:10,qrbox:{width:250,height:150}},(t)=>{this._toggleScan();this._addEanVal(t);}).catch(()=>{this._t("Kamera nedostupná");this.scan=false;});}catch(e){this.scan=false;}},400);}else if(this._sc){try{this._sc.stop();}catch(e){}this._sc=null;}}

_addEan(){const i=this.shadowRoot.getElementById("ean-in");if(!i)return;this._addEanVal(i.value.trim());i.value="";}
_addEanVal(v){if(!v)return;this._svc("add_item_by_ean",{ean:v});this._t(`EAN: ${v}…`);setTimeout(()=>this._fetch(),2000);}
_qty(n,d){const i=this.data.inventory[n];if(!i)return;const nq=Math.max(0,i.quantity+d);this._svc("update_inventory",{name:n,quantity:nq,last_price:i.last_price||0,unit:i.unit||"ks",image_url:i.image_url||"",store:i.store||"",category:i.category||"",location:i.location||"",expiry_date:i.expiry_date||"",min_quantity:i.min_quantity||0});i.quantity=nq;this.requestUpdate();}
_del(n){this._svc("update_inventory",{name:n,action:"delete"});delete this.data.inventory[n];this.editing="";this.requestUpdate();this._t("Smazáno");}
_saveEdit(item){const cat=this.shadowRoot.getElementById("ecat")?.value||"";const loc=this.shadowRoot.getElementById("eloc")?.value||"";const exp=this.shadowRoot.getElementById("eexp")?.value||"";const min=parseInt(this.shadowRoot.getElementById("emin")?.value||"0",10);
this._svc("update_inventory",{name:item.name,quantity:item.quantity,last_price:item.last_price||0,unit:item.unit||"ks",image_url:item.image_url||"",store:item.store||"",category:cat,location:loc,expiry_date:exp,min_quantity:min});
item.category=cat;item.location=loc;item.expiry_date=exp;item.min_quantity=min;this.editing="";this.requestUpdate();this._t("Uloženo");}
_saveRec(r){this._svc("update_pending_receipt",{receipt_id:r.id,items:r.items,store:r.store});this.editingReceipt="";this._t("Uloženo");}
_delRec(id){if(confirm("Smazat účtenku?")){this._svc("update_pending_receipt",{receipt_id:id,action:"delete"});delete this.data.pending_receipts[id];this.editingReceipt="";this.requestUpdate();}}
_addRcp(){const i=this.shadowRoot.getElementById("rurl");if(!i)return;const u=i.value.trim();if(!u)return;this._svc("add_recipe",{url:u});i.value="";this._t("Stahuji recept…");setTimeout(()=>this._fetch(),5000);}
}
customElements.define("shopping-list-panel",ShoppingListPanel);
