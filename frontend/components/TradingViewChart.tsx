"use client";
import { useEffect, useRef } from "react";

// Map our display tickers → TradingView symbol format
const TV_SYMBOL: Record<string, string> = {
  // Metals
  "XAUUSD": "OANDA:XAUUSD", "XAGUSD": "OANDA:XAGUSD",
  "XPTUSD": "OANDA:XPTUSD", "XPDUSD": "OANDA:XPDUSD",
  // FX majors
  "EURUSD": "FX:EURUSD",   "EURUSD=X": "FX:EURUSD",
  "GBPUSD": "FX:GBPUSD",   "GBPUSD=X": "FX:GBPUSD",
  "USDJPY": "FX:USDJPY",   "USDJPY=X": "FX:USDJPY",
  "AUDUSD": "FX:AUDUSD",   "AUDUSD=X": "FX:AUDUSD",
  "USDCAD": "FX:USDCAD",   "USDCAD=X": "FX:USDCAD",
  "USDCHF": "FX:USDCHF",   "USDCHF=X": "FX:USDCHF",
  "NZDUSD": "FX:NZDUSD",   "NZDUSD=X": "FX:NZDUSD",
  // FX crosses
  "EURGBP": "FX:EURGBP",   "EURGBP=X": "FX:EURGBP",
  "EURJPY": "FX:EURJPY",   "EURJPY=X": "FX:EURJPY",
  "GBPJPY": "FX:GBPJPY",   "GBPJPY=X": "FX:GBPJPY",
  "EURCHF": "FX:EURCHF",   "EURCHF=X": "FX:EURCHF",
  "EURAUD": "FX:EURAUD",   "EURAUD=X": "FX:EURAUD",
  "EURCAD": "FX:EURCAD",   "EURCAD=X": "FX:EURCAD",
  "EURNZD": "FX:EURNZD",   "EURNZD=X": "FX:EURNZD",
  "GBPAUD": "FX:GBPAUD",   "GBPAUD=X": "FX:GBPAUD",
  "GBPCAD": "FX:GBPCAD",   "GBPCAD=X": "FX:GBPCAD",
  "GBPCHF": "FX:GBPCHF",   "GBPCHF=X": "FX:GBPCHF",
  "GBPNZD": "FX:GBPNZD",   "GBPNZD=X": "FX:GBPNZD",
  "AUDJPY": "FX:AUDJPY",   "AUDJPY=X": "FX:AUDJPY",
  "CADJPY": "FX:CADJPY",   "CADJPY=X": "FX:CADJPY",
  "CHFJPY": "FX:CHFJPY",   "CHFJPY=X": "FX:CHFJPY",
  "NZDJPY": "FX:NZDJPY",   "NZDJPY=X": "FX:NZDJPY",
  "AUDCAD": "FX:AUDCAD",   "AUDCAD=X": "FX:AUDCAD",
  "AUDCHF": "FX:AUDCHF",   "AUDCHF=X": "FX:AUDCHF",
  "AUDNZD": "FX:AUDNZD",   "AUDNZD=X": "FX:AUDNZD",
  "CADCHF": "FX:CADCHF",   "CADCHF=X": "FX:CADCHF",
  "NZDCAD": "FX:NZDCAD",   "NZDCAD=X": "FX:NZDCAD",
  "NZDCHF": "FX:NZDCHF",   "NZDCHF=X": "FX:NZDCHF",
  // Exotic FX
  "USDTRY": "FX:USDTRY",   "USDTRY=X": "FX:USDTRY",
  "USDZAR": "FX:USDZAR",   "USDZAR=X": "FX:USDZAR",
  "USDMXN": "FX:USDMXN",   "USDMXN=X": "FX:USDMXN",
  "USDSEK": "FX:USDSEK",   "USDSEK=X": "FX:USDSEK",
  "USDNOK": "FX:USDNOK",   "USDNOK=X": "FX:USDNOK",
  "USDSGD": "FX:USDSGD",   "USDSGD=X": "FX:USDSGD",
  "USDHKD": "FX:USDHKD",   "USDHKD=X": "FX:USDHKD",
  "USDCNH": "FX:USDCNH",   "USDCNH=X": "FX:USDCNH",
  "USDINR": "FX:USDINR",   "USDINR=X": "FX:USDINR",
  "USDBRL": "FX:USDBRL",   "USDBRL=X": "FX:USDBRL",
  "USDKRW": "FX:USDKRW",   "USDKRW=X": "FX:USDKRW",
  // Indices
  "US500":  "SP:SPX",    "SPX":    "SP:SPX",
  "US100":  "NASDAQ:NDX","NDX":    "NASDAQ:NDX",
  "US30":   "DJ:DJI",    "DJIA":   "DJ:DJI",
  "US2000": "TVC:RUT",
  "UK100":  "TVC:UKX",
  "GER40":  "TVC:DEU40", "DAX":    "TVC:DEU40",
  "FRA40":  "TVC:CAC40", "CAC40":  "TVC:CAC40",
  "JPN225": "TVC:NI225", "NKY":    "TVC:NI225",
  "HK50":   "TVC:HSI",
  "AUS200": "ASX:XJO",
  "ESP35":  "TVC:IBEX35",
  "STOXX50":"TVC:STOXX50E",
  // Energy
  "USOIL":  "TVC:USOIL", "UKOIL":  "TVC:UKOIL",
  "NATGAS": "TVC:NATURALGAS",
  // Commodities
  "CORN":   "CBOT:ZC1!",  "WHEAT":  "CBOT:ZW1!",
  "SOYBEAN":"CBOT:ZS1!",  "COFFEE": "ICEUS:KC1!",
  "SUGAR":  "ICEUS:SB1!",
  // Crypto
  "BTC-USD":  "BITSTAMP:BTCUSD", "ETH-USD":  "BITSTAMP:ETHUSD",
  "SOL-USD":  "BINANCE:SOLUSDT", "BNB-USD":  "BINANCE:BNBUSDT",
  "XRP-USD":  "BITSTAMP:XRPUSD", "ADA-USD":  "BINANCE:ADAUSDT",
  "DOGE-USD": "BINANCE:DOGEUSDT","AVAX-USD": "BINANCE:AVAXUSDT",
  "MATIC-USD":"BINANCE:MATICUSDT","DOT-USD": "BINANCE:DOTUSDT",
  "LINK-USD": "BINANCE:LINKUSDT","UNI-USD":  "BINANCE:UNIUSDT",
  "LTC-USD":  "BITSTAMP:LTCUSD", "BCH-USD":  "BITSTAMP:BCHUSD",
  "ATOM-USD": "BINANCE:ATOMUSDT","OP-USD":   "BINANCE:OPUSDT",
  "ARB-USD":  "BINANCE:ARBUSDT", "SHIB-USD": "BINANCE:SHIBUSDT",
  "PEPE-USD": "BINANCE:PEPEUSDT","WIF-USD":  "BINANCE:WIFUSDT",
};

