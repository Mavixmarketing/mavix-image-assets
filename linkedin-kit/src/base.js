// Shared by every template. window.D (the post data) is injected before this file.
const LOGO = "M879.02 728.71C864.94 683.9 831.37 645.32 788.76 624.99C778.69 620.19 758.82 613 755.62 613C754.73 613 754 612.55 754 612C754 611.45 754.79 610.99 755.75 610.99C759.36 610.95 781.09 602.97 790.71 598.15C817.77 584.57 841.97 563.18 858.75 538C866.17 526.87 873.64 511.28 878.45 496.94L882.71 484.21L887.02 497.31C904.75 551.05 949.49 594.3 1002.75 609.18C1010.26 611.28 1013.31 613 1009.51 613C1006.39 613 986.06 620.38 976.39 625.02C956.48 634.59 935.26 650.75 920.99 667.21C905.5 685.07 894.39 704.6 886.87 727.19C884.62 733.96 882.71 739.57 882.64 739.65C882.56 739.73 880.93 734.81 879.02 728.71ZM1 306.5L1 1L90.84 1L180.67 1L241.5 114.25C274.96 176.54 347.52 311.65 402.74 414.5C457.97 517.35 504.47 603.86 506.09 606.75L509.02 612L413.7 612L318.39 612L267.95 512.25L217.5 412.5L194.25 412.23L171 411.96L171 511.98L171 612L86 612L1 612L1 306.5ZM724.58 558.25C723.78 556.74 705.8 523.33 684.64 484L646.17 412.5L623.09 412.23L600 411.96L599.98 471.73C599.95 538.96 600.19 536.7 592.44 542.62L588.66 545.5L564.07 545.8L539.47 546.09L484.74 444.21L430 342.33L430 171.66L430 1L520.39 1L610.77 1L652.29 78.25C675.12 120.74 726.29 216 766.01 289.94L838.22 424.39L837.54 432.44C833.38 481.52 803.39 525.97 758.95 548.94C748.54 554.32 731.09 561 727.44 561C726.67 561 725.39 559.76 724.58 558.25Z";
const ACCTS = {
  farhan: {name: "Mohd Farhan", role: "Founder, Mavix Marketing", img: "farhan.jpg", light: "#005AFF", dark: "#4D8BFF", onDark: "#101010"},
  nasir:  {name: "Nasir Ahmad", role: "Co-founder, Mavix Marketing", img: "nasir.jpg", light: "#0A7C42", dark: "#B4FF24", onDark: "#101010"},
};
window.__overflow = [];
const A = ACCTS[D.acct];
const THEME = D.theme || (D.acct === "farhan" ? "light" : "dark");
const ACC = THEME === "light" ? A.light : A.dark;
document.documentElement.classList.add(THEME);
document.documentElement.style.setProperty("--a", ACC);
document.documentElement.style.setProperty("--on-a", THEME === "light" ? "#FFFFFF" : A.onDark);

const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
// *phrase* -> lime highlighter, _phrase_ -> accent colour, ~phrase~ -> Playfair italic
const rich = s => esc(s).replace(/\*(.+?)\*/g, '<span class="hl">$1</span>')
  .replace(/_(.+?)_/g, '<span class="acc-t">$1</span>').replace(/~(.+?)~/g, '<span class="it">$1</span>');
const lockup = () => `<div class="lockup"><svg class="mark" viewBox="0 0 1013 741" aria-hidden="true"><path fill="${ACC}" fill-rule="evenodd" d="${LOGO}"/></svg><div class="wm"><span class="mvx-n">Mavix</span><span class="mvx-s">marketing</span></div></div>`;
const author = () => `<div class="author"><img src="${A.img}"><div><div class="n">${A.name}</div><div class="r">${A.role}</div></div></div>`;
const outline = s => { const h = rich(s); return `<span class="oh"><span class="oh__ghost" aria-hidden="true">${h}</span><span class="oh__solid">${h}</span></span>`; };

// Shrink text until it fits its box. If it still does not fit at the floor, flag it.
function fit(el, max, min, name) {
  let s = max; el.style.fontSize = s + "px";
  const mh = parseFloat(getComputedStyle(el).maxHeight) || 0;
  const c = el.hasAttribute("data-child") ? (el.querySelector(".oh__solid") || el.firstElementChild) : null;
  const wonly = el.hasAttribute("data-wonly");
  const over = () => wonly ? el.scrollWidth > el.clientWidth + 2 : c ? (c.offsetHeight > el.clientHeight + 2 || c.scrollWidth > c.clientWidth + 2 || el.scrollWidth > el.clientWidth + 8)
                       : (el.scrollHeight > (mh || el.clientHeight) + 8 || el.scrollWidth > el.clientWidth + 2);
  while (over() && s > min) { s -= 2; el.style.fontSize = s + "px"; }
  if (over()) window.__overflow.push(`${name || el.id}: too long even at ${min}px, shorten it`);
  return s;
}
function need(keys) { for (const k of keys) if (D[k] === undefined || D[k] === "") window.__overflow.push(`missing field: ${k}`); }
window.__ready = document.fonts.ready;
