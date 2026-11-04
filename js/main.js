/* Fischer Investments — interactions & animated backgrounds */
(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => [...c.querySelectorAll(s)];

  /* ---------- split hero title into letters ---------- */
  $$('[data-split]').forEach(el => {
    const text = el.textContent;
    el.textContent = '';
    [...text].forEach((ch, i) => {
      const s = document.createElement('span');
      s.className = 'ch';
      s.style.setProperty('--i', i);
      s.setAttribute('aria-hidden', 'true');
      s.textContent = ch;
      el.appendChild(s);
    });
  });
  requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.add('is-loaded')));
  const tower = $('.hero__tower');
  if (tower) tower.addEventListener('transitionend', () => { tower.style.transition = 'none'; }, { once: true });

  /* ---------- reveal on scroll ---------- */
  // Clipped (mask) elements report no intersection while fully clipped,
  // so they are triggered by watching their parent instead.
  const targets = new Map();
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      (targets.get(e.target) || []).forEach(el => el.classList.add('is-in'));
      io.unobserve(e.target);
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
  $$('.reveal').forEach(el => {
    const watch = el.classList.contains('reveal--mask') ? el.parentElement : el;
    if (!targets.has(watch)) targets.set(watch, []);
    targets.get(watch).push(el);
    io.observe(watch);
  });

  /* ---------- counters ---------- */
  const countIO = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      countIO.unobserve(e.target);
      $$('[data-count]', e.target).forEach(el => {
        const end = +el.dataset.count, suf = el.dataset.suffix || '';
        if (reduce) { el.textContent = end + suf; return; }
        const t0 = performance.now(), dur = 1600;
        const tick = now => {
          const p = Math.min(1, (now - t0) / dur);
          el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3))) + suf;
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
    });
  }, { threshold: 0.4 });
  $$('.stats').forEach(el => countIO.observe(el));

  /* ---------- nav: scrolled state, active link, mobile menu ---------- */
  const nav = $('.nav');
  const toggle = $('.nav__toggle');
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', open);
    toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
  });
  $$('.nav__links a').forEach(a => a.addEventListener('click', () => {
    nav.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
  }));

  const links = $$('.nav__links a');
  const sectionIO = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      links.forEach(a => a.classList.toggle('is-active', a.getAttribute('href') === '#' + e.target.id));
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  $$('main section[id]').forEach(s => sectionIO.observe(s));

  /* ---------- scroll loop: progress + parallax ---------- */
  const bar = $('.progress span');
  const parallax = $$('[data-parallax]');
  let ticking = false;
  const onScroll = () => {
    const y = window.scrollY;
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    nav.classList.toggle('is-scrolled', y > 20);
    if (!reduce) {
      parallax.forEach(el => {
        const r = el.getBoundingClientRect();
        const offset = Math.max(-40, Math.min(40, (r.top + r.height / 2 - innerHeight / 2) * +el.dataset.parallax));
        if (el.classList.contains('hero__tower')) el.style.setProperty('--py', `${y * +el.dataset.parallax}px`);
        else el.style.transform = `translate3d(0, ${offset}px, 0)`;
      });
    }
    ticking = false;
  };
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  addEventListener('resize', onScroll);
  onScroll();

  /* ---------- custom cursor, tilt, magnetic ---------- */
  if (fine && !reduce) {
    const cur = $('.cursor');
    let mx = -100, my = -100, cx = mx, cy = my;
    addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; cur.classList.add('is-on'); });
    document.addEventListener('mouseleave', () => cur.classList.remove('is-on'));
    const loop = () => {
      cx += (mx - cx) * 0.18; cy += (my - cy) * 0.18;
      cur.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
      requestAnimationFrame(loop);
    };
    loop();
    $$('a, button, [data-tilt]').forEach(el => {
      el.addEventListener('mouseenter', () => cur.classList.add('is-hover'));
      el.addEventListener('mouseleave', () => cur.classList.remove('is-hover'));
    });

    $$('[data-tilt]').forEach(el => {
      el.addEventListener('mousemove', e => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        el.style.transition = 'transform .15s ease-out, clip-path 1.5s cubic-bezier(.2,.7,.1,1)';
        el.style.transform = `perspective(1000px) rotateY(${px * 8}deg) rotateX(${-py * 8}deg)`;
      });
      el.addEventListener('mouseleave', () => {
        el.style.transition = 'transform .8s cubic-bezier(.2,.7,.1,1), clip-path 1.5s cubic-bezier(.2,.7,.1,1)';
        el.style.transform = '';
      });
    });

    $$('[data-magnetic]').forEach(el => {
      el.addEventListener('mousemove', e => {
        const r = el.getBoundingClientRect();
        const x = e.clientX - r.left - r.width / 2;
        const y = e.clientY - r.top - r.height / 2;
        el.style.transform = `translate(${x * 0.25}px, ${y * 0.35}px)`;
      });
      el.addEventListener('mouseleave', () => { el.style.transform = ''; });
    });
  }

  /* ---------- animated canvas backgrounds ---------- */
  const fxs = $$('canvas[data-fx]').map(canvas => {
    const ctx = canvas.getContext('2d');
    const mode = canvas.dataset.fx;
    const st = { w: 0, h: 0, dpr: 1, t: 0, visible: true, mouse: { x: -999, y: -999 }, items: [] };

    const resize = () => {
      st.dpr = Math.min(devicePixelRatio || 1, 2);
      st.w = canvas.clientWidth; st.h = canvas.clientHeight;
      canvas.width = st.w * st.dpr; canvas.height = st.h * st.dpr;
      ctx.setTransform(st.dpr, 0, 0, st.dpr, 0, 0);
      seed();
    };

    const seed = () => {
      st.items = [];
      if (mode === 'blueprint') {
        // drifting construction points that link like a plan
        const n = Math.round(Math.min(70, (st.w * st.h) / 18000));
        for (let i = 0; i < n; i++) st.items.push({
          x: Math.random() * st.w, y: Math.random() * st.h,
          vx: (Math.random() - .5) * .18, vy: (Math.random() - .5) * .18
        });
      } else {
        // rising "growth" lines
        const n = Math.round(st.w / 26);
        for (let i = 0; i < n; i++) st.items.push(newLine(true));
      }
    };
    const newLine = initial => ({
      x: Math.random() * st.w,
      y: initial ? Math.random() * st.h : st.h + Math.random() * 100,
      len: 40 + Math.random() * 160,
      v: .25 + Math.random() * .7,
      a: .05 + Math.random() * .14
    });

    canvas.parentElement.addEventListener('mousemove', e => {
      const r = canvas.getBoundingClientRect();
      st.mouse.x = e.clientX - r.left; st.mouse.y = e.clientY - r.top;
    });
    canvas.parentElement.addEventListener('mouseleave', () => { st.mouse.x = st.mouse.y = -999; });

    const drawBlueprint = () => {
      const { w, h } = st;
      ctx.clearRect(0, 0, w, h);
      // fine architectural grid with slow drift
      const g = 64, off = (st.t * 0.08) % g;
      ctx.strokeStyle = 'rgba(14,58,50,.055)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = -g + off; x < w + g; x += g) { ctx.moveTo(x + .5, 0); ctx.lineTo(x + .5, h); }
      for (let y = -g + off; y < h + g; y += g) { ctx.moveTo(0, y + .5); ctx.lineTo(w, y + .5); }
      ctx.stroke();

      const pts = st.items, m = st.mouse;
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        const dx = p.x - m.x, dy = p.y - m.y, d2 = dx * dx + dy * dy;
        if (d2 < 16000) { const f = (16000 - d2) / 16000 * .6; p.x += dx / Math.sqrt(d2 || 1) * f; p.y += dy / Math.sqrt(d2 || 1) * f; }
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
      }
      // orthogonal links: plans use right angles
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const a = pts[i], b = pts[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 150) {
            ctx.strokeStyle = `rgba(14,58,50,${(1 - d / 150) * .22})`;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      ctx.fillStyle = 'rgba(14,58,50,.45)';
      for (const p of pts) { ctx.fillRect(p.x - 1.5, p.y - 1.5, 3, 3); }
    };

    const drawRise = () => {
      const { w, h } = st;
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < st.items.length; i++) {
        const l = st.items[i];
        l.y -= l.v;
        if (l.y + l.len < 0) st.items[i] = newLine(false);
        const grad = ctx.createLinearGradient(0, l.y, 0, l.y + l.len);
        grad.addColorStop(0, `rgba(241,237,229,${l.a})`);
        grad.addColorStop(1, 'rgba(241,237,229,0)');
        ctx.fillStyle = grad;
        ctx.fillRect(l.x, l.y, 1, l.len);
      }
      // soft light following the pointer
      if (st.mouse.x > -999) {
        const r = ctx.createRadialGradient(st.mouse.x, st.mouse.y, 0, st.mouse.x, st.mouse.y, 320);
        r.addColorStop(0, 'rgba(241,237,229,.08)'); r.addColorStop(1, 'rgba(241,237,229,0)');
        ctx.fillStyle = r; ctx.fillRect(0, 0, w, h);
      }
    };

    const draw = mode === 'blueprint' ? drawBlueprint : drawRise;
    const vis = new IntersectionObserver(([e]) => { st.visible = e.isIntersecting; });
    vis.observe(canvas);
    resize();
    return { st, draw, resize };
  });

  addEventListener('resize', () => fxs.forEach(f => f.resize()));
  if (reduce) { fxs.forEach(f => f.draw()); return; }
  const frame = () => {
    fxs.forEach(f => { if (f.st.visible) { f.st.t++; f.draw(); } });
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();
