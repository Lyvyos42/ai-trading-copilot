"use client";
import { useEffect, useRef, useCallback } from "react";
import * as THREE from "three";
import { API_URL } from "@/lib/api";

// ── Theme ──
const THEME = {
  gold: 0xc9a84c,
  bidLow: [8, 145, 178] as [number, number, number],
  bidHigh: [6, 182, 212] as [number, number, number],
  askLow: [59, 130, 246] as [number, number, number],
  askHigh: [99, 102, 241] as [number, number, number],
  liqLow: [16, 185, 129] as [number, number, number],
  liqMid: [234, 179, 8] as [number, number, number],
  liqHigh: [239, 68, 68] as [number, number, number],
};

// ── Helpers ──
function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }
function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }
function smoothstep(edge0: number, edge1: number, x: number) {
  const t = clamp((x - edge0) / Math.max(1e-6, edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}
function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}
function lerpRgb(c1: number[], c2: number[], t: number): [number, number, number] {
  return [lerp(c1[0], c2[0], t) / 255, lerp(c1[1], c2[1], t) / 255, lerp(c1[2], c2[2], t) / 255];
}
function liquidityColor(t: number): [number, number, number] {
  t = clamp(t, 0, 1);
  if (t < 0.5) return lerpRgb(THEME.liqLow, THEME.liqMid, t * 2);
  return lerpRgb(THEME.liqMid, THEME.liqHigh, (t - 0.5) * 2);
}
function formatPrice(p: number | null | undefined) {
  if (p == null || !isFinite(p)) return "—";
  const abs = Math.abs(p);
  if (abs < 50) return p.toFixed(5);
  if (abs < 1000) return p.toFixed(3);
  return p.toFixed(2);
}

interface TerrainData {
  geometry: THREE.PlaneGeometry;
  colIndex: Int32Array;
  rowIndex: Int32Array;
  count: number;
  rows: number;
  cols: number;
}

function buildTerrain(rows: number, cols: number, width: number, depth: number): TerrainData {
  const geo = new THREE.PlaneGeometry(width, depth, cols - 1, rows - 1);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  const count = pos.count;
  const colIndex = new Int32Array(count);
  const rowIndex = new Int32Array(count);
  for (let i = 0; i < count; i++) {
    const x = pos.getX(i);
    const z = pos.getZ(i);
    colIndex[i] = clamp(Math.round(((x / width) + 0.5) * (cols - 1)), 0, cols - 1);
    rowIndex[i] = clamp(Math.round(((z / depth) + 0.5) * (rows - 1)), 0, rows - 1);
  }
  const colorAttr = new THREE.BufferAttribute(new Float32Array(count * 3), 3);
  geo.setAttribute("color", colorAttr);
  return { geometry: geo, colIndex, rowIndex, count, rows, cols };
}

// ── 3D Surface Engine ──
class Surface3DEngine {
  canvas: HTMLCanvasElement;
  container: HTMLElement;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  renderer: THREE.WebGLRenderer;
  target = new THREE.Vector3(0, 0.6, 0);
  destroyed = false;
  private _raf: number | null = null;
  private _clock = new THREE.Clock();
  private spherical: { radius: number; theta: number; phi: number };
  private defaultSpherical: { radius: number; theta: number; phi: number };
  private minRadius: number;
  private maxRadius: number;
  private _dragging = false;
  private _dragLast = { x: 0, y: 0 };
  private _lastInteraction = 0;
  private _resizeObserver: ResizeObserver;
  onFrame?: (dt: number) => void;

  constructor(canvas: HTMLCanvasElement, opts: { radius?: number; targetY?: number } = {}) {
    this.canvas = canvas;
    this.container = canvas.parentElement!;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 500);
    this.target.y = opts.targetY ?? 0.6;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x080808, 1);

    this.scene.fog = new THREE.Fog(0x080808, 10, 40);

    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    const dir = new THREE.DirectionalLight(0xf8f4ec, 0.4);
    dir.position.set(8, 12, 6);
    const point = new THREE.PointLight(THEME.gold, 0.2, 22, 2);
    point.position.set(0, 3, 1);
    this.scene.add(ambient, dir, point);

    const r = opts.radius ?? 16;
    this.defaultSpherical = { radius: r, theta: THREE.MathUtils.degToRad(45), phi: THREE.MathUtils.degToRad(60) };
    this.spherical = { ...this.defaultSpherical };
    this.minRadius = 6;
    this.maxRadius = 40;

    this._bindEvents();
    this._resizeObserver = new ResizeObserver(() => this._onResize());
    this._resizeObserver.observe(this.container);
    this._onResize();
    this._updateCamera();
    this._animate();
  }

  private _bindEvents() {
    this.canvas.addEventListener("pointerdown", this._onPointerDown);
    this.canvas.addEventListener("pointermove", this._onPointerMove);
    window.addEventListener("pointerup", this._onPointerUp);
    this.canvas.addEventListener("wheel", this._onWheel, { passive: false });
    this.canvas.addEventListener("dblclick", this._onDblClick);
  }

  private _onPointerDown = (e: PointerEvent) => {
    this._dragging = true;
    this._dragLast = { x: e.clientX, y: e.clientY };
    this._lastInteraction = performance.now();
  };
  private _onPointerMove = (e: PointerEvent) => {
    if (!this._dragging) return;
    const dx = e.clientX - this._dragLast.x;
    const dy = e.clientY - this._dragLast.y;
    this._dragLast = { x: e.clientX, y: e.clientY };
    this.spherical.theta -= dx * 0.006;
    this.spherical.phi = clamp(this.spherical.phi - dy * 0.006, THREE.MathUtils.degToRad(12), THREE.MathUtils.degToRad(85));
    this._lastInteraction = performance.now();
  };
  private _onPointerUp = () => { this._dragging = false; };
  private _onWheel = (e: WheelEvent) => {
    e.preventDefault();
    this.spherical.radius = clamp(this.spherical.radius * (1 + Math.sign(e.deltaY) * 0.08), this.minRadius, this.maxRadius);
    this._lastInteraction = performance.now();
  };
  private _onDblClick = () => {
    this.spherical = { ...this.defaultSpherical };
    this._lastInteraction = 0;
  };

  private _onResize() {
    const w = Math.max(1, this.container.clientWidth);
    const h = Math.max(1, this.container.clientHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private _updateCamera() {
    const s = this.spherical;
    const sinPhi = Math.sin(s.phi);
    this.camera.position.set(
      this.target.x + s.radius * sinPhi * Math.sin(s.theta),
      this.target.y + s.radius * Math.cos(s.phi),
      this.target.z + s.radius * sinPhi * Math.cos(s.theta),
    );
    this.camera.lookAt(this.target);
    (this.scene.fog as THREE.Fog).near = s.radius * 1.05;
    (this.scene.fog as THREE.Fog).far = s.radius * 2.8;
  }

  private _animate = () => {
    if (this.destroyed) return;
    const dt = Math.min(this._clock.getDelta(), 0.1);
    if (!this._dragging && performance.now() - this._lastInteraction > 1500) {
      this.spherical.theta += 0.001;
    }
    this._updateCamera();
    this.onFrame?.(dt);
    this.renderer.render(this.scene, this.camera);
    this._raf = requestAnimationFrame(this._animate);
  };

  addGridFloor(size: number) {
    const grid = new THREE.GridHelper(size, 24, 0xd4a240, 0xd4a240);
    grid.position.y = -0.02;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.025;
    (grid.material as THREE.Material).depthWrite = false;
    this.scene.add(grid);
  }

  destroy() {
    this.destroyed = true;
    if (this._raf) cancelAnimationFrame(this._raf);
    this._resizeObserver.disconnect();
    this.canvas.removeEventListener("pointerdown", this._onPointerDown);
    this.canvas.removeEventListener("pointermove", this._onPointerMove);
    window.removeEventListener("pointerup", this._onPointerUp);
    this.canvas.removeEventListener("wheel", this._onWheel);
    this.canvas.removeEventListener("dblclick", this._onDblClick);
    this.scene.traverse((obj) => {
      if ((obj as THREE.Mesh).geometry) (obj as THREE.Mesh).geometry.dispose();
      if ((obj as THREE.Mesh).material) {
        const mats = Array.isArray((obj as THREE.Mesh).material) ? (obj as THREE.Mesh).material as THREE.Material[] : [(obj as THREE.Mesh).material as THREE.Material];
        mats.forEach(m => m.dispose());
      }
    });
    this.renderer.dispose();
  }
}

// ── Depth Surface ──
const DEPTH_W = 16, DEPTH_D = 10, DEPTH_H = 3.4;

interface DepthState {
  grid: number[][];
  levels: number[];
  mid: number;
  bidTotal: number;
  askTotal: number;
}

function normalizeDepth(data: any): DepthState | null {
  if (!data?.grid?.length || !data.grid[0]?.length || data.grid[0].length < 2 || data.grid.length < 2) return null;
  const meta = data.meta || {};
  let levels = data.levels;
  if (!levels) {
    const pMin = meta.price_min ?? 0, pMax = meta.price_max ?? 1;
    const n = meta.levels ?? data.grid[0].length;
    const step = n > 1 ? (pMax - pMin) / (n - 1) : 0;
    levels = Array.from({ length: n }, (_, i) => pMin + i * step);
  }
  const mid = data.mid_price ?? meta.mid ?? levels[Math.floor(levels.length / 2)];
  const lastRow = data.grid[data.grid.length - 1];
  let bidTotal = data.bid_total, askTotal = data.ask_total;
  if (bidTotal == null || askTotal == null) {
    bidTotal = 0; askTotal = 0;
    for (let c = 0; c < lastRow.length; c++) {
      if (levels[c] <= mid) bidTotal += lastRow[c]; else askTotal += lastRow[c];
    }
  }
  return { grid: data.grid, levels, mid, bidTotal, askTotal };
}

function computeDepthVertexData(state: DepthState, terrain: TerrainData) {
  const { count, colIndex, rowIndex } = terrain;
  const heights = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const r = rowIndex[i], c = colIndex[i];
    let vol = state.grid[r]?.[c] ?? 0;
    vol = clamp(vol, 0, 1);
    heights[i] = vol * DEPTH_H;
    const px = state.levels[c] ?? state.mid;
    const isBid = px <= state.mid;
    const lo = isBid ? THEME.bidLow : THEME.askLow;
    const hi = isBid ? THEME.bidHigh : THEME.askHigh;
    const rgb = lerpRgb(lo, hi, smoothstep(0, 1, vol));
    const boost = smoothstep(0.65, 1.0, vol) * 0.35;
    colors[i * 3] = rgb[0] + boost;
    colors[i * 3 + 1] = rgb[1] + boost;
    colors[i * 3 + 2] = rgb[2] + boost;
  }
  return { heights, colors };
}

