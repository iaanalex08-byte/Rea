// Lumen: plataforma de streaming de ejemplo (SPA sin dependencias, rutas por hash).
const $ = (sel, root = document) => root.querySelector(sel);
const app = $("#app");
const byId = Object.fromEntries(TITLES.map((t) => [t.id, t]));

const PROFILES = [
  { id: "p1", name: "Tú", hue: 40 },
  { id: "p2", name: "Familia", hue: 170 },
  { id: "p3", name: "Niños", hue: 300 },
];

// ---------- Almacenamiento local (por perfil) ----------
const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* sin almacenamiento */ }
  },
};
const profile = () => PROFILES.find((p) => p.id === store.get("lumen.profile", null));
const key = (name) => `lumen.${profile()?.id ?? "anon"}.${name}`;
const myList = () => store.get(key("list"), []);
const inList = (id) => myList().includes(id);
const toggleList = (id) => {
  const list = myList();
  const next = list.includes(id) ? list.filter((x) => x !== id) : [id, ...list];
  store.set(key("list"), next);
  toast(next.includes(id) ? "Agregado a Mi lista" : "Quitado de Mi lista");
  return next.includes(id);
};
const progress = () => store.get(key("progress"), {});
const saveProgress = (id, ratio) => store.set(key("progress"), { ...progress(), [id]: ratio });

// ---------- Utilidades ----------
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const art = (t, extra = "") => `<div class="art ${extra}" style="--h:${t.hue}"></div>`;
const match = (t) => 80 + ((t.id.length * 7 + t.year) % 19);
const length = (t) => (t.type === "Serie" ? `${t.seasons} temporada${t.seasons > 1 ? "s" : ""}` : t.duration);
const metaLine = (t) => `
  <div class="meta">
    <span class="match">${match(t)}% para ti</span>
    <span>${t.year}</span><span class="badge">${t.rating}</span><span>${length(t)}</span>
  </div>`;

function toast(msg) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  document.body.append(el);
  setTimeout(() => el.remove(), 1800);
}

// ---------- Barra superior ----------
function renderTopbar(route) {
  const logged = !!profile();
  $("#nav").hidden = !logged;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", "#" + route === a.getAttribute("href")));
  const actions = $("#top-actions");
  if (!logged) {
    actions.innerHTML = route === "/" ? `<a class="btn btn-primary" href="#/profiles">Iniciar sesión</a>` : "";
    return;
  }
  const p = profile();
  const q = route.startsWith("/search/") ? decodeURIComponent(route.slice(8)) : "";
  actions.innerHTML = `
    <input class="search" id="search" type="search" placeholder="Buscar títulos, géneros" value="${esc(q)}" />
    <a href="#/profiles" title="Cambiar perfil"><span class="avatar" style="background:hsl(${p.hue} 60% 45%)">${esc(p.name[0])}</span></a>`;
  const input = $("#search");
  input.addEventListener("input", () => {
    const v = input.value.trim();
    location.hash = v ? `#/search/${encodeURIComponent(v)}` : "#/browse";
  });
  if (q) { input.focus(); input.setSelectionRange(q.length, q.length); }
}

// ---------- Vistas ----------
function viewLanding() {
  app.innerHTML = `
    <section class="landing">
      <div>
        <h1>Historias que iluminan<br/>tus noches.</h1>
        <p>Series, películas y documentales originales. Cancela cuando quieras.</p>
        <form class="signup" id="signup">
          <input type="email" required placeholder="Correo electrónico" aria-label="Correo electrónico" />
          <button class="btn btn-primary" type="submit">Comenzar ›</button>
        </form>
        <div class="features">
          <div class="feature"><h3>En cualquier pantalla</h3><p class="muted">Tele, compu, tablet o celular.</p></div>
          <div class="feature"><h3>Perfiles</h3><p>Cada quien con su lista y su progreso.</p></div>
          <div class="feature"><h3>Sigue viendo</h3><p>Retoma justo donde te quedaste.</p></div>
        </div>
      </div>
    </section>`;
  $("#signup").addEventListener("submit", (e) => { e.preventDefault(); location.hash = "#/profiles"; });
}

