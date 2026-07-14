const fs = require("fs");
const vm = require("vm");
const path = require("path");

const root = path.resolve(__dirname, "..");
const jsPath = path.join(root, "static", "js", "cotacao_lances.js");
const js = fs.readFileSync(jsPath, "utf8");
const marker = "// MEDBOX - LANCES OPERACIONAL UNICO";
const idx = js.lastIndexOf(marker);
if (idx < 0) throw new Error("Bloco operacional unico nao encontrado");
const finalBlock = js.slice(idx);

class FakeClassList {
  constructor(names = []) { this.values = new Set(names); }
  toggle(name, on) { if (on) this.values.add(name); else this.values.delete(name); }
  has(name) { return this.values.has(name); }
  contains(name) { return this.values.has(name); }
}

class FakeElement {
  constructor(value = "") {
    this.value = value;
    this.textContent = value;
    this.innerHTML = "";
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.selectedOptions = [];
    this.classList = new FakeClassList();
  }
  appendChild(child) { this.children.push(child); child.parent = this; return child; }
  contains(target) { return this === target || this.children.includes(target); }
  addEventListener() {}
  matches() { return false; }
  closest() { return null; }
  getBoundingClientRect() { return { left: 0, bottom: 20, width: 240 }; }
}

class FakeInput extends FakeElement {
  constructor(selector, value = "") {
    super(value);
    this.selector = selector;
    this.classList = new FakeClassList(selector.slice(1).split(" "));
  }
  matches(selectorList) {
    return selectorList.split(",").map((s) => s.trim()).includes(this.selector);
  }
  closest(selector) {
    if (selector.includes("tbody tr") || selector === "tr") return this.row;
    return null;
  }
}

class FakeCell extends FakeElement {
  constructor() {
    super("");
    this.strong = new FakeElement("R$ 0,00");
    this.small = new FakeElement("-");
  }
  querySelector(selector) {
    if (selector === "strong") return this.strong;
    if (selector === "small") return this.small;
    return null;
  }
}

class FakeRow {
  constructor(values) {
    this.dataset = {};
    this.classList = new FakeClassList();
    this.fields = {};
    for (const [selector, value] of Object.entries(values)) {
      if (!selector.startsWith(".")) continue;
      this.fields[selector] = new FakeInput(selector, value);
      this.fields[selector].row = this;
    }
    this.statusCell = new FakeElement("");
    this.menorValorCell = new FakeCell();
    this.strong = new FakeElement(values.descricao || "PRODUTO ORIGINAL");
    this.children = [null, { querySelector: (selector) => selector === "strong" ? this.strong : null }];
  }
  querySelector(selector) {
    if (selector === ".status-cell") return this.statusCell;
    if (selector === ".menor-valor-cell") return this.menorValorCell;
    return this.fields[selector] || null;
  }
}

const rows = [
  new FakeRow({
    descricao: "PRODUTO ORIGINAL",
    ".sku-master-input": "SKU A",
    ".categoria-input": "CORRELATOS",
    ".qtd-input": "10",
    ".osinfo-input": "R$ 20,00",
    ".ultima-input": "R$ 0,00",
    ".concorrente-input": "R$ 0,00",
    ".custo-manual-input": "R$ 10,00",
    ".markup-atual-input": "80",
    ".medbox-input": "",
    ".empresa-input": "",
    ".fornecedor-input": "FORN",
    ".fabricante-input": "MARCA"
  }),
  new FakeRow({
    descricao: "SEM SKU",
    ".sku-master-input": "",
    ".categoria-input": "CORRELATOS",
    ".qtd-input": "5",
    ".osinfo-input": "R$ 10,00",
    ".ultima-input": "R$ 0,00",
    ".concorrente-input": "R$ 0,00",
    ".custo-manual-input": "",
    ".markup-atual-input": "80",
    ".medbox-input": "",
    ".empresa-input": "",
    ".fornecedor-input": "",
    ".fabricante-input": ""
  })
];

const kpis = new Map();
const listeners = { document: {}, window: {} };
function kpi(name) {
  if (!kpis.has(name)) kpis.set(name, new FakeElement(""));
  return kpis.get(name);
}
function addListener(bucket, type, fn) {
  if (!listeners[bucket][type]) listeners[bucket][type] = [];
  listeners[bucket][type].push(fn);
}

const document = {
  body: new FakeElement(""),
  createElement(tag) { const el = new FakeElement(""); el.tagName = tag.toUpperCase(); return el; },
  addEventListener(type, fn) { addListener("document", type, fn); },
  querySelectorAll(selector) { return selector === "#tabelaLances tbody tr" ? rows : []; },
  querySelector(selector) {
    const match = selector.match(/^\[data-kpi="(.+)"\]$/);
    return match ? kpi(match[1]) : null;
  }
};

