// ExportarDelta — delta y delta acumulado (CVD) por vela, con exportación a CSV, para medir el orderflow
// en los retrocesos al POC de las 10:30.
//
// Cómo se calcula: con Tick Replay, cada operación (tick "Last") se compara con el bid/ask de ese momento.
//   precio >= ask  -> compra agresiva      precio <= bid -> venta agresiva      en medio -> mitad y mitad
//   Delta = compras - ventas de la vela.  CVD = suma del delta desde la apertura del día (hora CDMX).
//
// Uso:
//  1. Tools -> Options -> Market data -> marcar "Show Tick Replay".
//  2. NinjaScript Editor -> clic derecho en Indicators -> New Indicator -> nombre "ExportarDelta"
//     -> borrar todo, pegar este archivo -> clic derecho -> Compile.
//  3. Abrir un gráfico de NQ o MNQ (contrato actual, ej. "NQ 12-26") en 1 minuto. En Data Series:
//     marcar "Tick Replay" y poner "Days to load" = 60 a 90 (o lo máximo que deje tu proveedor de datos).
//  4. Agregar el indicador ExportarDelta. Tarda en cargar (procesa cada tick).
//  5. Al cerrar el gráfico (o quitar el indicador) se termina de escribir el archivo en
//     Documentos\NinjaTrader 8\export\ORDERFLOW\<instrumento>.csv (hora de apertura de la vela en UTC).
//     Comprime la carpeta ORDERFLOW y súbela.
// Solo lee datos: no envía órdenes ni usa ninguna cuenta.