function viewProfiles() {
  app.innerHTML = `
    <section class="profiles">
      <h1>¿Quién está viendo?</h1>
      <div class="profile-list">
        ${PROFILES.map((p) => `
          <button class="profile" data-id="${p.id}">
            <span class="avatar" style="background:hsl(${p.hue} 60% 45%)">${esc(p.name[0])}</span>${esc(p.name)}
          </button>`).join("")}
      </div>
    </section>`;
  app.querySelectorAll(".profile").forEach((b) =>
    b.addEventListener("click", () => { store.set("lumen.profile", b.dataset.id); location.hash = "#/browse"; }));
}

const card = (t) => {
  const p = progress()[t.id];
  return `<div class="card" tabindex="0" data-open="${t.id}" aria-label="${esc(t.title)}">
      ${art(t)}<div class="label">${esc(t.title)}</div>
      ${p ? `<div class="progress" style="width:${Math.round(p * 100)}%"></div>` : ""}
    </div>`;
};

const row = (name, items) => items.length ? `
  <section class="row">
    <h2>${esc(name)}</h2>
    <div class="row-wrap">
      <button class="arrow left" aria-label="Anterior">‹</button>
      <div class="row-track">${items.map(card).join("")}</div>
      <button class="arrow right" aria-label="Siguiente">›</button>
    </div>
  </section>` : "";

function viewBrowse(type) {
  const pool = type ? TITLES.filter((t) => t.type === type) : TITLES;
  const featured = pool[new Date().getDate() % pool.length];
  const prog = progress();
  const rows = [
    row("Seguir viendo", Object.keys(prog).filter((id) => prog[id] < 0.97 && byId[id]).map((id) => byId[id])),
    row("Mi lista", myList().map((id) => byId[id]).filter(Boolean)),
    ...ROWS.map((r) => row(r.name, (r.ids ? r.ids.map((id) => byId[id]) : TITLES.filter(r.filter)).filter((t) => pool.includes(t)))),
  ];
  app.innerHTML = `
    <section class="hero">
      ${art(featured, "hero-art")}
      <div class="hero-content">
        <h1>${esc(featured.title)}</h1>
        ${metaLine(featured)}
        <p>${esc(featured.synopsis)}</p>
        <div class="actions">
          <a class="btn btn-primary" href="#/watch/${featured.id}">▶ Reproducir</a>
          <button class="btn btn-ghost" data-open="${featured.id}">ⓘ Más información</button>
        </div>
      </div>
    </section>
    <div class="rows">${rows.join("")}</div>`;
}

function viewGrid(heading, items, emptyMsg) {
  app.innerHTML = `
    <div class="page-top">
      <section class="row"><h2>${esc(heading)}</h2></section>
      ${items.length ? `<div class="grid">${items.map(card).join("")}</div>` : `<p class="empty">${esc(emptyMsg)}</p>`}
    </div>`;
}

function viewSearch(q) {
  const n = q.toLowerCase();
  const items = TITLES.filter((t) => [t.title, t.synopsis, t.type, ...t.genres].join(" ").toLowerCase().includes(n));
  viewGrid(`Resultados para “${q}”`, items, "No encontramos nada. Prueba con otro título o género.");
}

function viewWatch(id) {
  const t = byId[id];
  if (!t) return (location.hash = "#/browse");
  const v = VIDEOS[t.video];
  app.innerHTML = `
    <section class="player">
      <video id="video" src="${v.src}" controls autoplay playsinline></video>
      <div class="player-top">
        <button class="btn-round" id="back" aria-label="Volver">←</button>
        <strong>${esc(t.title)}</strong>
      </div>
      <div class="player-credit">Video de muestra: ${esc(v.credit)}</div>
    </section>`;
  const video = $("#video");
  video.addEventListener("loadedmetadata", () => {
    const p = progress()[id];
    if (p && p < 0.97) video.currentTime = p * video.duration;
  });
  video.addEventListener("timeupdate", () => {
    if (video.duration) saveProgress(id, video.currentTime / video.duration);
  });
  $("#back").addEventListener("click", () => history.back());
}