let fetchCalls = 0;
const context = {
  window: { scrollX: 0, scrollY: 0, addEventListener(type, fn) { addListener("window", type, fn); } },
  document,
  console,
  Intl,
  Number,
  String,
  Array,
  Math,
  setTimeout(fn) { if (typeof fn === "function") fn(); return 1; },
  clearTimeout() {},
  fetch: async (url, options) => {
    fetchCalls += 1;
    if (!String(url).includes("/cotacoes/lances/sugerir-skus?q=")) throw new Error("endpoint errado");
    if (options && options.method && options.method !== "GET") throw new Error("autocomplete deve ser GET");
    return { json: async () => ({ ok: true, sugestoes: [{ sku_master: "SKU NOVO", categoria: "NOVA", fornecedor_menor_custo: "FORN NOVO", marca_fabricante: "MARCA NOVA", menor_custo_unitario: 4, score: 99 }] }) };
  }
};
context.global = context;
vm.createContext(context);
vm.runInContext(finalBlock, context);

function assert(cond, msg) { if (!cond) throw new Error(msg); }
function textoMoeda(valor) { return String(valor || "").replace(/\u00a0/g, " "); }

assert((listeners.document.input || []).length === 1, "um listener input");
assert((listeners.document.change || []).length === 1, "um listener change");
assert((listeners.document.focusin || []).length === 1, "um listener focusin");

context.window.recalcularResumoLances();
assert(rows[0].dataset.status === "MEDBOX VENCE", "linha vencedora inicial");
assert(rows[0].dataset.empresaVencedora === "MEDBOX", "empresa vencedora medbox");
assert(textoMoeda(rows[0].menorValorCell.strong.textContent) === "R$ 18,00", "menor valor vencedor exibido");
assert(kpi("itens_ganhos_medbox").textContent === "1", "ganhos iniciais");
assert(textoMoeda(kpi("total_ganho_medbox").textContent) === "R$ 180,00", "total por menor valor inicial");

const itemManual = { quantidade: 10, medbox_vence: true, menor_valor_vencedor: 7, empresa_vencedora: "MEDBOX", preco_medbox: 9 };
assert(context.window.calcularValorGanhoItem(itemManual) === 70, "total usa menor valor, nao preco medbox");
itemManual.empresa_vencedora = "OUTRA EMPRESA";
assert(context.window.calcularValorGanhoItem(itemManual) === 0, "empresa diferente nao soma");
itemManual.empresa_vencedora = "MEDBOX DISTRIBUIDORA DE MEDICAMENTOS";
assert(context.window.calcularValorGanhoItem(itemManual) === 70, "normaliza nome medbox");

rows[0].fields[".markup-atual-input"].value = "150";
context.window.recalcularResumoLances();
assert(rows[0].dataset.status === "NEGOCIAR", "markup deve virar negociar");
assert(kpi("itens_ganhos_medbox").textContent === "0", "ganhos apos markup");
assert(textoMoeda(kpi("total_ganho_medbox").textContent) === "R$ 0,00", "total apos markup");

rows[0].fields[".markup-atual-input"].value = "80";
rows[0].fields[".custo-manual-input"].value = "R$ 5,00";
context.window.recalcularResumoLances();
assert(textoMoeda(rows[0].fields[".medbox-input"].value) === "R$ 9,00", "custo recalcula preco");
assert(rows[0].dataset.status === "MEDBOX VENCE", "custo menor vence");

rows[0].fields[".osinfo-input"].value = "R$ 8,00";
context.window.recalcularResumoLances();
assert(rows[0].dataset.status === "NEGOCIAR", "osinfo menor muda status");

rows[0].fields[".osinfo-input"].value = "R$ 20,00";
rows[0].fields[".qtd-input"].value = "0";
context.window.recalcularResumoLances();
assert(rows[0].dataset.status === "FORA DA COTAÇÃO", "quantidade zero fora da cotacao");
assert(rows[0].classList.has("linha-fora-cotacao"), "classe neutra fora cotacao");
assert(kpi("total_itens").textContent === "1", "quantidade zero sai do operacional");
assert(kpi("percentual_itens_ganhos").textContent === "0,00%", "percentual com denominador correto");

rows[0].fields[".qtd-input"].value = "10";
context.window.aplicarSugestaoSku(rows[0], { sku_master: "SKU NOVO", categoria: "NOVA", fornecedor_menor_custo: "FORN NOVO", marca_fabricante: "MARCA NOVA", menor_custo_unitario: 4 });
assert(rows[0].fields[".sku-master-input"].value === "SKU NOVO", "sku preenchido");
assert(rows[0].fields[".categoria-input"].value === "CORRELATOS", "categoria manual preservada");
assert(rows[0].fields[".fornecedor-input"].value === "FORN NOVO", "fornecedor atualizado");
assert(rows[0].fields[".fabricante-input"].value === "MARCA NOVA", "marca atualizada");
assert(textoMoeda(rows[0].fields[".medbox-input"].value) === "R$ 7,20", "sku/enriquecimento recalcula preco");
assert(rows[0].strong.textContent === "PRODUTO ORIGINAL", "descricao original preservada");

(async () => {
  await context.window.buscarSugestoesSku(rows[0].fields[".sku-master-input"]);
  assert(fetchCalls === 1, "autocomplete chama endpoint uma vez");
  assert(document.body.children.length === 1, "dropdown criado");
  assert(document.body.children[0].style.display === "block", "dropdown visivel");
  console.log("OK: lances_recalculo_dinamico_test passou");
})().catch((err) => { console.error(err); process.exit(1); });
