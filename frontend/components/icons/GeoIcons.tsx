/**
 * GeoIcons — Geometric SVG Icon System
 *
 * All icons are constructed from geometric primitives (lines, arcs, circles)
 * at 1–2px stroke weight on a 16×16 viewBox.
 * No filled shapes. No emoji. No icon library.
 * Each icon communicates function through form: scientific instrument aesthetic.
 */

import React from "react";

interface IconProps {
  size?: number;
  color?: string;
  strokeWidth?: number;
  className?: string;
  style?: React.CSSProperties;
}

const defaults = {
  size: 16,
  color: "currentColor",
  strokeWidth: 1.5,
};

// ─── Navigation & UI ──────────────────────────────────────────────────────────

/** Terminal / Dashboard — 3 horizontal bars with left-aligned dots */
export function IconTerminal({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <rect x="1.5" y="2" width="13" height="12" rx="1" />
      <polyline points="4,5.5 6,8 4,10.5" />
      <line x1="8" y1="10.5" x2="13" y2="10.5" />
    </svg>
  );
}

/** Signal / Zap — geometric lightning derived from angles */
export function IconSignal({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <polyline points="9.5,2 5.5,8.5 8.5,8.5 6.5,14 10.5,7.5 7.5,7.5 9.5,2" />
    </svg>
  );
}

/** Intel / News — folded corner document */
export function IconIntel({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <path d="M3 14V3a1 1 0 011-1h6.5L13 4.5V14a1 1 0 01-1 1H4a1 1 0 01-1-1z" />
      <polyline points="9.5,2 9.5,5 13,5" />
      <line x1="5.5" y1="8" x2="10.5" y2="8" />
      <line x1="5.5" y1="10.5" x2="10.5" y2="10.5" />
      <line x1="5.5" y1="5.5" x2="7.5" y2="5.5" />
    </svg>
  );
}

/** Portfolio / Briefcase — geometric case outline */
export function IconPortfolio({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <rect x="1.5" y="5.5" width="13" height="9" rx="1" />
      <path d="M5 5.5V4a1 1 0 011-1h4a1 1 0 011 1v1.5" />
      <line x1="1.5" y1="9.5" x2="14.5" y2="9.5" />
    </svg>
  );
}

/** Agents / Network — hub-and-spoke topology */
export function IconAgents({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <circle cx="8" cy="8" r="1.5" />
      <circle cx="3" cy="4" r="1.5" />
      <circle cx="13" cy="4" r="1.5" />
      <circle cx="3" cy="12" r="1.5" />
      <circle cx="13" cy="12" r="1.5" />
      <line x1="4.25" y1="4.75" x2="6.5" y2="7" />
      <line x1="11.75" y1="4.75" x2="9.5" y2="7" />
      <line x1="4.25" y1="11.25" x2="6.5" y2="9" />
      <line x1="11.75" y1="11.25" x2="9.5" y2="9" />
    </svg>
  );
}

/** Backtest — timeline with regression line */
export function IconBacktest({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <polyline points="2,12 5,7 8,9 11,5 14,3" />
      <line x1="2" y1="12" x2="14" y2="12" />
      <line x1="2" y1="3" x2="2" y2="13" />
      <line x1="2.5" y1="10" x2="13.5" y2="4.5" strokeDasharray="1.5 1.5" strokeWidth="1" opacity="0.5" />
    </svg>
  );
}

/** Refresh — open arc with arrow */
export function IconRefresh({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <path d="M13.5 4A6.5 6.5 0 103 11.5" />
      <polyline points="11,2.5 13.5,4 12,6.5" />
    </svg>
  );
}

/** Settings / Gear — precise circular gear */
export function IconSettings({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4" />
    </svg>
  );
}

/** Logout — arrow exiting rectangle */
export function IconLogout({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <path d="M6 3H3a1 1 0 00-1 1v8a1 1 0 001 1h3" />
      <polyline points="10.5,5.5 13.5,8 10.5,10.5" />
      <line x1="13.5" y1="8" x2="6" y2="8" />
    </svg>
  );
}

/** Crown — tier premium indicator */
export function IconCrown({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <polyline points="2,11 2,6 5.5,9.5 8,4 10.5,9.5 14,6 14,11" />
      <line x1="2" y1="13" x2="14" y2="13" />
    </svg>
  );
}

/** Lock — security state */
export function IconLock({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <rect x="3.5" y="8" width="9" height="7" rx="1" />
      <path d="M5.5 8V5.5a2.5 2.5 0 015 0V8" />
      <circle cx="8" cy="11.5" r="1" />
    </svg>
  );
}