// ---------- Ventana de detalle ----------
function openModal(id) {
  const t = byId[id];
  if (!t) return;
  const episodes = t.type === "Serie"
    ? `<div class="episodes"><h3>Episodios · Temporada 1</h3>${[1, 2, 3, 4, 5].map((n) => `
        <div class="episode" data-play="${t.id}">
          <span class="n">${n}</span>
          ${art({ ...t, hue: t.hue + n * 12 })}
          <div><strong>Capítulo ${n}</strong><div class="meta">${40 + ((n * 7) % 15)} min</div></div>
        </div>`).join("")}</div>`
    : "";
  $("#modal-card").innerHTML = `
    <div class="modal-hero">
      ${art(t, "hero-art")}
      <button class="btn-round modal-close" data-close aria-label="Cerrar">✕</button>
      <div class="hero-content">
        <h2>${esc(t.title)}</h2>
        <div class="actions">
          <a class="btn btn-primary" href="#/watch/${t.id}">▶ Reproducir</a>
          <button class="btn-round" id="toggle-list" aria-label="Mi lista">${inList(t.id) ? "✓" : "+"}</button>
        </div>
      </div>
    </div>
    <div class="modal-body">
      <div>${metaLine(t)}<p>${esc(t.synopsis)}</p></div>
      <div class="side">
        <div>Géneros: <b>${t.genres.map(esc).join(", ")}</b></div>
        <div>Tipo: <b>${t.type}</b></div>
      </div>
      ${episodes}
    </div>`;
  $("#modal").hidden = false;
  document.body.style.overflow = "hidden";
  $("#toggle-list").addEventListener("click", (e) => { e.currentTarget.textContent = toggleList(t.id) ? "✓" : "+"; });
}
function closeModal() {
  $("#modal").hidden = true;
  document.body.style.overflow = "";
}

// ---------- Eventos globales ----------
document.addEventListener("click", (e) => {
  const open = e.target.closest("[data-open]");
  if (open) return openModal(open.dataset.open);
  const play = e.target.closest("[data-play]");
  if (play) { closeModal(); location.hash = `#/watch/${play.dataset.play}`; return; }
  if (e.target.closest("[data-close]")) return closeModal();
  const arrow = e.target.closest(".arrow");
  if (arrow) {
    const track = arrow.parentElement.querySelector(".row-track");
    track.scrollBy({ left: (arrow.classList.contains("left") ? -1 : 1) * track.clientWidth * 0.85 });
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
  if (e.key === "Enter" && e.target.matches(".card")) openModal(e.target.dataset.open);
});
window.addEventListener("scroll", () => $("#topbar").classList.toggle("solid", scrollY > 40));

// ---------- Rutas ----------
function router() {
  closeModal();
  const route = decodeURIComponent(location.hash.slice(1) || "/");
  const needsProfile = !["/", "/profiles"].includes(route);
  if (needsProfile && !profile()) return (location.hash = "#/profiles");
  if (route === "/" && profile()) return (location.hash = "#/browse");

  $("#topbar").hidden = route.startsWith("/watch/");
  renderTopbar(route);
  scrollTo(0, 0);

  if (route === "/") viewLanding();
  else if (route === "/profiles") viewProfiles();
  else if (route === "/browse") viewBrowse();
  else if (route.startsWith("/browse/")) viewBrowse(route.slice(8));
  else if (route === "/mylist") viewGrid("Mi lista", myList().map((id) => byId[id]).filter(Boolean), "Aún no agregas nada. Usa el botón + en cualquier título.");
  else if (route.startsWith("/search/")) viewSearch(route.slice(8));
  else if (route.startsWith("/watch/")) viewWatch(route.slice(7));
  else location.hash = "#/browse";
}
window.addEventListener("hashchange", router);
router();