// Map our interval strings to TradingView resolution strings
const TV_INTERVAL: Record<string, string> = {
  "1m": "1", "5m": "5", "15m": "15", "30m": "30",
  "1h": "60", "4h": "240",
  "1d": "D", "1wk": "W", "1mo": "M",
};

function toTVSymbol(ticker: string): string {
  const upper = ticker.toUpperCase();
  if (TV_SYMBOL[upper]) return TV_SYMBOL[upper];
  if (TV_SYMBOL[ticker]) return TV_SYMBOL[ticker];
  // Fallback for US stocks: assume NASDAQ
  return `NASDAQ:${ticker.replace("=X","").replace("-USD","").replace("=F","")}`;
}

function toTVInterval(interval: string): string {
  return TV_INTERVAL[interval] || "D";
}

interface TradingViewChartProps {
  ticker: string;
  interval?: string;
  fillContainer?: boolean;
}

export function TradingViewChart({ ticker, interval = "1d", fillContainer }: TradingViewChartProps) {
  const containerRef  = useRef<HTMLDivElement>(null);
  // Keep interval in a ref so it's readable at mount time without being a dep.
  // This means: interval sets the INITIAL timeframe when a new ticker loads,
  // but changing interval alone does NOT recreate the widget (preserving drawings).
  const intervalRef = useRef(interval);
  useEffect(() => { intervalRef.current = interval; }, [interval]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Clear previous widget
    container.innerHTML = "";

    // TradingView requires a specific DOM structure:
    // .tradingview-widget-container > .tradingview-widget-container__widget + <script>
    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "calc(100% - 32px)";
    widgetDiv.style.width = "100%";
    container.appendChild(widgetDiv);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    // Must use textContent — TradingView reads the script's text as config JSON
    script.textContent = JSON.stringify({
      autosize: true,
      symbol: toTVSymbol(ticker),
      // Use the current interval as the initial timeframe; user can change via TV's own toolbar
      interval: toTVInterval(intervalRef.current),
      timezone: "Etc/UTC",
      theme: "dark",
      style: "1",
      locale: "en",
      backgroundColor: "#0a0a0a",
      hide_top_toolbar: false,
      hide_legend: false,
      hide_side_toolbar: false,
      allow_symbol_change: false,
      save_image: false,
      calendar: false,
      support_host: "https://www.tradingview.com",
    });
    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  // Only recreate the widget when the TICKER changes — not on interval change.
  // This preserves drawings (position boxes, trendlines etc) when the user
  // switches timeframes using our buttons or TradingView's own toolbar.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container"
      style={{
        width: "100%",
        // fillContainer relies on parent having explicit height via flex-1
        // We also set a min-height so the widget always has room to render
        height: fillContainer ? "100%" : "380px",
        minHeight: fillContainer ? "400px" : "380px",
      }}
    />
  );
}
