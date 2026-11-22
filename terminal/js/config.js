// Terminal configuration.
//
// OPTIONS_API: URL of your options proxy (the Cloudflare Worker in terminal/worker/), for example
// 'https://orbe-options.tu-cuenta.workers.dev'. Empty = the gamma map and volatility use the
// simulator. The proxy keeps the provider key private; never put an API key in this file.
export const OPTIONS_API = '';

// A different proxy can be tried in one browser without editing this file:
//   localStorage.setItem('orbe.optionsApi', 'https://...')   (empty string to go back)
export function optionsApi() {
  try {
    const v = localStorage.getItem('orbe.optionsApi');
    if (v != null) return v.trim();
  } catch { /* storage blocked */ }
  return OPTIONS_API;
}
