// Barcode scanning with the phone camera. Uses the browser's native BarcodeDetector where it
// exists (Chrome on Android) and the ZXing library elsewhere (iPhone Safari, Firefox).

const ZXING = 'https://unpkg.com/@zxing/library@0.21.3/umd/index.min.js';
let zxingLoading;
function loadZxing() {
  if (window.ZXing) return Promise.resolve(window.ZXing);
  zxingLoading ??= new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = ZXING;
    s.onload = () => res(window.ZXing);
    s.onerror = () => { zxingLoading = null; s.remove(); rej(new Error('No se pudo cargar el lector de códigos')); };
    document.head.append(s);
  });
  return zxingLoading;
}

async function makeDetector() {
  if ('BarcodeDetector' in window) {
    try {
      const formats = await window.BarcodeDetector.getSupportedFormats();
      const want = ['ean_13', 'ean_8', 'upc_a', 'upc_e'].filter((f) => formats.includes(f));
      if (want.length) {
        const d = new window.BarcodeDetector({ formats: want });
        return async (video) => (await d.detect(video))[0]?.rawValue ?? null;
      }
    } catch { /* fall back to ZXing */ }
  }
  const Z = await loadZxing();
  const hints = new Map();
  hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.EAN_8, Z.BarcodeFormat.UPC_A, Z.BarcodeFormat.UPC_E]);
  hints.set(Z.DecodeHintType.TRY_HARDER, true);
  const reader = new Z.MultiFormatReader();
  reader.setHints(hints);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  return async (video) => {
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return null;
    canvas.width = w; canvas.height = h;
    ctx.drawImage(video, 0, 0, w, h);
    try {
      const bmp = new Z.BinaryBitmap(new Z.HybridBinarizer(new Z.HTMLCanvasElementLuminanceSource(canvas)));
      return reader.decode(bmp).getText();
    } catch { return null; } // NotFoundException on frames without a code
  };
}

// Opens a full-screen camera view; resolves with the code, or null if the user closes it.
export function scanBarcode() {
  return new Promise((resolve) => {
    // A modal <dialog> so it sits above whichever sheet is open (modal sheets make the rest inert).
    const el = document.createElement('dialog');
    el.className = 'scanner';
    el.setAttribute('aria-label', 'Escanear código de barras');
    el.innerHTML = `
      <video playsinline muted></video>
      <div class="scan-frame" aria-hidden="true"></div>
      <p class="scan-msg">Apunta al código de barras del empaque</p>
      <form class="scan-manual"><input inputmode="numeric" pattern="[0-9]*" placeholder="o escribe el número" aria-label="Número del código de barras"><button>Buscar</button></form>
      <button class="scan-close" aria-label="Cerrar">✕</button>`;
    document.body.append(el);
    el.showModal();
    const video = el.querySelector('video');
    const msg = el.querySelector('.scan-msg');
    let stream = null, done = false, timer;

    const finish = (code) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
      if (el.open) el.close();
      el.remove();
      resolve(code);
    };
    el.querySelector('.scan-close').onclick = () => finish(null);
    el.addEventListener('cancel', (e) => { e.preventDefault(); finish(null); });
    el.querySelector('.scan-manual').onsubmit = (e) => {
      e.preventDefault();
      const v = e.target.querySelector('input').value.replace(/\D/g, '');
      if (v.length >= 8) finish(v);
    };

    (async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('Este navegador no permite usar la cámara aquí');
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 } }, audio: false });
        if (done) { stream.getTracks().forEach((t) => t.stop()); return; }
        video.srcObject = stream;
        await video.play();
        const detect = await makeDetector();
        const loop = async () => {
          if (done) return;
          const code = await detect(video).catch(() => null);
          if (code) { navigator.vibrate?.(60); finish(code); return; }
          timer = setTimeout(loop, 200);
        };
        loop();
      } catch (e) {
        const why = e.name === 'NotAllowedError' ? 'Sin permiso para usar la cámara.'
          : e.name === 'NotFoundError' ? 'No se encontró una cámara.'
          : e.message;
        msg.textContent = why + ' Puedes escribir el número abajo.';
      }
    })();
  });
}
