"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { BarChart2, Play, TrendingUp, TrendingDown, Minus, ArrowUp, ArrowDown, X } from "lucide-react";
import { runBacktest, listStrategies } from "@/lib/api";
import { formatPct } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────
type Tab  = "chart" | "strategy";
type TF   = "5m" | "15m" | "1h" | "4h" | "1d" | "1w";
type Tool = "none" | "trendline" | "hline" | "buy" | "sell";
type Bar  = { time: number; open: number; high: number; low: number; close: number; volume: number };

interface HLine  { id: string; price: number }
interface TLine  { id: string; p1: { time: number; value: number }; p2: { time: number; value: number } }
interface Marker { time: number; type: "buy" | "sell" }

interface BacktestResult {
  total_return_pct: number; annual_return_pct: number; sharpe_ratio: number;
  max_drawdown_pct: number; win_rate_pct: number; total_trades: number; calmar_ratio: number;
  equity_curve: number[];
  sample_trades: { trade_num: number; direction: string; return_pct: number; hold_days: number; outcome: string }[];
}

// ── Constants ─────────────────────────────────────────────────────────────────
const SYMBOLS: Record<string, string[]> = {
  "FX":      ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY"],
  "Metals":  ["XAUUSD","XAGUSD"],
  "Energy":  ["USOIL","UKOIL","NATGAS"],
  "Crypto":  ["BTCUSD","ETHUSD"],
  "Indices": ["SPX500","NAS100","GER40","UK100","JPN225"],
  "Stocks":  ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META"],
};

const TIMEFRAMES: { label: string; value: TF }[] = [
  { label:"5m", value:"5m" }, { label:"15m", value:"15m" }, { label:"1h", value:"1h" },
  { label:"4h", value:"4h" }, { label:"1D",  value:"1d"  }, { label:"1W", value:"1w"  },
];

const TOOL_INFO: Record<Tool, string> = {
  none:      "Select a drawing tool",
  trendline: "Click 2 points to draw a trend line",
  hline:     "Click a bar to draw a horizontal level",
  buy:       "Click a bar to place a Buy marker",
  sell:      "Click a bar to place a Sell marker",
};