// ── Liquidity Surface ──
const LIQ_W = 11, LIQ_D = 9, LIQ_H = 4.0;

interface LiqState {
  grid: number[][];
  priceLevels: number[];
  maxVolume: number;
  hotspotPrice: number;
}

function normalizeLiquidity(data: any): LiqState | null {
  if (!data?.grid?.length || !data.grid[0]?.length) return null;
  let priceLevels = data.price_levels ?? Array.from({ length: data.grid[0].length }, (_, i) => i);
  let maxVolume = data.max_volume;
  if (maxVolume == null) {
    maxVolume = 0;
    for (const row of data.grid) for (const v of row) if (v > maxVolume) maxVolume = v;
    if (maxVolume <= 0) maxVolume = 1;
  }
  let hotspotPrice = data.hotspot_price;
  if (hotspotPrice == null) {
    const last = data.grid[data.grid.length - 1];
    let best = -Infinity, idx = 0;
    for (let c = 0; c < last.length; c++) if (last[c] > best) { best = last[c]; idx = c; }
    hotspotPrice = priceLevels[idx];
  }
  return { grid: data.grid, priceLevels, maxVolume, hotspotPrice };
}

function computeLiqVertexData(state: LiqState, terrain: TerrainData) {
  const { count, colIndex, rowIndex } = terrain;
  const heights = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const r = rowIndex[i], c = colIndex[i];
    let vol = state.grid[r]?.[c] ?? 0;
    vol = clamp(vol / (state.maxVolume || 1), 0, 1);
    heights[i] = 0.15 + vol * LIQ_H;
    const rgb = liquidityColor(vol);
    const boost = vol > 0.01 ? 0.15 * vol : 0;
    colors[i * 3] = clamp(rgb[0] + boost, 0, 1);
    colors[i * 3 + 1] = clamp(rgb[1] + boost * 0.5, 0, 1);
    colors[i * 3 + 2] = clamp(rgb[2], 0, 1);
  }
  return { heights, colors };
}

