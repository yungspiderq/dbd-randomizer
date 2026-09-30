# -*- coding: utf-8 -*-
"""Простыня для ручного заполнения русских названий: HTML с превью всех записей
без RU-имени + готовый CSV.

Зачем
-----
576 записей, которых нет на русской вики, заполняются официальными именами из
русского клиента игры. Искать их вслепую по английскому имени долго, поэтому
скрипт делает «простыню»: плитка на запись — превью 96 px (миниатюра wiki.gg),
персонаж, редкость, дата выхода, английское имя и поле ввода. Заполненное
скачивается кнопкой как CSV в формате `tools/ru_names_missing.py`
(id;name_ru), который затем скармливается ему же.

Запуск:  python tools/ru_names_sheet.py
Результат: tools/skin_names_missing.html (открывается в браузере, сеть нужна
           только для картинок) + tools/skin_names_missing.csv (как и прежде).

HTML самодостаточен по логике (никаких библиотек), картинки грузятся напрямую с
deadbydaylight.wiki.gg — то есть файл можно открыть и на машине без репозитория.
"""
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "skin_names_missing.html")
THUMB = "https://deadbydaylight.wiki.gg/images/thumb/{f}/160px-{f}"
PLACEHOLDER_SVG = (
    "data:image/svg+xml;utf8," +
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='96'%3E"
    "%3Crect width='96' height='96' fill='%231c232c'/%3E"
    "%3Ctext x='48' y='52' fill='%2356606c' font-size='11' "
    "text-anchor='middle' font-family='sans-serif'%3Enet foto%3C/text%3E%3C/svg%3E")


def rows(SK):
    try:
        import skin_names_manual as MAN
        manual = {int(k): str(v) for k, v in (MAN.SKIN_RU or {}).items() if str(v).strip()}
    except ImportError:
        manual = {}
    out = []
    for sid, info in sorted(SK.SKINS_BY_ID.items()):
        if info.get("name_ru") or sid in manual:
            continue
        out.append((sid, info, manual.get(sid, "")))
    out.sort(key=lambda r: (r[1].get("char", ""), 0 if r[1].get("kind") == "coschar" else 1,
                            r[1].get("date") or "9999", r[0]))
    return out