/** X / Close */
export function IconX({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <line x1="3" y1="3" x2="13" y2="13" />
      <line x1="13" y1="3" x2="3" y2="13" />
    </svg>
  );
}

/** Menu / hamburger */
export function IconMenu({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <line x1="2.5" y1="5" x2="13.5" y2="5" />
      <line x1="2.5" y1="8" x2="13.5" y2="8" />
      <line x1="2.5" y1="11" x2="13.5" y2="11" />
    </svg>
  );
}

/** Chevron Down */
export function IconChevronDown({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <polyline points="4,6.5 8,10.5 12,6.5" />
    </svg>
  );
}

/** Arrow Right */
export function IconArrowRight({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <line x1="3" y1="8" x2="13" y2="8" />
      <polyline points="9,4.5 13,8 9,11.5" />
    </svg>
  );
}

/** Shield — risk management */
export function IconShield({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <path d="M8 1.5L2.5 4v4.5c0 3 2 5 5.5 6 3.5-1 5.5-3 5.5-6V4L8 1.5z" />
      <polyline points="5.5,8 7,9.5 10.5,6" />
    </svg>
  );
}

/** Clock */
export function IconClock({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <circle cx="8" cy="8" r="6" />
      <polyline points="8,5 8,8.5 10.5,10.5" />
    </svg>
  );
}

/** Target / Crosshair */
export function IconTarget({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <circle cx="8" cy="8" r="5" />
      <circle cx="8" cy="8" r="2" />
      <line x1="8" y1="1.5" x2="8" y2="3" />
      <line x1="8" y1="13" x2="8" y2="14.5" />
      <line x1="1.5" y1="8" x2="3" y2="8" />
      <line x1="13" y1="8" x2="14.5" y2="8" />
    </svg>
  );
}

/** Trend Up */
export function IconTrendUp({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <polyline points="2,11.5 6,7.5 9,10 14,4" />
      <polyline points="10.5,4 14,4 14,7.5" />
    </svg>
  );
}

/** Trend Down */
export function IconTrendDown({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <polyline points="2,4.5 6,8.5 9,6 14,12" />
      <polyline points="10.5,12 14,12 14,8.5" />
    </svg>
  );
}

/** Dollar / Value */
export function IconDollar({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" className={className} style={style}>
      <line x1="8" y1="1.5" x2="8" y2="14.5" />
      <path d="M5 4.5c0-1.1 1.3-2 3-2s3 .9 3 2-1.3 2-3 2-3 .9-3 2 1.3 2 3 2 3-.9 3-2" />
    </svg>
  );
}

/** Bell alert */
export function IconBell({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <path d="M6.5 13.5a1.5 1.5 0 003 0" />
      <path d="M8 2a1 1 0 00-1 1v.5C5 4 3.5 5.5 3.5 7.5v3.5L2 12.5h12l-1.5-1.5V7.5C12.5 5.5 11 4 9 3.5V3a1 1 0 00-1-1z" />
    </svg>
  );
}

/** Calendar — page with grid lines */
export function IconCalendar({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <rect x="2" y="3" width="12" height="11" rx="1.5" />
      <line x1="2" y1="6.5" x2="14" y2="6.5" />
      <line x1="5.5" y1="3" x2="5.5" y2="1.5" />
      <line x1="10.5" y1="3" x2="10.5" y2="1.5" />
      <line x1="5.5" y1="6.5" x2="5.5" y2="14" strokeWidth="0.75" opacity="0.4" />
      <line x1="10.5" y1="6.5" x2="10.5" y2="14" strokeWidth="0.75" opacity="0.4" />
      <line x1="2" y1="10" x2="14" y2="10" strokeWidth="0.75" opacity="0.4" />
    </svg>
  );
}

/** Correlation Grid — 2x2 cells with connection lines */
export function IconGrid({ size = 16, color = "currentColor", strokeWidth = 1.5, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      <rect x="2" y="2" width="5" height="5" rx="0.5" />
      <rect x="9" y="2" width="5" height="5" rx="0.5" />
      <rect x="2" y="9" width="5" height="5" rx="0.5" />
      <rect x="9" y="9" width="5" height="5" rx="0.5" />
      <line x1="7" y1="4.5" x2="9" y2="4.5" strokeDasharray="1 1" strokeWidth="1" opacity="0.5" />
      <line x1="4.5" y1="7" x2="4.5" y2="9" strokeDasharray="1 1" strokeWidth="1" opacity="0.5" />
    </svg>
  );
}

