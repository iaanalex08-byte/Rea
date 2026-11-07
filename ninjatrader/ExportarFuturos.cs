// ExportarFuturos — descarga y exporta velas de 1 minuto de NQ, GC, YM y CL (2024 a hoy)
// para comparar las estrategias de "POC Apertura CDMX" en otros activos.
//
// Uso: NinjaScript Editor -> clic derecho en la carpeta Indicators -> New Indicator -> nombre "ExportarFuturos"
//      -> borrar todo y pegar este archivo -> clic derecho -> Compile. Luego agregarlo a cualquier gráfico.
// El avance se ve en New -> NinjaScript Output. Al terminar, los archivos quedan en
//      Documentos\NinjaTrader 8\export\POC_NQ, POC_GC, POC_YM y POC_CL (un .csv por contrato, hora en UTC).
// Solo lee datos: no envía órdenes ni usa ninguna cuenta.
// Para no descargar algún activo, borra su línea en la lista "activos" de IniciarDescargas().

#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
	public class ExportarFuturos : Indicator
	{
		private readonly List<BarsRequest> requests = new List<BarsRequest>();
		private int pendientes;
		private bool iniciado;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Name = "ExportarFuturos";
				Description = "Descarga y exporta 1 min de NQ, GC, YM y CL (2024 a hoy) para el backtest";
				IsOverlay = true;
				Calculate = Calculate.OnBarClose;
			}
			else if (State == State.DataLoaded && !iniciado)
			{
				iniciado = true;
				IniciarDescargas();
			}
			else if (State == State.Terminated)
			{
				lock (requests)
				{
					foreach (BarsRequest r in requests)
						r.Dispose();
					requests.Clear();
				}
			}
		}

		protected override void OnBarUpdate() { }

		// Devuelve (contrato, desde, hasta) cubriendo el periodo en que cada vencimiento es el principal.
		private List<Tuple<string, DateTime, DateTime>> Contratos(string raiz)
		{
			DateTime hoy = DateTime.Today;
			var lista = new List<Tuple<string, DateTime, DateTime>>();
			int[] meses;
			if (raiz == "GC")
				meses = new[] { 2, 4, 6, 8, 10, 12 };
			else if (raiz == "CL")
				meses = new[] { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 };
			else
				meses = new[] { 3, 6, 9, 12 };

			for (int y = 2024; y <= hoy.Year + 1; y++)
			{
				foreach (int m in meses)
				{
					DateTime venc = new DateTime(y, m, 1);
					DateTime desde, hasta;
					if (raiz == "CL")
					{
						// El CL vence alrededor del día 20 del mes anterior a su mes de contrato
						desde = venc.AddMonths(-3);
						hasta = venc.AddMonths(-1).AddDays(24);
					}
					else if (raiz == "GC")
					{
						// El GC deja de ser el principal a finales del mes anterior a su vencimiento
						desde = venc.AddMonths(-3);
						hasta = venc.AddDays(-1);
					}
					else
					{
						desde = venc.AddMonths(-3);
						hasta = new DateTime(y, m, 21);
					}
					if (hasta < new DateTime(2024, 1, 1) || desde > hoy)
						continue;
					if (hasta > hoy)
						hasta = hoy.AddDays(1);
					string nombre = string.Format("{0} {1:00}-{2:00}", raiz, m, y % 100);
					lista.Add(Tuple.Create(nombre, desde, hasta));
				}
			}
			return lista;
		}

		private void IniciarDescargas()
		{
			string[] activos = { "NQ", "GC", "YM", "CL" };
			var trabajo = new List<Tuple<string, string, DateTime, DateTime>>();
			foreach (string raiz in activos)
			{
				string carpeta = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "export", "POC_" + raiz);
				Directory.CreateDirectory(carpeta);
				foreach (var c in Contratos(raiz))
					trabajo.Add(Tuple.Create(carpeta, c.Item1, c.Item2, c.Item3));
			}

			pendientes = trabajo.Count;
			Print(string.Format("ExportarFuturos: descargando {0} contratos de {1}", trabajo.Count, string.Join(", ", activos)));

			foreach (var w in trabajo)
			{
				string carpeta = w.Item1, nombre = w.Item2;
				Instrument ins = Instrument.GetInstrument(nombre);
				if (ins == null)
				{
					Print("  " + nombre + ": instrumento no encontrado");
					Terminar();
					continue;
				}
				var br = new BarsRequest(ins, w.Item3, w.Item4);
				br.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1 };
				br.TradingHours = ins.MasterInstrument.TradingHours;
				br.MergePolicy = MergePolicy.DoNotMerge;
				lock (requests)
					requests.Add(br);
				br.Request(new Action<BarsRequest, ErrorCode, string>((req, err, msg) => Guardar(carpeta, nombre, req, err, msg)));
			}
		}

		private void Guardar(string carpeta, string nombre, BarsRequest req, ErrorCode err, string msg)
		{
			try
			{
				if (err != ErrorCode.NoError || req.Bars == null || req.Bars.Count == 0)
				{
					Print(string.Format("  {0}: SIN DATOS ({1} {2})", nombre, err, msg));
					return;
				}
				TimeZoneInfo tz = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
				CultureInfo inv = CultureInfo.InvariantCulture;
				var sb = new StringBuilder();
				sb.AppendLine("time,open,high,low,close,volume");
				for (int i = 0; i < req.Bars.Count; i++)
				{
					// NinjaTrader marca la vela con su hora de cierre: se guarda la hora de apertura en UTC
					DateTime local = DateTime.SpecifyKind(req.Bars.GetTime(i), DateTimeKind.Unspecified);
					DateTime utc = TimeZoneInfo.ConvertTimeToUtc(local, tz).AddMinutes(-1);
					sb.Append(utc.ToString("yyyy-MM-ddTHH:mm:ss", inv)).Append("Z,")
					  .Append(req.Bars.GetOpen(i).ToString(inv)).Append(',')
					  .Append(req.Bars.GetHigh(i).ToString(inv)).Append(',')
					  .Append(req.Bars.GetLow(i).ToString(inv)).Append(',')
					  .Append(req.Bars.GetClose(i).ToString(inv)).Append(',')
					  .Append(req.Bars.GetVolume(i).ToString(inv)).AppendLine();
				}
				File.WriteAllText(Path.Combine(carpeta, nombre + ".csv"), sb.ToString());
				Print(string.Format("  {0}: {1:N0} velas, {2:d} a {3:d}", nombre, req.Bars.Count,
					req.Bars.GetTime(0), req.Bars.GetTime(req.Bars.Count - 1)));
			}
			catch (Exception ex)
			{
				Print("  " + nombre + ": ERROR " + ex.Message);
			}
			finally
			{
				Terminar();
			}
		}

		private void Terminar()
		{
			if (Interlocked.Decrement(ref pendientes) == 0)
				Print("ExportarFuturos: LISTO. Comprime las carpetas POC_NQ, POC_GC, POC_YM y POC_CL de "
					+ Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "export") + " en un .zip y súbelo.");
		}
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private ExportarFuturos[] cacheExportarFuturos;
		public ExportarFuturos ExportarFuturos()
		{
			return ExportarFuturos(Input);
		}

		public ExportarFuturos ExportarFuturos(ISeries<double> input)
		{
			if (cacheExportarFuturos != null)
				for (int idx = 0; idx < cacheExportarFuturos.Length; idx++)
					if (cacheExportarFuturos[idx] != null &&  cacheExportarFuturos[idx].EqualsInput(input))
						return cacheExportarFuturos[idx];
			return CacheIndicator<ExportarFuturos>(new ExportarFuturos(), input, ref cacheExportarFuturos);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.ExportarFuturos ExportarFuturos()
		{
			return indicator.ExportarFuturos(Input);
		}

		public Indicators.ExportarFuturos ExportarFuturos(ISeries<double> input )
		{
			return indicator.ExportarFuturos(input);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.ExportarFuturos ExportarFuturos()
		{
			return indicator.ExportarFuturos(Input);
		}

		public Indicators.ExportarFuturos ExportarFuturos(ISeries<double> input )
		{
			return indicator.ExportarFuturos(input);
		}
	}
}

#endregion