#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
	public class ExportarDelta : Indicator
	{
		private double curBuy, curSell, nextBuy, nextSell, cvd;
		private DateTime cvdDay = DateTime.MinValue;
		private StreamWriter sw;
		private TimeZoneInfo tzNT, tzCdmx;
		private readonly CultureInfo inv = CultureInfo.InvariantCulture;
		private int rows;
		private double ticksVistos;

		[NinjaScriptProperty]
		[Range(0, 23)]
		[Display(Name = "Exportar desde (hora CDMX)", Order = 1, GroupName = "Exportación")]
		public int HoraInicio { get; set; }

		[NinjaScriptProperty]
		[Range(1, 24)]
		[Display(Name = "Exportar hasta (hora CDMX)", Order = 2, GroupName = "Exportación")]
		public int HoraFin { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Guardar CSV", Order = 3, GroupName = "Exportación")]
		public bool GuardarCsv { get; set; }

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Name = "ExportarDelta";
				Description = "Delta y CVD por vela (Tick Replay) y exportación a CSV";
				Calculate = Calculate.OnEachTick;
				IsOverlay = false;
				DrawOnPricePanel = false;
				BarsRequiredToPlot = 0;
				HoraInicio = 7;
				HoraFin = 15;
				GuardarCsv = true;
				AddPlot(new Stroke(Brushes.DodgerBlue, 3), PlotStyle.Bar, "Delta");
				AddPlot(new Stroke(Brushes.Orange, 2), PlotStyle.Line, "CVD");
			}
			else if (State == State.DataLoaded)
			{
				tzNT = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
				tzCdmx = TimeZoneInfo.CreateCustomTimeZone("CDMX fija", TimeSpan.FromHours(-6), "CDMX fija", "CDMX fija");
				if (GuardarCsv)
				{
					string carpeta = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "export", "ORDERFLOW");
					Directory.CreateDirectory(carpeta);
					string nombre = Instrument.FullName.Replace(" ", "_").Replace("/", "-") + "_" + MinutosVela() + "min_" + DateTime.Now.ToString("yyyyMMdd_HHmm") + ".csv";
					sw = new StreamWriter(Path.Combine(carpeta, nombre), false);
					sw.WriteLine("time,open,high,low,close,volume,buy,sell,delta,cvd");
					Print("ExportarDelta: escribiendo " + Path.Combine(carpeta, nombre));
				}
			}
			else if (State == State.Terminated)
			{
				if (sw != null)
				{
					sw.Flush();
					sw.Close();
					sw = null;
					Print(string.Format("ExportarDelta: LISTO, {0:N0} velas exportadas.", rows));
					if (ticksVistos == 0)
						Print("ExportarDelta: ATENCIÓN, no llegó ningún tick: activa Tick Replay en la serie de datos o el delta saldrá en cero.");
				}
			}
		}

		protected override void OnMarketData(MarketDataEventArgs e)
		{
			if (e.MarketDataType != MarketDataType.Last || CurrentBar < 0)
				return;
			double v = e.Volume;
			ticksVistos += v;
			double b = 0, s = 0;
			if (e.Ask > 0 && e.Price >= e.Ask)
				b = v;
			else if (e.Bid > 0 && e.Price <= e.Bid)
				s = v;
			else
			{
				b = v / 2.0;
				s = v / 2.0;
			}
			// NinjaTrader marca la vela con su hora de cierre: un tick posterior pertenece a la vela siguiente
			if (e.Time > Time[0])
			{
				nextBuy += b;
				nextSell += s;
			}
			else
			{
				curBuy += b;
				curSell += s;
			}
		}

		protected override void OnBarUpdate()
		{
			if (IsFirstTickOfBar && CurrentBar > 0)
			{
				CerrarVela(1);
				curBuy = nextBuy;
				curSell = nextSell;
				nextBuy = 0;
				nextSell = 0;
			}
			double d = curBuy - curSell;
			Values[0][0] = d;
			Values[1][0] = cvd + d;
			PlotBrushes[0][0] = d >= 0 ? Brushes.SeaGreen : Brushes.Crimson;
		}

		// En velas Volumetric, BarsPeriod.Value son los "ticks per level"; los minutos están en el periodo base
		private int MinutosVela()
		{
			if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute && BarsPeriod.BaseBarsPeriodType == BarsPeriodType.Minute)
				return BarsPeriod.BaseBarsPeriodValue;
			return BarsPeriod.Value;
		}

		private void CerrarVela(int ago)
		{
			DateTime local = DateTime.SpecifyKind(Time[ago], DateTimeKind.Unspecified);
			DateTime utcOpen = TimeZoneInfo.ConvertTimeToUtc(local, tzNT).AddMinutes(-MinutosVela());
			DateTime cdmx = TimeZoneInfo.ConvertTimeFromUtc(utcOpen, tzCdmx);
			if (cdmx.Date != cvdDay)
			{
				cvd = 0;
				cvdDay = cdmx.Date;
			}
			double delta = curBuy - curSell;
			cvd += delta;
			Values[0][ago] = delta;
			Values[1][ago] = cvd;
			if (sw != null && cdmx.Hour >= HoraInicio && cdmx.Hour < HoraFin)
			{
				sw.Write(utcOpen.ToString("yyyy-MM-ddTHH:mm:ss", inv));
				sw.Write("Z,");
				sw.Write(Open[ago].ToString(inv)); sw.Write(',');
				sw.Write(High[ago].ToString(inv)); sw.Write(',');
				sw.Write(Low[ago].ToString(inv)); sw.Write(',');
				sw.Write(Close[ago].ToString(inv)); sw.Write(',');
				sw.Write(Volume[ago].ToString(inv)); sw.Write(',');
				sw.Write(curBuy.ToString(inv)); sw.Write(',');
				sw.Write(curSell.ToString(inv)); sw.Write(',');
				sw.Write(delta.ToString(inv)); sw.Write(',');
				sw.WriteLine(cvd.ToString(inv));
				rows++;
				if (rows % 5000 == 0)
					sw.Flush();
			}
		}

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Delta { get { return Values[0]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> CVD { get { return Values[1]; } }
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private ExportarDelta[] cacheExportarDelta;
		public ExportarDelta ExportarDelta(int horaInicio, int horaFin, bool guardarCsv)
		{
			return ExportarDelta(Input, horaInicio, horaFin, guardarCsv);
		}

		public ExportarDelta ExportarDelta(ISeries<double> input, int horaInicio, int horaFin, bool guardarCsv)
		{
			if (cacheExportarDelta != null)
				for (int idx = 0; idx < cacheExportarDelta.Length; idx++)
					if (cacheExportarDelta[idx] != null && cacheExportarDelta[idx].HoraInicio == horaInicio && cacheExportarDelta[idx].HoraFin == horaFin && cacheExportarDelta[idx].GuardarCsv == guardarCsv && cacheExportarDelta[idx].EqualsInput(input))
						return cacheExportarDelta[idx];
			return CacheIndicator<ExportarDelta>(new ExportarDelta() { HoraInicio = horaInicio, HoraFin = horaFin, GuardarCsv = guardarCsv }, input, ref cacheExportarDelta);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.ExportarDelta ExportarDelta(int horaInicio, int horaFin, bool guardarCsv)
		{
			return indicator.ExportarDelta(Input, horaInicio, horaFin, guardarCsv);
		}

		public Indicators.ExportarDelta ExportarDelta(ISeries<double> input, int horaInicio, int horaFin, bool guardarCsv)
		{
			return indicator.ExportarDelta(input, horaInicio, horaFin, guardarCsv);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.ExportarDelta ExportarDelta(int horaInicio, int horaFin, bool guardarCsv)
		{
			return indicator.ExportarDelta(Input, horaInicio, horaFin, guardarCsv);
		}

		public Indicators.ExportarDelta ExportarDelta(ISeries<double> input, int horaInicio, int horaFin, bool guardarCsv)
		{
			return indicator.ExportarDelta(input, horaInicio, horaFin, guardarCsv);
		}
	}
}

#endregion