// ─── Agent Role Geometry Icons ────────────────────────────────────────────────
// These are 2D projections of 3D geometric forms — suggest depth through line construction

/** Researcher — Octahedron (2D projection showing dual-pyramid form) */
export function GeoOctahedron({ size = 32, color = "currentColor", strokeWidth = 1.2, active = false }: IconProps & { active?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="geo-svg" style={{ transform: "translateZ(0)" }}>
      {/* Main visible faces */}
      <polygon points="16,3 27,16 16,29 5,16" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.9" />
      {/* Cross-section equatorial diamond */}
      <ellipse cx="16" cy="16" rx="11" ry="5.5" stroke={color} strokeWidth={strokeWidth * 0.6} strokeDasharray="2 1.5" fill="none" opacity="0.45" />
      {/* Top-face edges */}
      <line x1="16" y1="3" x2="27" y2="16" stroke={color} strokeWidth={strokeWidth} opacity="0.9" />
      <line x1="16" y1="3" x2="5" y2="16" stroke={color} strokeWidth={strokeWidth} opacity="0.9" />
      {/* Hidden bottom-face edges */}
      <line x1="27" y1="16" x2="16" y2="29" stroke={color} strokeWidth={strokeWidth * 0.5} strokeDasharray="2 2" opacity="0.3" />
      <line x1="5" y1="16" x2="16" y2="29" stroke={color} strokeWidth={strokeWidth * 0.5} strokeDasharray="2 2" opacity="0.3" />
      {active && <circle cx="16" cy="3" r="1.5" fill={color} opacity="0.8" />}
    </svg>
  );
}

/** Analyst — Cylinder (elliptical top + body) */
export function GeoCylinder({ size = 32, color = "currentColor", strokeWidth = 1.2, active = false }: IconProps & { active?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="geo-svg">
      {/* Body rectangle */}
      <path d="M6 10v12" stroke={color} strokeWidth={strokeWidth} opacity="0.7" />
      <path d="M26 10v12" stroke={color} strokeWidth={strokeWidth} opacity="0.7" />
      {/* Top ellipse */}
      <ellipse cx="16" cy="10" rx="10" ry="4" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.95" />
      {/* Bottom ellipse — partial, hidden back arc */}
      <path d="M6 22 C6 24.2 10.5 26 16 26 C21.5 26 26 24.2 26 22" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.95" />
      <path d="M6 22 C6 19.8 10.5 18 16 18 C21.5 18 26 19.8 26 22" stroke={color} strokeWidth={strokeWidth * 0.4} strokeDasharray="2 2" fill="none" opacity="0.25" />
      {/* Interior depth line */}
      <line x1="6" y1="10" x2="26" y2="10" stroke={color} strokeWidth={strokeWidth * 0.3} opacity="0.2" />
      {active && <ellipse cx="16" cy="10" rx="3" ry="1.2" fill={color} opacity="0.6" />}
    </svg>
  );
}

/** Generator — Cube (isometric projection) */
export function GeoCube({ size = 32, color = "currentColor", strokeWidth = 1.2, active = false }: IconProps & { active?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="geo-svg">
      {/* Top face */}
      <polygon points="16,3 27,9.5 16,16 5,9.5" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.9" />
      {/* Left face */}
      <polygon points="5,9.5 16,16 16,29 5,22.5" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.7" />
      {/* Right face */}
      <polygon points="27,9.5 16,16 16,29 27,22.5" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.55" />
      {/* Central vertical axis */}
      <line x1="16" y1="16" x2="16" y2="29" stroke={color} strokeWidth={strokeWidth * 0.4} opacity="0.4" />
      {active && <circle cx="16" cy="3" r="1.5" fill={color} opacity="0.8" />}
    </svg>
  );
}