// ── React Components ──

interface Surface3DProps {
  ticker: string;
  className?: string;
}

export function DepthSurface3D({ ticker, className }: Surface3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<Surface3DEngine | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const wireRef = useRef<THREE.Mesh | null>(null);
  const midPlaneRef = useRef<THREE.Mesh | null>(null);
  const terrainRef = useRef<TerrainData | null>(null);
  const tweenRef = useRef<{ startH: Float32Array; endH: Float32Array; startC: Float32Array; endC: Float32Array; t0: number; dur: number } | null>(null);
  const infoRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const engine = new Surface3DEngine(canvas, { radius: 13, targetY: 0.6 });
    engineRef.current = engine;
    engine.addGridFloor(Math.max(DEPTH_W, DEPTH_D) * 1.4);

    engine.onFrame = (dt) => {
      const tw = tweenRef.current;
      if (!tw || !terrainRef.current) return;
      const t = (performance.now() - tw.t0) / tw.dur;
      const geo = terrainRef.current.geometry;
      const posAttr = geo.attributes.position;
      const colorAttr = geo.attributes.color;
      const eased = easeInOutCubic(clamp(t, 0, 1));
      for (let i = 0; i < terrainRef.current.count; i++) {
        posAttr.setY(i, lerp(tw.startH[i], tw.endH[i], eased));
        colorAttr.setXYZ(i, lerp(tw.startC[i * 3], tw.endC[i * 3], eased), lerp(tw.startC[i * 3 + 1], tw.endC[i * 3 + 1], eased), lerp(tw.startC[i * 3 + 2], tw.endC[i * 3 + 2], eased));
      }
      posAttr.needsUpdate = true;
      colorAttr.needsUpdate = true;
      geo.computeVertexNormals();
      if (t >= 1) tweenRef.current = null;
    };

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      engine.destroy();
      engineRef.current = null;
    };
  }, []);

  const setData = useCallback((raw: any) => {
    const engine = engineRef.current;
    if (!engine) return;
    const state = normalizeDepth(raw);
    if (!state) return;

    const rows = state.grid.length, cols = state.grid[0].length;
    let rebuilt = false;
    if (!terrainRef.current || terrainRef.current.rows !== rows || terrainRef.current.cols !== cols) {
      if (meshRef.current) { engine.scene.remove(meshRef.current); meshRef.current.geometry.dispose(); (meshRef.current.material as THREE.Material).dispose(); }
      if (wireRef.current) { engine.scene.remove(wireRef.current); (wireRef.current.material as THREE.Material).dispose(); }
      const terrain = buildTerrain(rows, cols, DEPTH_W, DEPTH_D);
      terrainRef.current = terrain;
      const mat = new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 18, side: THREE.DoubleSide });
      meshRef.current = new THREE.Mesh(terrain.geometry, mat);
      engine.scene.add(meshRef.current);
      const wireMat = new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true, transparent: true, opacity: 0.03, depthWrite: false });
      wireRef.current = new THREE.Mesh(terrain.geometry, wireMat);
      engine.scene.add(wireRef.current);
      if (!midPlaneRef.current) {
        const pg = new THREE.PlaneGeometry(DEPTH_D, DEPTH_H * 1.6);
        const pm = new THREE.MeshBasicMaterial({ color: THEME.gold, transparent: true, opacity: 0.15, side: THREE.DoubleSide, depthWrite: false });
        midPlaneRef.current = new THREE.Mesh(pg, pm);
        midPlaneRef.current.rotation.y = Math.PI / 2;
        midPlaneRef.current.position.y = DEPTH_H * 0.5;
        engine.scene.add(midPlaneRef.current);
      }
      rebuilt = true;
    }

    const terrain = terrainRef.current!;
    const vdata = computeDepthVertexData(state, terrain);
    const posAttr = terrain.geometry.attributes.position;
    const colorAttr = terrain.geometry.attributes.color;

    if (rebuilt) {
      for (let i = 0; i < terrain.count; i++) {
        posAttr.setY(i, vdata.heights[i]);
        colorAttr.setXYZ(i, vdata.colors[i * 3], vdata.colors[i * 3 + 1], vdata.colors[i * 3 + 2]);
      }
      posAttr.needsUpdate = true;
      colorAttr.needsUpdate = true;
      terrain.geometry.computeVertexNormals();
    } else {
      const startH = new Float32Array(terrain.count);
      const startC = new Float32Array(terrain.count * 3);
      for (let j = 0; j < terrain.count; j++) {
        startH[j] = posAttr.getY(j);
        startC[j * 3] = colorAttr.getX(j);
        startC[j * 3 + 1] = colorAttr.getY(j);
        startC[j * 3 + 2] = colorAttr.getZ(j);
      }
      tweenRef.current = { startH, endH: vdata.heights, startC, endC: vdata.colors, t0: performance.now(), dur: 500 };
    }

    const pMin = state.levels[0], pMax = state.levels[state.levels.length - 1];
    const frac = pMax > pMin ? (state.mid - pMin) / (pMax - pMin) : 0.5;
    if (midPlaneRef.current) midPlaneRef.current.position.x = (clamp(frac, 0, 1) - 0.5) * DEPTH_W;

    if (infoRef.current) {
      const bidHeavy = state.bidTotal >= state.askTotal;
      const ratio = state.askTotal > 0 ? (state.bidTotal / state.askTotal) : Infinity;
      const ratioStr = isFinite(ratio) ? `B/A: ${ratio.toFixed(1)}x` : "B/A: ∞";
      infoRef.current.innerHTML = `<span class="${bidHeavy ? "text-cyan-400" : "text-blue-400"}">${bidHeavy ? "BID HEAVY" : "ASK HEAVY"}</span> <span class="text-muted-foreground ml-2">${ratioStr}</span>`;
    }
  }, []);

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    const fetchData = () => {
      fetch(`${API_URL}/api/v1/market/depth-surface/${encodeURIComponent(ticker)}`)
        .then(r => r.json())
        .then(setData)
        .catch(() => {});
    };
    fetchData();
    pollRef.current = setInterval(fetchData, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [ticker, setData]);

  return (
    <div className={`flex flex-col bg-background ${className ?? ""}`}>
      <div className="terminal-header shrink-0">
        <span className="terminal-label">3D ORDER BOOK DEPTH</span>
        <div ref={infoRef} className="ml-auto text-[11px] font-mono" />
      </div>
      <div className="relative flex-1 min-h-0">
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
    </div>
  );
}