// ── Equity curve SVG (strategy tab) ───────────────────────────────────────────
function EquityCurve({ data, positive }: { data: number[]; positive: boolean }) {
  if (data.length < 2) return null;
  const W=700,H=160,pL=52,pR=12,pT=8,pB=24,iW=W-pL-pR,iH=H-pT-pB;
  const min=Math.min(...data),max=Math.max(...data),range=max-min||1;
  const px=(i:number)=>pL+(i/(data.length-1))*iW;
  const py=(v:number)=>pT+iH-((v-min)/range)*iH;
  const pts=data.map((v,i)=>`${px(i)},${py(v)}`).join(" ");
  const color=positive?"#22c55e":"#e63946";
  const ticks=[0,.25,.5,.75,1].map(t=>({y:pT+iH-t*iH,val:min+t*range}));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{height:H}}>
      {ticks.map((t,i)=><line key={i} x1={pL} y1={t.y} x2={W-pR} y2={t.y} stroke="hsl(0 0% 12%)" strokeWidth="1"/>)}
      <polygon points={`${pL},${py(data[0])} ${pts} ${px(data.length-1)},${pT+iH} ${pL},${pT+iH}`} fill={color} opacity={0.08}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={px(0)} cy={py(data[0])} r="3" fill={color} opacity={0.6}/>
      <circle cx={px(data.length-1)} cy={py(data[data.length-1])} r="4" fill={color}/>
      {ticks.map((t,i)=>(
        <text key={i} x={pL-6} y={t.y+4} textAnchor="end" fontSize="9" fill="hsl(0 0% 40%)" fontFamily="monospace">${(t.val/1000).toFixed(0)}k</text>
      ))}
    </svg>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function BacktestPage() {
  const [tab, setTab] = useState<Tab>("chart");

  // ── Chart state ──────────────────────────────────────────────────────────────
  const chartRef    = useRef<HTMLDivElement>(null);
  const chartInst   = useRef<any>(null);
  const candleSer   = useRef<any>(null);
  const volSer      = useRef<any>(null);
  const lineRefs    = useRef<Map<string, any>>(new Map());
  const allBarsRef   = useRef<Bar[]>([]);
  const replayActive = useRef(false);
  const replayTimer  = useRef<ReturnType<typeof setTimeout>|null>(null);
  const activeToolRef = useRef<Tool>("none");

  const [symbol,    setSymbol]    = useState("EURUSD");
  const [timeframe, setTimeframe] = useState<TF>("1d");
  const [years,     setYears]     = useState(2);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError,   setChartError]   = useState("");
  const [bars,      setBars]      = useState(0);
  const [ohlcv,     setOhlcv]     = useState<{t:string;o:number;h:number;l:number;c:number}|null>(null);
  const [tool,          setTool]          = useState<Tool>("none");
  const [hlines,        setHlines]        = useState<HLine[]>([]);
  const [tlines,        setTlines]        = useState<TLine[]>([]);
  const [markers,       setMarkers]       = useState<Marker[]>([]);
  const [replayStatus, setReplayStatus] = useState<"idle"|"playing"|"paused">("idle");
  const [replayIdx,    setReplayIdx]    = useState(0);
  const [replaySpeed,  setReplaySpeed]  = useState<"fast"|"normal"|"slow">("normal");
  const replayIdxRef   = useRef(0);
  const replayDelayRef = useRef(40);
  const pendingPt   = useRef<{time:number;value:number}|null>(null);

  // ── Strategy state ───────────────────────────────────────────────────────────
  const [strategies, setStrategies] = useState<{name:string;ref:string;description:string}[]>([]);
  const [selected,   setSelected]   = useState("price_momentum");
  const [ticker,     setTicker]     = useState("SPY");
  const [period,     setPeriod]     = useState("1Y");
  const [result,     setResult]     = useState<BacktestResult|null>(null);
  const [stratLoading, setStratLoading] = useState(false);
  const [stratError,   setStratError]   = useState<string|null>(null);

  useEffect(() => {
    listStrategies().then(d => setStrategies(d.strategies));
  }, []);

  // ── Replay engine ─────────────────────────────────────────────────────────────
  // Keep delay in a ref so tickOnce (stable) always uses current speed
  useEffect(() => {
    replayDelayRef.current = replaySpeed === "fast" ? 8 : replaySpeed === "slow" ? 150 : 40;
  }, [replaySpeed]);

  const tickOnce = useCallback(() => {
    const all = allBarsRef.current;
    const idx = replayIdxRef.current;
    if (!replayActive.current || !candleSer.current || !volSer.current) return;
    if (idx >= all.length) { replayActive.current = false; setReplayStatus("idle"); return; }
    const b = all[idx];
    candleSer.current.update({ time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close });
    volSer.current.update({ time: b.time as any, value: b.volume, color: b.close >= b.open ? "rgba(34,197,94,0.35)" : "rgba(230,57,70,0.35)" });
    replayIdxRef.current = idx + 1;
    setReplayIdx(idx + 1);
    if (idx + 1 < all.length) {
      replayTimer.current = setTimeout(tickOnce, replayDelayRef.current);
    } else {
      replayActive.current = false;
      setReplayStatus("idle");
    }
  // stable — reads everything from refs
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopReplay = useCallback(() => {
    replayActive.current = false;
    if (replayTimer.current) { clearTimeout(replayTimer.current); replayTimer.current = null; }
    replayIdxRef.current = 0;
    setReplayIdx(0);
    setReplayStatus("idle");
    // restore full chart
    if (candleSer.current && volSer.current && allBarsRef.current.length > 0) {
      const data = allBarsRef.current;
      candleSer.current.setData(data.map(b => ({ time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close })));
      volSer.current.setData(data.map(b => ({ time: b.time as any, value: b.volume, color: b.close >= b.open ? "rgba(34,197,94,0.35)" : "rgba(230,57,70,0.35)" })));
      chartInst.current?.timeScale().fitContent();
    }
  }, []);

  const pauseReplay = useCallback(() => {
    replayActive.current = false;
    if (replayTimer.current) { clearTimeout(replayTimer.current); replayTimer.current = null; }
    setReplayStatus("paused");
  }, []);

  const playReplay = useCallback(() => {
    if (!candleSer.current || !volSer.current || allBarsRef.current.length === 0) return;
    replayActive.current = true;
    setReplayStatus("playing");
    replayTimer.current = setTimeout(tickOnce, replayDelayRef.current);
  }, [tickOnce]);

  const startReplay = useCallback(() => {
    if (!candleSer.current || !volSer.current || allBarsRef.current.length === 0) return;
    replayActive.current = false;
    if (replayTimer.current) { clearTimeout(replayTimer.current); replayTimer.current = null; }
    candleSer.current.setData([]);
    volSer.current.setData([]);
    replayIdxRef.current = 0;
    setReplayIdx(0);
    replayActive.current = true;
    setReplayStatus("playing");
    replayTimer.current = setTimeout(tickOnce, replayDelayRef.current);
  }, [tickOnce]);

  // ── Load OHLCV ───────────────────────────────────────────────────────────────
  const loadData = useCallback(async (sym:string, tf:TF, yr:number) => {
    stopReplay();
    setChartLoading(true); setChartError("");
    try {
      const res  = await fetch(`${API_URL}/api/v1/backtest/ohlcv?symbol=${sym}&timeframe=${tf}&years=${yr}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "Fetch failed");
      const data: Bar[] = json.data;
      allBarsRef.current = data;
      setBars(data.length);
      if (!candleSer.current) return;
      candleSer.current.setData(data.map(b=>({time:b.time as any,open:b.open,high:b.high,low:b.low,close:b.close})));
      volSer.current.setData(data.map(b=>({time:b.time as any,value:b.volume,color:b.close>=b.open?"rgba(34,197,94,0.35)":"rgba(230,57,70,0.35)"})));
      chartInst.current.timeScale().fitContent();
    } catch(e:any) { setChartError(e.message); }
    finally { setChartLoading(false); }
  }, [stopReplay]);

  // ── Mount chart ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return;
    let cleanup: (() => void) | undefined;
    import("lightweight-charts").then(({ createChart, CrosshairMode }) => {
      if (!chartRef.current) return;
      const chart = createChart(chartRef.current, {
        layout:    { background:{color:"#080810"}, textColor:"#94a3b8" },
        grid:      { vertLines:{color:"rgba(255,255,255,0.04)"}, horzLines:{color:"rgba(255,255,255,0.04)"} },
        crosshair: { mode: CrosshairMode.Normal },
        rightPriceScale: { borderColor:"rgba(255,255,255,0.08)", scaleMargins:{ top:0.08, bottom:0.22 } },
        timeScale: { borderColor:"rgba(255,255,255,0.08)", timeVisible:true, secondsVisible:false },
        width:  chartRef.current.clientWidth,
        height: chartRef.current.clientHeight || 520,
      });

      const cSer = chart.addCandlestickSeries({
        upColor:"#22c55e", downColor:"#e63946",
        borderUpColor:"#22c55e", borderDownColor:"#e63946",
        wickUpColor:"#22c55e", wickDownColor:"#e63946",
      });

      const vSer = chart.addHistogramSeries({ priceFormat:{type:"volume"}, priceScaleId:"vol" });
      chart.priceScale("vol").applyOptions({ scaleMargins:{top:0.85,bottom:0} });

      chart.subscribeCrosshairMove((param:any) => {
        if (!param.time || !param.seriesData) return;
        const d = param.seriesData.get(cSer);
        if (!d) return;
        const dt = new Date(param.time * 1000).toISOString().replace("T"," ").slice(0,16);
        setOhlcv({ t:dt, o:d.open, h:d.high, l:d.low, c:d.close });
      });

      chart.subscribeClick((param:any) => {
        if (!param.point || !param.time) return;
        const price = cSer.coordinateToPrice(param.point.y);
        if (price == null) return;
        const currentTool = activeToolRef.current;
        const time = param.time as number;
        if (currentTool === "hline") {
          addHLine(price, cSer);
        } else if (currentTool === "trendline") {
          if (!pendingPt.current) { pendingPt.current = {time,value:price}; }
          else { addTLine(pendingPt.current, {time,value:price}, chart); pendingPt.current = null; }
        } else if (currentTool === "buy") {
          addMarkerDirect(time, "buy", cSer);
        } else if (currentTool === "sell") {
          addMarkerDirect(time, "sell", cSer);
        }
      });

      chartInst.current = chart;
      candleSer.current = cSer;
      volSer.current    = vSer;

      const ro = new ResizeObserver(() => chart.applyOptions({ width: chartRef.current!.clientWidth, height: chartRef.current!.clientHeight }));
      ro.observe(chartRef.current);

      loadData("EURUSD","1d",2);

      cleanup = () => { ro.disconnect(); chart.remove(); };
    });
    return () => cleanup?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Drawing helpers ──────────────────────────────────────────────────────────
  const addHLine = (price:number, cSer?:any) => {
    const series = cSer || candleSer.current;
    if (!series) return;
    const id = `hl-${Date.now()}`;
    const pl = series.createPriceLine({ price, color:"#3b82f6", lineWidth:1, lineStyle:2, axisLabelVisible:true, title:"Level" });
    lineRefs.current.set(id, pl);
    setHlines(p=>[...p,{id,price}]);
  };

  const addTLine = (p1:{time:number;value:number}, p2:{time:number;value:number}, chart?:any) => {
    const inst = chart || chartInst.current;
    if (!inst) return;
    const id = `tl-${Date.now()}`;
    const s  = inst.addLineSeries({ color:"#f59e0b", lineWidth:1, lastValueVisible:false, priceLineVisible:false });
    s.setData([
      {time:Math.min(p1.time,p2.time) as any, value:p1.time<=p2.time?p1.value:p2.value},
      {time:Math.max(p1.time,p2.time) as any, value:p1.time<=p2.time?p2.value:p1.value},
    ]);
    lineRefs.current.set(id, s);
    setTlines(p=>[...p,{id,p1,p2}]);
  };

  const mkMarker = (m:{time:number;type:"buy"|"sell"}) => ({
    time: m.time as any,
    position: m.type==="buy" ? "belowBar" : "aboveBar",
    color: m.type==="buy" ? "#00e676" : "#ff1744",
    shape: m.type==="buy" ? "arrowUp" : "arrowDown",
    text: m.type==="buy" ? "▲ BUY" : "▼ SELL",
    size: 3,
  });

  const addMarkerDirect = (time:number, type:"buy"|"sell", cSer?:any) => {
    setMarkers(prev=>{
      const next = [...prev,{time,type}];
      const series = cSer || candleSer.current;
      if (series) series.setMarkers(
        [...next].sort((a,b)=>a.time-b.time).map(mkMarker)
      );
      return next;
    });
  };

  const removeHLine = (id:string) => {
    const pl = lineRefs.current.get(id);
    if (pl && candleSer.current) try { candleSer.current.removePriceLine(pl); } catch {}
    lineRefs.current.delete(id);
    setHlines(p=>p.filter(x=>x.id!==id));
  };

  const removeTLine = (id:string) => {
    const s = lineRefs.current.get(id);
    if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
    lineRefs.current.delete(id);
    setTlines(p=>p.filter(x=>x.id!==id));
  };

  const removeMarker = (i:number) => {
    setMarkers(prev=>{
      const next = prev.filter((_,idx)=>idx!==i);
      if (candleSer.current) candleSer.current.setMarkers(
        [...next].sort((a,b)=>a.time-b.time).map(mkMarker)
      );
      return next;
    });
  };

  const clearAll = () => {
    tlines.forEach(tl=>{ const s=lineRefs.current.get(tl.id); if(s&&chartInst.current) try{chartInst.current.removeSeries(s);}catch{} lineRefs.current.delete(tl.id); });
    hlines.forEach(hl=>{ const pl=lineRefs.current.get(hl.id); if(pl&&candleSer.current) try{candleSer.current.removePriceLine(pl);}catch{} lineRefs.current.delete(hl.id); });
    setHlines([]); setTlines([]); setMarkers([]); pendingPt.current = null;
    if (candleSer.current) candleSer.current.setMarkers([]);
  };

  const selectTool = (t:Tool) => {
    setTool(t);
    activeToolRef.current = t;
    pendingPt.current = null;
  };

  const handleLoad = () => { clearAll(); loadData(symbol, timeframe, years); };

  // ── Strategy run ─────────────────────────────────────────────────────────────
  const handleRun = async () => {
    setStratLoading(true); setStratError(null);
    try { setResult(await runBacktest(selected, ticker, period) as BacktestResult); }
    catch(e) { setStratError(e instanceof Error ? e.message : "Backtest failed — backend may be waking up, try again in 30s"); }
    finally { setStratLoading(false); }
  };

  const isPositive = result ? result.total_return_pct >= 0 : true;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-full px-0 py-0">
      {/* ── Header + tabs ── */}
      <div className="terminal-panel mx-4 mt-4">
        <div className="terminal-header">
          <BarChart2 className="h-3 w-3 text-primary" />
          <span className="terminal-label">Strategy Backtester — 151 Trading Strategies Framework</span>
          <div className="ml-auto flex gap-1">
            {(["chart","strategy"] as Tab[]).map(t=>(
              <button key={t} onClick={()=>setTab(t)}
                className={`px-3 py-0.5 text-xs font-mono font-semibold border transition-colors ${tab===t ? "border-primary/50 bg-primary/10 text-primary" : "border-border/30 text-muted-foreground hover:border-primary/30"}`}>
                {t === "chart" ? "CHART" : "STRATEGY"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ══════════════════ CHART TAB ══════════════════ */}
      {tab === "chart" && (
        <div className="mt-2">
          {/* Controls bar */}
          <div className="mx-4 mb-2 terminal-panel">
            <div className="p-2 flex items-center gap-2 flex-wrap">
              {/* Symbol */}
              <select value={symbol} onChange={e=>setSymbol(e.target.value)}
                className="px-2 py-1 bg-background border border-border/50 text-xs font-mono text-foreground focus:outline-none focus:border-primary/50">
                {Object.entries(SYMBOLS).map(([g,syms])=>(
                  <optgroup key={g} label={g}>
                    {syms.map(s=><option key={s} value={s}>{s}</option>)}
                  </optgroup>
                ))}
              </select>

              {/* Timeframe pills */}
              <div className="flex gap-1">
                {TIMEFRAMES.map(tf=>(
                  <button key={tf.value} onClick={()=>setTimeframe(tf.value)}
                    className={`px-2 py-0.5 text-xs font-mono border transition-colors ${timeframe===tf.value ? "border-primary/50 bg-primary/10 text-primary" : "border-border/40 text-muted-foreground hover:border-primary/30"}`}>
                    {tf.label}
                  </button>
                ))}
              </div>

              {/* History */}
              <div className="flex items-center gap-1">
                <span className="terminal-label">HIST:</span>
                {[1,2,3,5].map(y=>(
                  <button key={y} onClick={()=>setYears(y)}
                    className={`px-2 py-0.5 text-xs font-mono border transition-colors ${years===y ? "border-warn/50 bg-warn/10 text-warn" : "border-border/40 text-muted-foreground hover:border-warn/30"}`}>
                    {y}Y
                  </button>
                ))}
              </div>

              <button onClick={handleLoad} disabled={chartLoading}
                className="px-3 py-1 text-xs font-mono font-semibold border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 transition-colors">
                {chartLoading ? "LOADING…" : "LOAD"}
              </button>

              {bars > 0 && (
                <>
                  {/* Speed pills */}
                  <div className="flex gap-0.5">
                    {(["slow","normal","fast"] as const).map(s=>(
                      <button key={s} onClick={()=>setReplaySpeed(s)}
                        className={`px-1.5 py-0.5 text-[10px] font-mono border transition-colors ${replaySpeed===s ? "border-warn/50 bg-warn/10 text-warn" : "border-border/40 text-muted-foreground hover:border-warn/30"}`}>
                        {s === "fast" ? "F" : s === "normal" ? "N" : "S"}
                      </button>
                    ))}
                  </div>

                  {/* ⏮ Rewind — restart from bar 0 */}
                  <button onClick={startReplay} title="Restart from beginning"
                    className="w-7 h-6 flex items-center justify-center border border-border/40 text-muted-foreground hover:border-warn/40 hover:text-warn transition-colors">
                    <svg width="10" height="10" viewBox="0 0 10 10"><polygon points="5,1 1,5 5,9" fill="currentColor"/><rect x="6" y="1" width="2" height="8" rx="0.5" fill="currentColor"/></svg>
                  </button>

                  {/* ▶/⏸ Play / Pause */}
                  {replayStatus === "playing" ? (
                    <button onClick={pauseReplay}
                      className="px-2.5 py-1 text-xs font-mono font-semibold border border-warn/50 bg-warn/10 text-warn hover:bg-warn/20 transition-colors flex items-center gap-1.5">
                      <svg width="9" height="9" viewBox="0 0 9 9"><rect x="0" y="0" width="3" height="9" rx="0.5" fill="currentColor"/><rect x="6" y="0" width="3" height="9" rx="0.5" fill="currentColor"/></svg>
                      PAUSE
                    </button>
                  ) : (
                    <button onClick={replayStatus === "paused" ? playReplay : startReplay}
                      className="px-2.5 py-1 text-xs font-mono font-semibold border border-warn/50 bg-warn/10 text-warn hover:bg-warn/20 transition-colors flex items-center gap-1.5">
                      <svg width="8" height="10" viewBox="0 0 8 10"><polygon points="0,0 8,5 0,10" fill="currentColor"/></svg>
                      {replayStatus === "paused" ? "RESUME" : "REPLAY"}
                    </button>
                  )}

                  {/* ⏹ Stop — restore all bars */}
                  <button onClick={stopReplay} disabled={replayStatus === "idle"}
                    className="w-7 h-6 flex items-center justify-center border border-border/40 text-muted-foreground hover:border-bear/50 hover:text-bear disabled:opacity-30 transition-colors">
                    <svg width="8" height="8" viewBox="0 0 8 8"><rect x="0" y="0" width="8" height="8" rx="1" fill="currentColor"/></svg>
                  </button>

                  {/* Progress */}
                  {replayStatus !== "idle"
                    ? <span className="terminal-label text-warn">{replayIdx}/{bars}</span>
                    : <span className="terminal-label">{bars.toLocaleString()} BARS</span>
                  }
                </>
              )}
              {chartError && <span className="text-xs font-mono text-bear">{chartError}</span>}
            </div>
          </div>

          {/* Chart area + sidebars */}
          <div className="flex mx-4 gap-0 border border-border/30" style={{height:"calc(100vh - 195px)"}}>

            {/* Drawing toolbar */}
            <div className="w-12 bg-background border-r border-border/30 flex flex-col items-center pt-3 gap-2">
              {([
                { t:"trendline" as Tool, icon:<svg width="16" height="16" viewBox="0 0 16 16"><line x1="2" y1="14" x2="14" y2="2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>, label:"Trend Line" },
                { t:"hline"     as Tool, icon:<Minus className="h-3.5 w-3.5"/>,   label:"H-Line"     },
                { t:"buy"       as Tool, icon:<ArrowUp className="h-3.5 w-3.5"/>, label:"Buy"        },
                { t:"sell"      as Tool, icon:<ArrowDown className="h-3.5 w-3.5"/>,label:"Sell"      },
              ]).map(({t,icon,label})=>(
                <button key={t} title={label} onClick={()=>selectTool(tool===t?"none":t)}
                  className={`w-8 h-8 flex items-center justify-center border transition-colors ${tool===t ? "border-primary/50 bg-primary/10 text-primary" : "border-border/30 text-muted-foreground hover:border-primary/30 hover:text-primary"}`}>
                  {icon}
                </button>
              ))}
              <div className="flex-1"/>
              <button title="Clear all" onClick={clearAll}
                className="w-8 h-8 flex items-center justify-center border border-border/30 text-muted-foreground hover:border-bear/50 hover:text-bear transition-colors mb-3">
                <X className="h-3.5 w-3.5"/>
              </button>
            </div>

            {/* Chart column */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* OHLCV tooltip */}
              <div className="px-3 py-1.5 border-b border-border/30 bg-background flex gap-4 text-xs font-mono" style={{minHeight:32}}>
                {ohlcv ? (
                  <>
                    <span className="text-muted-foreground">{symbol} · {ohlcv.t}</span>
                    <span className="text-muted-foreground">O <span className="text-foreground">{ohlcv.o}</span></span>
                    <span className="text-muted-foreground">H <span className="text-bull">{ohlcv.h}</span></span>
                    <span className="text-muted-foreground">L <span className="text-bear">{ohlcv.l}</span></span>
                    <span className="text-muted-foreground">C <span className={ohlcv.c>=ohlcv.o?"text-bull":"text-bear"}>{ohlcv.c}</span></span>
                  </>
                ) : (
                  <span className="text-muted-foreground/50">Hover chart for OHLCV</span>
                )}
              </div>

              {/* Chart canvas */}
              <div ref={chartRef} className="flex-1" style={{cursor:tool!=="none"?"crosshair":"default"}}/>

              {/* Status bar */}
              <div className="px-3 py-1 border-t border-border/30 bg-background flex gap-4 text-[10px] font-mono text-muted-foreground">
                <span className={tool!=="none"?"text-primary":""}>
                  {TOOL_INFO[tool]}
                </span>
                <div className="flex-1"/>
                <span>{hlines.length} H-Lines</span>
                <span>{tlines.length} Trend</span>
                <span className="text-bull">{markers.filter(m=>m.type==="buy").length} Buy</span>
                <span className="text-bear">{markers.filter(m=>m.type==="sell").length} Sell</span>
              </div>
            </div>

            {/* Drawings panel */}
            <div className="w-44 border-l border-border/30 bg-background overflow-y-auto">
              <div className="px-3 py-2 border-b border-border/30 terminal-label">DRAWINGS</div>
              {hlines.length===0 && tlines.length===0 && markers.length===0 ? (
                <div className="px-3 py-3 terminal-label">None yet</div>
              ) : null}
              {hlines.map(hl=>(
                <div key={hl.id} className="flex items-center gap-2 px-3 py-1.5 border-b border-border/20 text-xs font-mono">
                  <Minus className="h-3 w-3 text-primary shrink-0"/>
                  <span className="flex-1 text-foreground">{hl.price.toFixed(4)}</span>
                  <button onClick={()=>removeHLine(hl.id)} className="text-muted-foreground hover:text-bear transition-colors"><X className="h-3 w-3"/></button>
                </div>
              ))}
              {tlines.map(tl=>(
                <div key={tl.id} className="flex items-center gap-2 px-3 py-1.5 border-b border-border/20 text-xs font-mono">
                  <svg width="12" height="12" viewBox="0 0 12 12" className="text-warn shrink-0"><line x1="1" y1="11" x2="11" y2="1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  <span className="flex-1 text-foreground">Trend</span>
                  <button onClick={()=>removeTLine(tl.id)} className="text-muted-foreground hover:text-bear transition-colors"><X className="h-3 w-3"/></button>
                </div>
              ))}
              {markers.map((m,i)=>(
                <div key={`${m.time}-${i}`} className="flex items-center gap-2 px-3 py-1.5 border-b border-border/20 text-xs font-mono">
                  {m.type==="buy" ? <ArrowUp className="h-3 w-3 text-bull shrink-0"/> : <ArrowDown className="h-3 w-3 text-bear shrink-0"/>}
                  <span className={`flex-1 ${m.type==="buy"?"text-bull":"text-bear"}`}>{m.type.toUpperCase()}</span>
                  <button onClick={()=>removeMarker(i)} className="text-muted-foreground hover:text-bear transition-colors"><X className="h-3 w-3"/></button>
                </div>
              ))}
              <div className="mx-2 my-3 p-2 border border-border/30 text-[10px] font-mono text-muted-foreground leading-relaxed">
                <span className="text-primary">Coming soon:</span><br/>
                Fibonacci<br/>Rectangle zones<br/>Text labels<br/>Save drawings
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════ STRATEGY TAB ══════════════════ */}
      {tab === "strategy" && (
        <div className="mt-2 mx-4 grid lg:grid-cols-[260px_1fr] gap-4">

          {/* Config panel */}
          <div className="space-y-4">
            <div className="terminal-panel">
              <div className="terminal-header"><span className="terminal-label">Configuration</span></div>
              <div className="p-4 space-y-4">
                <div>
                  <div className="terminal-label mb-1.5">Strategy</div>
                  <select value={selected} onChange={e=>setSelected(e.target.value)}
                    className="w-full px-2 py-1.5 bg-background border border-border/50 text-xs font-mono text-foreground focus:outline-none focus:border-primary/50">
                    {strategies.map(s=>(
                      <option key={s.name} value={s.name}>[{s.ref}] {s.name.replace(/_/g," ")}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="terminal-label mb-1.5">Ticker</div>
                  <div className="flex items-center border border-border/50 bg-background focus-within:border-primary/50">
                    <span className="pl-2 terminal-label text-primary shrink-0">›</span>
                    <input value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())}
                      className="flex-1 px-2 py-1.5 bg-transparent text-xs font-mono text-foreground focus:outline-none"/>
                  </div>
                </div>
                <div>
                  <div className="terminal-label mb-1.5">Period</div>
                  <div className="grid grid-cols-4 gap-1">
                    {["1Y","2Y","3Y","5Y"].map(p=>(
                      <button key={p} onClick={()=>setPeriod(p)}
                        className={`py-1 text-xs font-mono font-semibold border transition-colors ${period===p ? "border-primary/50 bg-primary/10 text-primary" : "border-border/40 text-muted-foreground hover:border-primary/30"}`}>
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
                <button onClick={handleRun} disabled={stratLoading}
                  className="w-full py-2 text-xs font-mono font-semibold border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 transition-colors flex items-center justify-center gap-2">
                  <Play className="h-3 w-3"/>
                  {stratLoading ? "RUNNING···" : "RUN BACKTEST"}
                </button>
              </div>
            </div>

            {/* Metrics */}
            {result && (
              <div className="terminal-panel">
                <div className="terminal-header"><span className="terminal-label">Performance Metrics</span>
                  <div className={`ml-auto flex items-center gap-1.5 px-2 py-0.5 border font-mono text-xs font-bold ${isPositive?"border-bull/40 bg-bull/10 text-bull":"border-bear/40 bg-bear/10 text-bear"}`}>
                    {isPositive?<TrendingUp className="h-3 w-3"/>:<TrendingDown className="h-3 w-3"/>}
                    {formatPct(result.total_return_pct)}
                  </div>
                </div>
                <div className="divide-y divide-border/30">
                  {[
                    {label:"TOTAL RETURN",  value:formatPct(result.total_return_pct),      color:result.total_return_pct>=0?"text-bull":"text-bear"},
                    {label:"ANNUAL RETURN", value:formatPct(result.annual_return_pct),      color:"text-bull"},
                    {label:"SHARPE RATIO",  value:result.sharpe_ratio.toFixed(2),           color:result.sharpe_ratio>=1?"text-bull":"text-warn"},
                    {label:"MAX DRAWDOWN",  value:`-${result.max_drawdown_pct.toFixed(1)}%`,color:"text-bear"},
                    {label:"WIN RATE",      value:formatPct(result.win_rate_pct),           color:result.win_rate_pct>=50?"text-bull":"text-bear"},
                    {label:"TOTAL TRADES",  value:String(result.total_trades),              color:"text-foreground"},
                    {label:"CALMAR RATIO",  value:result.calmar_ratio.toFixed(2),           color:result.calmar_ratio>=1?"text-bull":"text-warn"},
                  ].map(({label,value,color})=>(
                    <div key={label} className="flex justify-between items-center px-4 py-2">
                      <span className="terminal-label">{label}</span>
                      <span className={`text-xs font-mono font-bold ${color}`}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Chart + trades */}
          <div className="space-y-4">
            {result ? (
              <>
                <div className="terminal-panel">
                  <div className="terminal-header">
                    <span className="terminal-label">Equity Curve</span>
                    <span className="ml-2 font-mono text-[10px] text-foreground">{ticker} / {selected.replace(/_/g," ")} / {period}</span>
                  </div>
                  <div className="p-3">
                    <EquityCurve data={result.equity_curve} positive={isPositive}/>
                  </div>
                </div>
                <div className="terminal-panel">
                  <div className="terminal-header">
                    <span className="terminal-label">Sample Trades</span>
                    <span className="ml-auto terminal-label">{result.sample_trades.length} TRADES SHOWN</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border/50">
                          {["#","Direction","Return","Hold Days","Outcome"].map(h=>(
                            <th key={h} className="text-left px-4 py-2 terminal-label">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.sample_trades.map(t=>(
                          <tr key={t.trade_num} className="border-b border-border/20 hover:bg-muted/20 transition-colors">
                            <td className="px-4 py-2 font-mono text-muted-foreground">{String(t.trade_num).padStart(2,"0")}</td>
                            <td className={`px-4 py-2 font-mono font-bold ${t.direction==="LONG"?"text-bull":"text-bear"}`}>{t.direction}</td>
                            <td className={`px-4 py-2 font-mono font-semibold ${t.return_pct>=0?"text-bull":"text-bear"}`}>{formatPct(t.return_pct)}</td>
                            <td className="px-4 py-2 font-mono text-muted-foreground">{t.hold_days}d</td>
                            <td className="px-4 py-2">
                              <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 border ${t.outcome==="WIN"?"border-bull/30 bg-bull/10 text-bull":"border-bear/30 bg-bear/10 text-bear"}`}>{t.outcome}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="px-4 py-2 border-t border-border/30">
                    <span className="terminal-label">NOTE: SIMULATED RESULTS — CONNECT QUANTCONNECT LEAN FOR PRODUCTION BACKTESTS</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="terminal-panel" style={{minHeight:400}}>
                <div className="flex flex-col items-center justify-center h-96 gap-3">
                  {stratError ? (
                    <>
                      <div className="text-bear/40 font-mono text-5xl">[ ! ]</div>
                      <span className="terminal-label text-bear">{stratError}</span>
                      <button onClick={handleRun} disabled={stratLoading} className="mt-2 px-4 py-1.5 text-xs font-mono border border-primary/40 text-primary hover:bg-primary/10 transition-colors disabled:opacity-40">RETRY</button>
                    </>
                  ) : (
                    <>
                      <div className="text-primary/15 font-mono text-5xl">[ ]</div>
                      <span className="terminal-label">CONFIGURE A STRATEGY AND HIT RUN BACKTEST</span>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
