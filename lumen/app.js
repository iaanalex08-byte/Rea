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
let searchQuery = "";
function renderTopbar(route) {
  const logged = !!profile();
  $("#nav").hidden = !logged;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", "#" + route === a.getAttribute("href")));
  const actions = $("#top-actions");
  if (!logged) {
    actions.innerHTML = route === "" ? `<a class="btn btn-primary" href="#profiles">Iniciar sesión</a>` : "";
    return;
  }
  const p = profile();
  const q = route === "search" ? searchQuery : "";
  actions.innerHTML = `
    <input class="search" id="search" type="search" placeholder="Buscar títulos, géneros" aria-label="Buscar" value="${esc(q)}" />
    <a href="#profiles" title="Cambiar perfil"><span class="avatar" style="background:hsl(${p.hue} 60% 45%)">${esc(p.name[0])}</span></a>`;
  const input = $("#search");
  input.addEventListener("input", () => {
    searchQuery = input.value.trim();
    if (!searchQuery) { location.hash = "#browse"; return; }
    if (location.hash !== "#search") location.hash = "#search";
    else viewSearch(searchQuery);
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
  $("#signup").addEventListener("submit", (e) => { e.preventDefault(); location.hash = "#profiles"; });
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
    b.addEventListener("click", () => { store.set("lumen.profile", b.dataset.id); location.hash = "#browse"; }));
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
          <a class="btn btn-primary" href="#watch-${featured.id}">▶ Reproducir</a>
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
  if (!t) return (location.hash = "#browse");
  if (window.LUMEN_SIMULATED_PLAYER) return viewSimulatedPlayer(t);
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

// Reproductor simulado: se usa donde no se pueden cargar videos externos.
// Dibuja una escena animada original en canvas y se comporta como un video
// (reproducir/pausar, barra de avance, saltos de 10 s y avance guardado).
function viewSimulatedPlayer(t) {
  const DURATION = 180; // segundos simulados
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  app.innerHTML = `
    <section class="player sim">
      <canvas id="screen"></canvas>
      <div class="player-top">
        <button class="btn-round" id="back" aria-label="Volver">←</button>
        <strong>${esc(t.title)}</strong>
      </div>
      <div class="sim-controls">
        <button class="btn-round" id="rew" aria-label="Retroceder 10 segundos">↺</button>
        <button class="btn-round sim-play" id="play" aria-label="Pausar">❚❚</button>
        <button class="btn-round" id="fwd" aria-label="Adelantar 10 segundos">↻</button>
        <input type="range" id="seek" min="0" max="${DURATION}" step="0.1" value="0" aria-label="Posición" />
        <span class="sim-time" id="time">0:00 / ${fmt(DURATION)}</span>
      </div>
      <div class="player-credit">Vista previa animada · demostración</div>
    </section>`;
  const canvas = $("#screen"), ctx = canvas.getContext("2d");
  const seek = $("#seek"), playBtn = $("#play"), timeEl = $("#time");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let pos = (progress()[t.id] ?? 0) < 0.97 ? (progress()[t.id] ?? 0) * DURATION : 0;
  let playing = true, last = performance.now(), raf;

  const resize = () => { canvas.width = innerWidth * devicePixelRatio; canvas.height = innerHeight * devicePixelRatio; };
  resize();
  addEventListener("resize", resize);

  // Estrellas/partículas deterministas por título
  let seed = [...t.id].reduce((a, c) => a + c.charCodeAt(0), 0);
  const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
  const dots = Array.from({ length: 90 }, () => ({ x: rnd(), y: rnd(), r: rnd() * 2 + 0.5, s: rnd() * 0.6 + 0.2 }));

  function draw() {
    const w = canvas.width, h = canvas.height, k = pos / DURATION, time = pos;
    const hue = t.hue + Math.sin(time / 20) * 25;
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, `hsl(${hue - 30} 50% 8%)`);
    g.addColorStop(1, `hsl(${hue} 60% ${18 + k * 10}%)`);
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    // Sol / luna que cruza la escena
    const sx = w * (0.15 + 0.7 * k), sy = h * (0.55 - Math.sin(k * Math.PI) * 0.35);
    const sun = ctx.createRadialGradient(sx, sy, 0, sx, sy, h * 0.35);
    sun.addColorStop(0, `hsla(${hue + 40} 90% 70% / .95)`); sun.addColorStop(1, "transparent");
    ctx.fillStyle = sun; ctx.fillRect(0, 0, w, h);
    // Partículas
    for (const d of dots) {
      const x = ((d.x + time * d.s * 0.01) % 1) * w, y = (d.y + Math.sin(time * d.s + d.x * 9) * 0.01) * h;
      ctx.fillStyle = `hsla(${hue + 60} 80% 85% / ${0.3 + d.s * 0.6})`;
      ctx.beginPath(); ctx.arc(x, y, d.r * devicePixelRatio, 0, Math.PI * 2); ctx.fill();
    }
    // Montañas en capas (parallax)
    for (let layer = 0; layer < 3; layer++) {
      ctx.fillStyle = `hsl(${hue - 10 + layer * 8} 40% ${6 + layer * 5}%)`;
      ctx.beginPath(); ctx.moveTo(0, h);
      for (let x = 0; x <= w; x += w / 60) {
        const n = x / w * (3 + layer) + time * 0.02 * (layer + 1);
        ctx.lineTo(x, h * (0.62 + layer * 0.1) - Math.sin(n * 2.1) * h * 0.06 - Math.sin(n * 5.3) * h * 0.025);
      }
      ctx.lineTo(w, h); ctx.fill();
    }
  }
  function tick(now) {
    if (!document.body.contains(canvas)) { removeEventListener("resize", resize); return; }
    const dt = (now - last) / 1000; last = now;
    if (playing) {
      pos = Math.min(DURATION, pos + (reduce ? dt * 0.5 : dt));
      if (pos >= DURATION) setPlaying(false);
    }
    seek.value = pos;
    timeEl.textContent = `${fmt(pos)} / ${fmt(DURATION)}`;
    saveProgress(t.id, pos / DURATION);
    draw();
    raf = requestAnimationFrame(tick);
  }
  function setPlaying(v) {
    playing = v;
    playBtn.textContent = v ? "❚❚" : "▶";
    playBtn.setAttribute("aria-label", v ? "Pausar" : "Reproducir");
  }
  playBtn.addEventListener("click", () => { if (pos >= DURATION) pos = 0; setPlaying(!playing); });
  $("#rew").addEventListener("click", () => (pos = Math.max(0, pos - 10)));
  $("#fwd").addEventListener("click", () => (pos = Math.min(DURATION, pos + 10)));
  seek.addEventListener("input", () => (pos = Number(seek.value)));
  $("#back").addEventListener("click", () => { cancelAnimationFrame(raf); location.hash = "#browse"; });
  raf = requestAnimationFrame(tick);
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
          <a class="btn btn-primary" href="#watch-${t.id}">▶ Reproducir</a>
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
  if (play) { closeModal(); location.hash = `#watch-${play.dataset.play}`; return; }
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
const TYPE_ROUTES = { series: "Serie", peliculas: "Película", documentales: "Documental" };
function router() {
  closeModal();
  const route = location.hash.slice(1);
  const needsProfile = !["", "profiles"].includes(route);
  if (needsProfile && !profile()) return (location.hash = "#profiles");
  if (route === "" && profile()) return (location.hash = "#browse");

  $("#topbar").hidden = route.startsWith("watch-");
  renderTopbar(route);
  scrollTo(0, 0);

  if (route === "") viewLanding();
  else if (route === "profiles") viewProfiles();
  else if (route === "browse") viewBrowse();
  else if (TYPE_ROUTES[route]) viewBrowse(TYPE_ROUTES[route]);
  else if (route === "mylist") viewGrid("Mi lista", myList().map((id) => byId[id]).filter(Boolean), "Aún no agregas nada. Usa el botón + en cualquier título.");
  else if (route === "search" && searchQuery) viewSearch(searchQuery);
  else if (route.startsWith("watch-")) viewWatch(route.slice(6));
  else location.hash = "#browse";
}
window.addEventListener("hashchange", router);
router();