export function LiquiditySurface3D({ ticker, className }: Surface3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<Surface3DEngine | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const wireRef = useRef<THREE.Mesh | null>(null);
  const terrainRef = useRef<TerrainData | null>(null);
  const tweenRef = useRef<{ startH: Float32Array; endH: Float32Array; startC: Float32Array; endC: Float32Array; t0: number; dur: number } | null>(null);
  const infoRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const engine = new Surface3DEngine(canvas, { radius: 15, targetY: 0.5 });
    engineRef.current = engine;
    engine.addGridFloor(Math.max(LIQ_W, LIQ_D) * 1.4);

    engine.onFrame = (dt) => {
      const tw = tweenRef.current;
      if (!tw || !terrainRef.current) return;
      const t = (performance.now() - tw.t0) / tw.dur;
      const geo = terrainRef.current.geometry;
      const posAttr = geo.attributes.position;
      const colorAttr = geo.attributes.color;
      const eased = easeInOutCubic(clamp(t, 0, 1));
      for (let i = 0; i < terrainRef.current.count; i++) {
        posAttr.setY(i, lerp(tw.startH[i], tw.endH[i], eased));
        colorAttr.setXYZ(i, lerp(tw.startC[i * 3], tw.endC[i * 3], eased), lerp(tw.startC[i * 3 + 1], tw.endC[i * 3 + 1], eased), lerp(tw.startC[i * 3 + 2], tw.endC[i * 3 + 2], eased));
      }
      posAttr.needsUpdate = true;
      colorAttr.needsUpdate = true;
      geo.computeVertexNormals();
      if (t >= 1) tweenRef.current = null;
    };

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      engine.destroy();
      engineRef.current = null;
    };
  }, []);

  const setData = useCallback((raw: any) => {
    const engine = engineRef.current;
    if (!engine) return;
    const state = normalizeLiquidity(raw);
    if (!state) return;

    const rows = state.grid.length, cols = state.grid[0].length;
    let rebuilt = false;
    if (!terrainRef.current || terrainRef.current.rows !== rows || terrainRef.current.cols !== cols) {
      if (meshRef.current) { engine.scene.remove(meshRef.current); meshRef.current.geometry.dispose(); (meshRef.current.material as THREE.Material).dispose(); }
      if (wireRef.current) { engine.scene.remove(wireRef.current); (wireRef.current.material as THREE.Material).dispose(); }
      const terrain = buildTerrain(rows, cols, LIQ_W, LIQ_D);
      terrainRef.current = terrain;
      const mat = new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 40, specular: new THREE.Color(0x333322), side: THREE.DoubleSide });
      meshRef.current = new THREE.Mesh(terrain.geometry, mat);
      engine.scene.add(meshRef.current);
      const wireMat = new THREE.MeshBasicMaterial({ color: 0xc9a84c, wireframe: true, transparent: true, opacity: 0.04 });
      wireRef.current = new THREE.Mesh(terrain.geometry, wireMat);
      engine.scene.add(wireRef.current);
      rebuilt = true;
    }

    const terrain = terrainRef.current!;
    const vdata = computeLiqVertexData(state, terrain);
    const posAttr = terrain.geometry.attributes.position;
    const colorAttr = terrain.geometry.attributes.color;

    if (rebuilt) {
      for (let i = 0; i < terrain.count; i++) {
        posAttr.setY(i, vdata.heights[i]);
        colorAttr.setXYZ(i, vdata.colors[i * 3], vdata.colors[i * 3 + 1], vdata.colors[i * 3 + 2]);
      }
      posAttr.needsUpdate = true;
      colorAttr.needsUpdate = true;
      terrain.geometry.computeVertexNormals();
    } else {
      const startH = new Float32Array(terrain.count);
      const startC = new Float32Array(terrain.count * 3);
      for (let j = 0; j < terrain.count; j++) {
        startH[j] = posAttr.getY(j);
        startC[j * 3] = colorAttr.getX(j);
        startC[j * 3 + 1] = colorAttr.getY(j);
        startC[j * 3 + 2] = colorAttr.getZ(j);
      }
      tweenRef.current = { startH, endH: vdata.heights, startC, endC: vdata.colors, t0: performance.now(), dur: 500 };
    }

    if (infoRef.current) {
      const grid = state.grid, levels = state.priceLevels;
      let migrationText = "COLLECTING…";
      if (grid.length >= 4) {
        const half = Math.floor(grid.length / 2);
        const centroid = (rows: number[][]) => {
          let sum = 0, wsum = 0;
          for (const row of rows) for (let ci = 0; ci < row.length; ci++) { sum += row[ci] * levels[ci]; wsum += row[ci]; }
          return wsum > 0 ? sum / wsum : null;
        };
        const c1 = centroid(grid.slice(0, half));
        const c2 = centroid(grid.slice(half));
        if (c1 == null || c2 == null) migrationText = "— STABLE";
        else if (c2 > c1) migrationText = "↑ MIGRATING UP";
        else if (c2 < c1) migrationText = "↓ MIGRATING DOWN";
        else migrationText = "— STABLE";
      }
      const migClass = migrationText.includes("UP") ? "text-emerald-400" : migrationText.includes("DOWN") ? "text-red-400" : "text-gray-400";
      infoRef.current.innerHTML = `<span class="text-primary">HOT ${formatPrice(state.hotspotPrice)}</span> <span class="${migClass} ml-2">${migrationText}</span>`;
    }
  }, []);

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    const fetchData = () => {
      fetch(`${API_URL}/api/v1/market/liquidity-surface/${encodeURIComponent(ticker)}`)
        .then(r => r.json())
        .then(setData)
        .catch(() => {});
    };
    fetchData();
    pollRef.current = setInterval(fetchData, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [ticker, setData]);

  return (
    <div className={`flex flex-col bg-background ${className ?? ""}`}>
      <div className="terminal-header shrink-0">
        <span className="terminal-label">3D LIQUIDITY HEATMAP</span>
        <div ref={infoRef} className="ml-auto text-[11px] font-mono" />
      </div>
      <div className="relative flex-1 min-h-0">
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
    </div>
  );
}