def build_html(data, game_version):
    total = len(data)
    chars = sorted({info["char"] for _sid, info, _v in data})
    cards = []
    for sid, info, value in data:
        f = info.get("file") or ""
        src = THUMB.format(f=f) if f else PLACEHOLDER_SVG
        star = "★ " if info.get("kind") == "coschar" else ""
        meta = " · ".join(x for x in (info.get("char", ""), info.get("rarity_ru", ""),
                                      info.get("date", "")) if x)
        cards.append(
            f'<div class="card" data-char="{html.escape(info.get("char", ""))}" '
            f'data-kind="{html.escape(info.get("kind", ""))}">'
            f'<img loading="lazy" src="{html.escape(src)}" width="96" height="96" '
            f'onerror="this.src=\'{PLACEHOLDER_SVG}\'">'
            f'<div class="t">{star}<b>{html.escape(info.get("name", ""))}</b></div>'
            f'<div class="m">{html.escape(meta)} · id {sid}</div>'
            f'<input type="text" data-id="{sid}" value="{html.escape(value)}" '
            f'placeholder="русское название">'
            f'</div>')
    opts = "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in chars)
    return """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>Русские названия наборов — дозаполнение (%(total)d)</title>
<style>
 body{background:#0e1116;color:#dfe5ea;font:14px/1.45 "Segoe UI",Arial,sans-serif;margin:0}
 header{position:sticky;top:0;background:#151a21;border-bottom:1px solid #2a323d;
        padding:10px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:9}
 header b{color:#e6ebf0}
 select,input[type=search]{background:#0e1116;color:#dfe5ea;border:1px solid #2a323d;
        border-radius:4px;padding:5px 8px;font:inherit}
 button{background:#e5534b;border:0;color:#fff;padding:7px 12px;border-radius:4px;
        font:inherit;cursor:pointer}
 button.sec{background:#1c232c;border:1px solid #2a323d;color:#dfe5ea}
 #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;padding:14px}
 .card{background:#151a21;border:1px solid #2a323d;border-radius:6px;padding:8px;text-align:center}
 .card img{background:#0e1116;border:1px solid #2a323d;border-radius:4px}
 .card .t{font-size:12px;margin:6px 0 2px;min-height:32px}
 .card .m{color:#8d99a6;font-size:11px;margin-bottom:6px}
 .card input{width:100%%;box-sizing:border-box;background:#0e1116;color:#e6ebf0;
        border:1px solid #2a323d;border-radius:4px;padding:5px;font:inherit}
 .card input:focus{border-color:#e5534b;outline:none}
 .card.filled{border-color:#3fb950}
 #stat{color:#8d99a6;font-size:12px}
</style></head><body>
<header>
  <b>Русские названия: %(total)d записей без перевода</b>
  <span id="stat">заполнено 0</span>
  <select id="fchar"><option value="">все персонажи</option>%(opts)s</select>
  <select id="fkind"><option value="">наборы и образы</option>
    <option value="coschar">только ★ скины персонажей</option>
    <option value="outfit">только наборы одежды</option></select>
  <input type="search" id="q" placeholder="поиск по английскому имени">
  <button id="save">⬇ Скачать CSV</button>
  <button class="sec" id="keep">💾 Сохранить в браузере</button>
  <button class="sec" id="load">↺ Загрузить сохранённое</button>
</header>
<div id="grid">%(cards)s</div>
<script>
const KEY="dbd_skin_names_ru";
const inputs=[...document.querySelectorAll(".card input")];
function mark(i){i.closest(".card").classList.toggle("filled", !!i.value.trim());}
function stat(){
  const n=inputs.filter(i=>i.value.trim()).length;
  document.getElementById("stat").textContent="заполнено "+n+" из "+inputs.length;
}
inputs.forEach(i=>{i.addEventListener("input",()=>{mark(i);stat();});mark(i);});
function apply(){
  const c=document.getElementById("fchar").value,
        k=document.getElementById("fkind").value,
        q=document.getElementById("q").value.trim().toLowerCase();
  document.querySelectorAll(".card").forEach(card=>{
    const okC=!c||card.dataset.char===c,
          okK=!k||card.dataset.kind===k,
          okQ=!q||card.querySelector(".t").textContent.toLowerCase().includes(q);
    card.style.display=(okC&&okK&&okQ)?"":"none";
  });
}
["fchar","fkind"].forEach(id=>document.getElementById(id).addEventListener("change",apply));
document.getElementById("q").addEventListener("input",apply);
function collect(){
  const rows=[];
  inputs.forEach(i=>{const v=i.value.trim(); if(v) rows.push([i.dataset.id,v]);});
  return rows;
}
document.getElementById("save").onclick=()=>{
  const rows=collect();
  if(!rows.length){alert("Пока пусто — заполните хотя бы одно поле.");return;}
  const txt="id;name_ru\\n"+rows.map(r=>r[0]+";"+r[1].replace(/;/g,",")).join("\\n")+"\\n";
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob(["\\ufeff"+txt],{type:"text/csv;charset=utf-8"}));
  a.download="skin_names_filled.csv"; a.click();
};
document.getElementById("keep").onclick=()=>{
  const o={}; collect().forEach(([id,v])=>o[id]=v);
  localStorage.setItem(KEY,JSON.stringify(o));
  document.getElementById("stat").textContent="сохранено в браузере: "+Object.keys(o).length;
};
document.getElementById("load").onclick=()=>{
  const o=JSON.parse(localStorage.getItem(KEY)||"{}");
  inputs.forEach(i=>{ if(o[i.dataset.id]!==undefined){i.value=o[i.dataset.id];mark(i);} });
  stat();
};
(function(){const o=JSON.parse(localStorage.getItem(KEY)||"{}");
 inputs.forEach(i=>{ if(o[i.dataset.id]&&!i.value){i.value=o[i.dataset.id];mark(i);} });})();
stat();
</script>
<p style="padding:0 14px 24px;color:#8d99a6;font-size:12px">
 Данные: wiki.gg, патч %(ver)s. Имена берите из русского клиента игры —
 перевод с русской вики для этих записей отсутствует. После заполнения:
 «⬇ Скачать CSV» → положить файл рядом с репозиторием и запустить
 <code>python tools/ru_names_missing.py --merge=skin_names_filled.csv</code>,
 затем <code>python tools/resolve_skins.py</code>.
 Кнопка «💾 Сохранить в браузере» держит прогресс локально, поэтому можно
 заполнять частями и не потерять введённое при перезагрузке страницы.
</p>
</body></html>
""" % {"total": total, "opts": opts, "cards": "\n".join(cards), "ver": html.escape(game_version)}


def main():
    import dbd_skins as SK
    data = rows(SK)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(build_html(data, getattr(SK, "GAME_VERSION", "?")))
    print(f"записей без RU-названия: {len(data)}")
    print(f"Простыня: {OUT} ({os.path.getsize(OUT) // 1024} КБ) — откройте в браузере")
    print("Заполнение: поля ввода -> «💾 Сохранить в браузере» (можно частями) -> "
          "«⬇ Скачать CSV»")
    print("Дальше: python tools/ru_names_missing.py --merge=<файл.csv> && "
          "python tools/resolve_skins.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
