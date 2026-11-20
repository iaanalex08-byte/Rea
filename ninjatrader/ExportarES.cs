// ExportarES — descarga y exporta velas de 1 minuto de los contratos trimestrales del ES
// (2024 a hoy) para el backtest de "POC Apertura CDMX".
//
// Uso: NinjaScript Editor -> Indicators -> clic derecho -> New Indicator -> nombre "ExportarES"
//      -> borrar todo y pegar este archivo -> F5 (compilar). Luego agregarlo a cualquier gráfico.
// El avance se ve en New -> NinjaScript Output. Al terminar, los archivos quedan en
//      Documentos\NinjaTrader 8\export\POC_ES\  (un .csv por contrato, hora en UTC).
// Solo lee datos: no envía órdenes ni usa ninguna cuenta.

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
	public class ExportarES : Indicator
	{
		private readonly List<BarsRequest> requests = new List<BarsRequest>();
		private string carpeta;
		private int pendientes;
		private bool iniciado;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Name = "ExportarES";
				Description = "Descarga y exporta 1 min de ES 03-24 a ES 12-26 para el backtest POC Apertura CDMX";
				IsOverlay = true;
				Calculate = Calculate.OnBarClose;
			}
			else if (State == State.DataLoaded && !iniciado)
			{
				iniciado = true;
				carpeta = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "export", "POC_ES");
				Directory.CreateDirectory(carpeta);
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

		private void IniciarDescargas()
		{
			DateTime hoy = DateTime.Today;
			var lista = new List<Tuple<string, DateTime, DateTime>>();
			for (int y = 2024; y <= hoy.Year + 1; y++)
			{
				foreach (int m in new[] { 3, 6, 9, 12 })
				{
					DateTime venc = new DateTime(y, m, 1);
					DateTime desde = venc.AddMonths(-3);
					DateTime hasta = new DateTime(y, m, 21);
					if (desde > hoy)
						continue;
					if (hasta > hoy)
						hasta = hoy.AddDays(1);
					string nombre = string.Format("ES {0:00}-{1:00}", m, y % 100);
					lista.Add(Tuple.Create(nombre, desde, hasta));
				}
			}

			pendientes = lista.Count;
			Print(string.Format("ExportarES: descargando {0} contratos a {1}", lista.Count, carpeta));

			foreach (var c in lista)
			{
				Instrument ins = Instrument.GetInstrument(c.Item1);
				if (ins == null)
				{
					Print("  " + c.Item1 + ": instrumento no encontrado");
					Terminar();
					continue;
				}
				var br = new BarsRequest(ins, c.Item2, c.Item3);
				br.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1 };
				br.TradingHours = ins.MasterInstrument.TradingHours;
				br.MergePolicy = MergePolicy.DoNotMerge;
				lock (requests)
					requests.Add(br);
				string nombre = c.Item1;
				br.Request(new Action<BarsRequest, ErrorCode, string>((req, err, msg) => Guardar(nombre, req, err, msg)));
			}
		}

		private void Guardar(string nombre, BarsRequest req, ErrorCode err, string msg)
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
				Print("ExportarES: LISTO. Comprime la carpeta " + carpeta + " en un .zip y súbela.");
		}
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private ExportarES[] cacheExportarES;
		public ExportarES ExportarES()
		{
			return ExportarES(Input);
		}

		public ExportarES ExportarES(ISeries<double> input)
		{
			if (cacheExportarES != null)
				for (int idx = 0; idx < cacheExportarES.Length; idx++)
					if (cacheExportarES[idx] != null &&  cacheExportarES[idx].EqualsInput(input))
						return cacheExportarES[idx];
			return CacheIndicator<ExportarES>(new ExportarES(), input, ref cacheExportarES);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.ExportarES ExportarES()
		{
			return indicator.ExportarES(Input);
		}

		public Indicators.ExportarES ExportarES(ISeries<double> input )
		{
			return indicator.ExportarES(input);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.ExportarES ExportarES()
		{
			return indicator.ExportarES(Input);
		}

		public Indicators.ExportarES ExportarES(ISeries<double> input )
		{
			return indicator.ExportarES(input);
		}
	}
}

#endregion