/** Evaluator — Sphere (concentric arcs + grid lines) */
export function GeoSphere({ size = 32, color = "currentColor", strokeWidth = 1.2, active = false }: IconProps & { active?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="geo-svg">
      {/* Outer circle */}
      <circle cx="16" cy="16" r="12.5" stroke={color} strokeWidth={strokeWidth} />
      {/* Horizontal latitude lines */}
      <ellipse cx="16" cy="10.5" rx="9" ry="3.5" stroke={color} strokeWidth={strokeWidth * 0.6} fill="none" opacity="0.45" />
      <ellipse cx="16" cy="16" rx="12.5" ry="5" stroke={color} strokeWidth={strokeWidth * 0.6} fill="none" opacity="0.5" />
      <ellipse cx="16" cy="21.5" rx="9" ry="3.5" stroke={color} strokeWidth={strokeWidth * 0.6} fill="none" opacity="0.35" />
      {/* Vertical meridian arc */}
      <path d="M16 3.5 C20 3.5 20 28.5 16 28.5" stroke={color} strokeWidth={strokeWidth * 0.6} fill="none" opacity="0.35" />
      <path d="M16 3.5 C12 3.5 12 28.5 16 28.5" stroke={color} strokeWidth={strokeWidth * 0.6} fill="none" strokeDasharray="2 1.5" opacity="0.25" />
      {active && <circle cx="16" cy="16" r="3" stroke={color} strokeWidth={strokeWidth} fill="none" />}
    </svg>
  );
}

/** Orchestrator — Icosahedron (complex geodesic projection) */
export function GeoIcosahedron({ size = 32, color = "currentColor", strokeWidth = 1.2, active = false }: IconProps & { active?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="geo-svg">
      {/* Outer pentagon */}
      <polygon points="16,3 28,11.5 23,25 9,25 4,11.5" stroke={color} strokeWidth={strokeWidth} fill="none" opacity="0.85" />
      {/* Inner triangle fan from center */}
      <line x1="16" y1="3"  x2="16" y2="25" stroke={color} strokeWidth={strokeWidth * 0.7} opacity="0.5" />
      <line x1="28" y1="11.5" x2="4" y2="11.5" stroke={color} strokeWidth={strokeWidth * 0.7} opacity="0.5" />
      <line x1="23" y1="25" x2="4" y2="11.5" stroke={color} strokeWidth={strokeWidth * 0.7} opacity="0.4" />
      <line x1="9" y1="25" x2="28" y2="11.5" stroke={color} strokeWidth={strokeWidth * 0.7} opacity="0.4" />
      {/* Center point with cross */}
      <circle cx="16" cy="16" r="1.5" fill={color} opacity="0.7" />
      {active && <polygon points="16,3 28,11.5 23,25 9,25 4,11.5" stroke={color} strokeWidth={strokeWidth * 1.5} fill="none" opacity="0.3" />}
    </svg>
  );
}

/** Executor — Torus (nested ovals suggesting revolution) */
export function GeoTorus({ size = 32, color = "currentColor", strokeWidth = 1.2, active = false }: IconProps & { active?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="geo-svg">
      {/* Outer ring */}
      <ellipse cx="16" cy="16" rx="12.5" ry="7" stroke={color} strokeWidth={strokeWidth} opacity="0.9" />
      {/* Inner ring (the hole) */}
      <ellipse cx="16" cy="16" rx="5.5" ry="3" stroke={color} strokeWidth={strokeWidth} opacity="0.75" />
      {/* Perpendicular revolution arc — shows the tube */}
      <path d="M16 9 C18.5 9 20.5 12 20.5 16 C20.5 20 18.5 23 16 23" stroke={color} strokeWidth={strokeWidth * 0.6} fill="none" opacity="0.5" />
      <path d="M16 9 C13.5 9 11.5 12 11.5 16 C11.5 20 13.5 23 16 23" stroke={color} strokeWidth={strokeWidth * 0.6} strokeDasharray="2 1.5" fill="none" opacity="0.3" />
      {active && <ellipse cx="16" cy="16" rx="12.5" ry="7" stroke={color} strokeWidth={strokeWidth * 1.5} fill="none" opacity="0.25" />}
    </svg>
  );
}

// Map role names to geometry components
export const ROLE_GEOMETRY: Record<string, {
  Component: React.ComponentType<IconProps & { active?: boolean }>;
  animationClass: string;
  label: string;
}> = {
  FundamentalAnalyst: { Component: GeoOctahedron,   animationClass: "shape-researcher",   label: "Octahedron" },
  TechnicalAnalyst:   { Component: GeoCylinder,      animationClass: "shape-analyst",      label: "Cylinder" },
  SentimentAnalyst:   { Component: GeoSphere,        animationClass: "shape-evaluator",    label: "Sphere" },
  MacroAnalyst:       { Component: GeoIcosahedron,   animationClass: "shape-orchestrator", label: "Icosahedron" },
  RiskManager:        { Component: GeoTorus,         animationClass: "shape-executor",     label: "Torus" },
  TraderAgent:        { Component: GeoCube,          animationClass: "shape-generator",    label: "Cube" },
};
