// ModeloB — Modelo B "Más dinero" para NinjaTrader 8 (ES / MES, gráfico de 1 minuto).
//
// Reglas (backtest con ES real 2024 – nov 2026: PF 1.72, 55 % ganadoras, positivo los 3 años):
//   1. Hora: 10:12 Nueva York (9:12 CDMX en invierno, 8:12 CDMX en el horario de verano de EE. UU.).
//   2. Dirección: precio arriba de la EMA 20 de 3 minutos = compra; abajo = venta.
//   3. A: el precio está FUERA del área de valor (70 %) del perfil de VOLUMEN de ayer (9:30–16:00 NY).
//   4. C: el perfil de volumen de hoy (9:30 NY hasta la entrada) NO tiene forma P si compras ni b si vendes
//         (POC en el 38 % de arriba del rango = P; en el 38 % de abajo = b).
//   5. Sin BOS en contra: en la última hora no hubo un BOS de 3 minutos en contra (swing de 2 velas a cada lado).
//   6. VWAP: precio arriba del VWAP de la sesión para comprar, abajo para vender.
//   Bracket: SL 30 ticks, TP1 40 ticks (mitad), TP2 160 ticks (otra mitad), sin break-even, cierre 15:59 NY.
//   Tamaño sugerido: 8 MES en la evaluación Lucid 50K, 6 MES ya fondeado.
//
// Uso: NinjaScript Editor -> Indicators -> New Indicator -> nombre "ModeloB" -> borrar todo, pegar este archivo -> F5.
// Gráfico de ES o MES en 1 Minute (tipo Minute) con al menos 5 días cargados. Agregar el indicador ModeloB.
// Dibuja: área de valor y POC de ayer, VWAP, EMA 20 de 3 min, la tabla de chequeos, la señal de las 10:12 NY
// con SL / TP1 / TP2, y el resultado al cerrar. Lanza una alerta con sonido a la hora de la señal.
// Solo dibuja y avisa: no envía órdenes.

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
	public class ModeloB : Indicator
	{
		private class Perfil
		{
			public Dictionary<int, double> V = new Dictionary<int, double>();
			public int Velas;
		}

		private class Evento
		{
			public DateTime T;
			public int Dir;
			public bool Bos;
		}

		private TimeZoneInfo tzNT, tzNY;
		private Perfil hoy, ayerPerfil;
		private DateTime fechaRTH = DateTime.MinValue;
		private double yPoc = double.NaN, yVah = double.NaN, yVal = double.NaN;
		private double sumPV, sumV;
		// velas de 3 minutos armadas con las de 1 minuto
		private readonly List<double> h3 = new List<double>(), l3 = new List<double>(), c3 = new List<double>();
		private readonly List<DateTime> t3 = new List<DateTime>();
		private double aggH = double.MinValue, aggL = double.MaxValue;
		private double ema3 = double.NaN;
		private double swH = double.NaN, swL = double.NaN;
		private int tendencia;
		private readonly List<Evento> eventos = new List<Evento>();
		// estado del día
		private DateTime diaEvaluado = DateTime.MinValue;
		private int lado;
		private bool enTrade, leg1, leg2;
		private double entrada, sl, tp1, tp2, r1, r2;
		private int barraEntrada;
		private string panel = "";

		[Range(0, 23), Display(Name = "Hora de entrada (NY)", Order = 1, GroupName = "1. Reglas")]
		public int HoraNY { get; set; }
		[Range(0, 59), Display(Name = "Minuto de entrada (NY)", Order = 2, GroupName = "1. Reglas")]
		public int MinutoNY { get; set; }
		[Range(1, 1000), Display(Name = "SL (ticks)", Order = 3, GroupName = "1. Reglas")]
		public int SlTicks { get; set; }
		[Range(1, 1000), Display(Name = "TP1 (ticks, mitad)", Order = 4, GroupName = "1. Reglas")]
		public int Tp1Ticks { get; set; }
		[Range(1, 2000), Display(Name = "TP2 (ticks, otra mitad)", Order = 5, GroupName = "1. Reglas")]
		public int Tp2Ticks { get; set; }
		[Display(Name = "Mover a break-even tras TP1", Order = 6, GroupName = "1. Reglas")]
		public bool BreakEven { get; set; }
		[Range(1, 240), Display(Name = "Minutos hacia atrás para BOS en contra", Order = 7, GroupName = "1. Reglas")]
		public int MinutosBos { get; set; }
		[Range(1, 5), Display(Name = "Velas a cada lado del swing", Order = 8, GroupName = "1. Reglas")]
		public int Fuerza { get; set; }
		[Range(0.25, 20), Display(Name = "Tamaño de nivel del perfil (pts)", Order = 9, GroupName = "1. Reglas")]
		public double NivelPts { get; set; }
		[Range(50, 95), Display(Name = "Área de valor (%)", Order = 10, GroupName = "1. Reglas")]
		public int AreaValor { get; set; }
		[Range(1, 100), Display(Name = "Contratos (para el resultado en $)", Order = 1, GroupName = "2. Resultado")]
		public int Contratos { get; set; }
		[Display(Name = "$ por tick por contrato (MES 1.25, ES 12.5)", Order = 2, GroupName = "2. Resultado")]
		public double ValorTick { get; set; }
		[Display(Name = "Costo por contrato ($, ida y vuelta + deslizamiento)", Order = 3, GroupName = "2. Resultado")]
		public double Costo { get; set; }
		[Display(Name = "Alerta con sonido", Order = 1, GroupName = "3. Vista")]
		public bool Alertar { get; set; }

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Name = "ModeloB";
				Description = "Modelo B (10:12 NY, EMA 20 de 3 min, perfil de volumen A + C, sin BOS en contra, VWAP) con SL/TP";
				Calculate = Calculate.OnBarClose;
				IsOverlay = true;
				DrawOnPricePanel = true;
				IsSuspendedWhileInactive = false;
				HoraNY = 10; MinutoNY = 12;
				SlTicks = 30; Tp1Ticks = 40; Tp2Ticks = 160; BreakEven = false;
				MinutosBos = 60; Fuerza = 2; NivelPts = 1.0; AreaValor = 70;
				Contratos = 8; ValorTick = 1.25; Costo = 2.49;
				Alertar = true;
				AddPlot(new Stroke(Brushes.SteelBlue, DashStyleHelper.Dash, 1), PlotStyle.Line, "VAH ayer");
				AddPlot(new Stroke(Brushes.SteelBlue, DashStyleHelper.Dash, 1), PlotStyle.Line, "VAL ayer");
				AddPlot(new Stroke(Brushes.Goldenrod, 2), PlotStyle.Line, "POC ayer");
				AddPlot(new Stroke(Brushes.MediumOrchid, 2), PlotStyle.Line, "VWAP");
				AddPlot(new Stroke(Brushes.Orange, 1), PlotStyle.Line, "EMA 20 (3 min)");
			}
			else if (State == State.DataLoaded)
			{
				tzNT = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
				tzNY = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
				hoy = new Perfil();
			}
		}

		private int Nivel(double p) { return (int)Math.Floor(p / NivelPts + 1e-9); }

		private void Agregar(Perfil p, double lo, double hi, double vol)
		{
			int a = Nivel(lo), z = Nivel(hi);
			double parte = vol / (z - a + 1);
			for (int i = a; i <= z; i++)
			{
				double x;
				p.V.TryGetValue(i, out x);
				p.V[i] = x + parte;
			}
			p.Velas++;
		}

		// POC, VAH, VAL y posición del POC dentro del rango (0 = abajo, 1 = arriba)
		private bool Niveles(Perfil p, out double poc, out double vah, out double val, out double pos)
		{
			poc = vah = val = pos = double.NaN;
			if (p == null || p.V.Count == 0) return false;
			int mn = p.V.Keys.Min(), mx = p.V.Keys.Max(), n = mx - mn + 1;
			double[] c = new double[n];
			foreach (var kv in p.V) c[kv.Key - mn] = kv.Value;
			int k = 0;
			for (int i = 1; i < n; i++) if (c[i] > c[k]) k = i;
			int up = k, dn = k;
			double acc = c[k], tot = c.Sum();
			while (acc < tot * AreaValor / 100.0)
			{
				double a = up + 1 < n ? c[up + 1] : -1;
				double b = dn - 1 >= 0 ? c[dn - 1] : -1;
				if (a < 0 && b < 0) break;
				if (a >= b) { up++; acc += a; } else { dn--; acc += b; }
			}
			poc = (mn + k) * NivelPts + NivelPts / 2;
			vah = (mn + up + 1) * NivelPts;
			val = (mn + dn) * NivelPts;
			double lo = mn * NivelPts, hi = (mx + 1) * NivelPts;
			pos = (poc - lo) / Math.Max(hi - lo, NivelPts);
			return true;
		}

		private void Vela3(DateTime cierreNY)
		{
			h3.Add(aggH); l3.Add(aggL); c3.Add(Close[0]); t3.Add(cierreNY);
			aggH = double.MinValue; aggL = double.MaxValue;
			double k = 2.0 / 21.0;
			ema3 = double.IsNaN(ema3) ? Close[0] : ema3 + k * (Close[0] - ema3);
			int i = c3.Count - 1, j = i - Fuerza, K = Fuerza;
			if (j >= K)
			{
				bool altoMax = true, bajoMin = true, altoSube = true, bajoBaja = true;
				for (int q = j - K; q <= j + K; q++)
				{
					if (h3[q] > h3[j]) altoMax = false;
					if (l3[q] < l3[j]) bajoMin = false;
					if (q < j && h3[q] >= h3[j]) altoSube = false;
					if (q < j && l3[q] <= l3[j]) bajoBaja = false;
				}
				if (altoMax && altoSube) swH = h3[j];
				if (bajoMin && bajoBaja) swL = l3[j];
			}
			if (!double.IsNaN(swH) && c3[i] > swH)
			{
				eventos.Add(new Evento { T = cierreNY, Dir = 1, Bos = tendencia != -1 });
				tendencia = 1; swH = double.NaN;
			}
			else if (!double.IsNaN(swL) && c3[i] < swL)
			{
				eventos.Add(new Evento { T = cierreNY, Dir = -1, Bos = tendencia != 1 });
				tendencia = -1; swL = double.NaN;
			}
			if (h3.Count > 400) { h3.RemoveAt(0); l3.RemoveAt(0); c3.RemoveAt(0); t3.RemoveAt(0); }
			eventos.RemoveAll(e => (cierreNY - e.T).TotalHours > 24);
		}

		private string Usd(double v) { return (v < 0 ? "-$" : "$") + Math.Abs(v).ToString("#,##0"); }

		protected override void OnBarUpdate()
		{
			if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 1)
			{
				Draw.TextFixed(this, "mbAviso", "ModeloB: usa un gráfico de 1 minuto (tipo Minute).", TextPosition.Center);
				return;
			}
			DateTime cierreNY = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(Time[0], DateTimeKind.Unspecified), tzNT, tzNY);
			DateTime aperturaNY = cierreNY.AddMinutes(-1);
			int minAp = aperturaNY.Hour * 60 + aperturaNY.Minute;
			int minCi = cierreNY.Hour * 60 + cierreNY.Minute;
			bool rth = minAp >= 570 && minAp < 960;

			// nueva sesión regular: el perfil de la anterior pasa a ser "ayer"
			if (rth && aperturaNY.Date != fechaRTH)
			{
				if (hoy.Velas >= 200)
				{
					ayerPerfil = hoy;
					double pos;
					Niveles(ayerPerfil, out yPoc, out yVah, out yVal, out pos);
				}
				hoy = new Perfil();
				fechaRTH = aperturaNY.Date;
				sumPV = 0; sumV = 0;
				enTrade = false; lado = 0;
				panel = "Esperando " + HoraNY + ":" + MinutoNY.ToString("00") + " NY";
			}
			if (rth)
			{
				Agregar(hoy, Low[0], High[0], Volume[0]);
				double tp = (High[0] + Low[0] + Close[0]) / 3;
				sumPV += tp * Volume[0]; sumV += Volume[0];
			}

			// velas de 3 minutos
			aggH = Math.Max(aggH, High[0]); aggL = Math.Min(aggL, Low[0]);
			if (minCi % 3 == 0) Vela3(cierreNY);

			double vwap = sumV > 0 ? sumPV / sumV : double.NaN;
			if (!double.IsNaN(yVah) && rth) { Values[0][0] = yVah; Values[1][0] = yVal; Values[2][0] = yPoc; }
			if (rth && !double.IsNaN(vwap)) Values[3][0] = vwap;
			if (!double.IsNaN(ema3)) Values[4][0] = ema3;

			int minEntrada = HoraNY * 60 + MinutoNY;

			// chequeos en vivo antes de la entrada y decisión al cierre de la vela anterior a la hora
			if (rth && minCi <= minEntrada && aperturaNY.Date == fechaRTH && diaEvaluado != fechaRTH && !double.IsNaN(ema3))
			{
				double precio = Close[0];
				int s = precio > ema3 ? 1 : -1;
				bool hayAyer = !double.IsNaN(yVah);
				bool okA = hayAyer && (precio > yVah || precio < yVal);
				double hPoc, hVah, hVal, hPos;
				bool hayHoy = hoy.Velas >= 20 && Niveles(hoy, out hPoc, out hVah, out hVal, out hPos);
				bool okC = hayHoy && (s == 1 ? hPos : 1 - hPos) <= 0.62;
				DateTime desde = cierreNY.AddMinutes(-MinutosBos);
				bool bosContra = eventos.Any(e => e.Bos && e.Dir == -s && e.T > desde && e.T <= cierreNY);
				bool okV = !double.IsNaN(vwap) && (precio - vwap) * s > 0;
				bool opera = okA && okC && !bosContra && okV;
				string si = "✔", no = "✖";
				panel = "Modelo B · " + fechaRTH.ToString("dd/MM") + " · entrada " + HoraNY + ":" + MinutoNY.ToString("00") + " NY\n"
					+ "EMA 20 (3 min): " + (s == 1 ? "COMPRA" : "VENTA") + "\n"
					+ (okA ? si : no) + " A: fuera del valor de ayer" + (hayAyer ? "" : " (falta ayer)") + "\n"
					+ (okC ? si : no) + " C: perfil de hoy no ya a favor" + (hayHoy ? "" : " (pocos datos)") + "\n"
					+ (!bosContra ? si : no) + " Sin BOS en contra (" + MinutosBos + " min)\n"
					+ (okV ? si : no) + " VWAP a favor\n"
					+ (minCi == minEntrada ? "DECISIÓN: " : "Si fuera ahora: ") + (opera ? (s == 1 ? "COMPRA" : "VENTA") : "NO OPERAR");

				if (minCi == minEntrada)
				{
					diaEvaluado = fechaRTH;
					string tag = "mb" + fechaRTH.ToString("yyyyMMdd");
					if (opera)
					{
						lado = s; enTrade = true; leg1 = leg2 = true; r1 = r2 = 0;
						entrada = precio;
						sl = entrada - s * SlTicks * TickSize;
						tp1 = entrada + s * Tp1Ticks * TickSize;
						tp2 = entrada + s * Tp2Ticks * TickSize;
						barraEntrada = CurrentBar;
						if (s == 1) Draw.ArrowUp(this, tag + "f", false, 0, Low[0] - 2 * TickSize, Brushes.LimeGreen);
						else Draw.ArrowDown(this, tag + "f", false, 0, High[0] + 2 * TickSize, Brushes.Red);
						Draw.Text(this, tag + "t", (s == 1 ? "COMPRA" : "VENTA") + " " + entrada.ToString("0.00"), 0, s == 1 ? Low[0] - 8 * TickSize : High[0] + 8 * TickSize, s == 1 ? Brushes.LimeGreen : Brushes.Red);
						if (Alertar)
							Alert(tag, Priority.High, "Modelo B: " + (s == 1 ? "COMPRA" : "VENTA") + " a mercado. SL " + sl.ToString("0.00") + " · TP1 " + tp1.ToString("0.00") + " · TP2 " + tp2.ToString("0.00"),
								NinjaTrader.Core.Globals.InstallDir + @"\sounds\Alert1.wav", 10, Brushes.Black, Brushes.Yellow);
					}
					else
					{
						Draw.Text(this, tag + "t", "NO OPERAR", 0, High[0] + 6 * TickSize, Brushes.Gray);
						if (Alertar)
							Alert(tag, Priority.Medium, "Modelo B: hoy NO se opera", NinjaTrader.Core.Globals.InstallDir + @"\sounds\Alert2.wav", 10, Brushes.Black, Brushes.Gray);
					}
				}
			}

			// seguimiento de la operación (stop primero si en la misma vela se tocan stop y objetivo)
			if (enTrade && CurrentBar > barraEntrada)
			{
				string tag = "mb" + fechaRTH.ToString("yyyyMMdd");
				int n = CurrentBar - barraEntrada;
				bool cierre = minCi >= 960;
				double fav = lado == 1 ? High[0] - entrada : entrada - Low[0];
				double contra = lado == 1 ? Low[0] - entrada : entrada - High[0];
				double stopTicks = (sl - entrada) * lado / TickSize;
				if (contra / TickSize <= stopTicks)
				{
					if (leg1) { r1 = stopTicks; leg1 = false; }
					if (leg2) { r2 = stopTicks; leg2 = false; }
				}
				else
				{
					if (leg1 && fav >= Tp1Ticks * TickSize) { r1 = Tp1Ticks; leg1 = false; if (BreakEven) sl = entrada; }
					if (leg2 && fav >= Tp2Ticks * TickSize) { r2 = Tp2Ticks; leg2 = false; }
				}
				if (cierre && (leg1 || leg2))
				{
					double t = (Close[0] - entrada) * lado / TickSize;
					if (leg1) { r1 = t; leg1 = false; }
					if (leg2) { r2 = t; leg2 = false; }
				}
				Draw.Line(this, tag + "e", false, n, entrada, 0, entrada, Brushes.DodgerBlue, DashStyleHelper.Solid, 2);
				Draw.Line(this, tag + "s", false, n, sl, 0, sl, Brushes.Red, DashStyleHelper.Solid, 2);
				Draw.Line(this, tag + "1", false, n, tp1, 0, tp1, Brushes.LimeGreen, DashStyleHelper.Dash, 2);
				Draw.Line(this, tag + "2", false, n, tp2, 0, tp2, Brushes.LimeGreen, DashStyleHelper.Solid, 2);
				if (!leg1 && !leg2)
				{
					enTrade = false;
					double usd = (r1 + r2) * (Contratos / 2.0) * ValorTick - Contratos * Costo;
					string res = (r1 >= Tp1Ticks && r2 >= Tp2Ticks) ? "TP1 + TP2" : (r1 >= Tp1Ticks ? "TP1 + " + (cierre ? "cierre" : "stop") : (cierre ? "Cierre 15:59" : "Stop"));
					Draw.Text(this, tag + "r", res + " " + Usd(usd) + " (" + Contratos + " contratos)", 0, lado == 1 ? High[0] + 6 * TickSize : Low[0] - 6 * TickSize, usd >= 0 ? Brushes.LimeGreen : Brushes.Red);
					panel = "Modelo B · " + fechaRTH.ToString("dd/MM") + "\nResultado: " + res + " " + Usd(usd);
				}
			}
			if (State == State.Realtime || CurrentBar == Count - 2)
				Draw.TextFixed(this, "mbPanel", panel, TextPosition.TopRight);
		}

		[Browsable(false), XmlIgnore]
		public Series<double> VahAyer { get { return Values[0]; } }
		[Browsable(false), XmlIgnore]
		public Series<double> ValAyer { get { return Values[1]; } }
		[Browsable(false), XmlIgnore]
		public Series<double> PocAyer { get { return Values[2]; } }
		[Browsable(false), XmlIgnore]
		public Series<double> Vwap { get { return Values[3]; } }
		[Browsable(false), XmlIgnore]
		public Series<double> Ema3 { get { return Values[4]; } }
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private ModeloB[] cacheModeloB;
		public ModeloB ModeloB()
		{
			return ModeloB(Input);
		}

		public ModeloB ModeloB(ISeries<double> input)
		{
			if (cacheModeloB != null)
				for (int idx = 0; idx < cacheModeloB.Length; idx++)
					if (cacheModeloB[idx] != null && cacheModeloB[idx].EqualsInput(input))
						return cacheModeloB[idx];
			return CacheIndicator<ModeloB>(new ModeloB(), input, ref cacheModeloB);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.ModeloB ModeloB()
		{
			return indicator.ModeloB(Input);
		}

		public Indicators.ModeloB ModeloB(ISeries<double> input)
		{
			return indicator.ModeloB(input);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.ModeloB ModeloB()
		{
			return indicator.ModeloB(Input);
		}

		public Indicators.ModeloB ModeloB(ISeries<double> input)
		{
			return indicator.ModeloB(input);
		}
	}
}

#endregion
