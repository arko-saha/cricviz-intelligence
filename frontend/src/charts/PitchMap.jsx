import { useState, useMemo, useRef, useCallback } from 'react';
import EmptyState from '../components/EmptyState';

// ═══════════════════════════════════════════════════════════════════════
// PITCH CONSTANTS — All measurements in metres, no magic pixel numbers
// ═══════════════════════════════════════════════════════════════════════
const PITCH_LENGTH_M = 20.12;   // stump to stump (66ft)
const PITCH_WIDTH_M  = 3.05;    // usable corridor (10ft)
const HALF_WIDTH     = PITCH_WIDTH_M / 2;   // 1.525m each side

// SVG canvas
const SVG_W  = 220;
const SVG_H  = 460;
const PAD_L  = 30;   // left padding for stump label
const PAD_T  = 20;   // top padding above pitch
const PAD_B  = 30;   // bottom padding below pitch
const PITCH_SVG_W = SVG_W - PAD_L - 20;  // ~170px
const PITCH_SVG_H = SVG_H - PAD_T - PAD_B;  // ~410px

// Coordinate transform helpers
// Y: 0 = batting crease (bottom of SVG), PITCH_LENGTH_M = bowling crease (top of SVG)
const metreToSvgX = (mX) =>
  PAD_L + ((mX + HALF_WIDTH) / PITCH_WIDTH_M) * PITCH_SVG_W;

const metreToSvgY = (mY) =>
  PAD_T + (1 - mY / PITCH_LENGTH_M) * PITCH_SVG_H;

// Stump X positions (metres from centre)
const OFF_STUMP_M   =  0.114;
const MID_STUMP_M   =  0.0;
const LEG_STUMP_M   = -0.114;

// Crease Y positions (metres from batting crease)
const BATTING_CREASE_M = 0.0;
const POPPING_CREASE_M = 1.22;    // 4ft ahead of batting crease
const BOWLING_CREASE_M = PITCH_LENGTH_M;  // at the bowling end

// ═══════════════════════════════════════════════════════════════════════
// LENGTH ZONE DEFINITIONS — Y range in metres from batting crease
// canonical centre used for jitter fallback
// ═══════════════════════════════════════════════════════════════════════
const LENGTH_ZONES = {
  YORKER:      { min: 0.0,  max: 1.8,  centre: 0.9  },
  FULL:        { min: 1.8,  max: 4.0,  centre: 2.9  },
  GOOD_LENGTH: { min: 4.0,  max: 6.5,  centre: 5.25 },
  SHORT:       { min: 6.5,  max: 8.5,  centre: 7.5  },
  BOUNCER:     { min: 8.5,  max: 10.0, centre: 9.25 },
};

// Width zone canonical X centres (metres from centre)
const LINE_ZONES = {
  WIDE_OUTSIDE_OFF: 1.2,
  OUTSIDE_OFF:      0.6,
  OFF_STUMP:        0.114,
  MIDDLE_STUMP:     0.0,
  LEG_STUMP:       -0.114,
  OUTSIDE_LEG:     -0.6,
};

// ═══════════════════════════════════════════════════════════════════════
// DETERMINISTIC JITTER — seeded from delivery id string
// Using a simple hash so the same delivery always lands at same pixel
// ═══════════════════════════════════════════════════════════════════════
function seededRandom(seed) {
  // Simple Mulberry32 seeded from string hash
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (Math.imul(31, h) + seed.charCodeAt(i)) | 0;
  }
  return () => {
    h += 0x6D2B79F5;
    let t = Math.imul(h ^ (h >>> 15), h | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const JITTER_M = 0.15; // ±0.15m jitter range

function getDeliveryCoords(delivery) {
  // Prefer real pitch_map coordinates if available
  if (delivery.pitch_map_x != null && delivery.pitch_map_y != null) {
    const mX = Math.max(-HALF_WIDTH, Math.min(HALF_WIDTH, delivery.pitch_map_x));
    const mY = Math.max(0, Math.min(PITCH_LENGTH_M, delivery.pitch_map_y));
    if (mX !== delivery.pitch_map_x || mY !== delivery.pitch_map_y) {
      console.warn(`[PitchMap] Delivery ${delivery.id} coords clamped to pitch bounds.`);
    }
    return { mX, mY };
  }

  // Fall back to zone-centre + deterministic jitter
  const zone = LENGTH_ZONES[delivery.pitch_zone];
  const lineX = LINE_ZONES[delivery.pitch_zone] ?? LINE_ZONES['MIDDLE_STUMP'];

  const centreY = zone ? zone.centre : 5.0;
  const centreX = LINE_ZONES[delivery.pitch_zone] !== undefined
    ? LINE_ZONES[delivery.pitch_zone]
    : 0;

  const rng = seededRandom(String(delivery.id ?? delivery.over + '_' + delivery.ball));
  const jX = (rng() - 0.5) * 2 * JITTER_M;
  const jY = (rng() - 0.5) * 2 * JITTER_M;

  return {
    mX: Math.max(-HALF_WIDTH, Math.min(HALF_WIDTH, centreX + jX)),
    mY: Math.max(0, Math.min(PITCH_LENGTH_M, centreY + jY)),
  };
}

// ═══════════════════════════════════════════════════════════════════════
// xW HEAT SCALE — continuous interpolation, not discrete buckets
// Low xW → cool blue (#1e40af), Mid → teal (#0d9488), High → red (#dc2626)
// ═══════════════════════════════════════════════════════════════════════
function lerp(a, b, t) { return a + (b - a) * t; }

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return [r,g,b];
}

const HEAT_STOPS = [
  { t: 0.0,  rgb: hexToRgb('#1e40af') },  // cool blue
  { t: 0.4,  rgb: hexToRgb('#0d9488') },  // teal
  { t: 0.75, rgb: hexToRgb('#f59e0b') },  // amber
  { t: 1.0,  rgb: hexToRgb('#dc2626') },  // red
];

function xwToColor(xw, allXw) {
  // Normalize within the dataset range for contrast — if all same value use 0.5
  const min = allXw.min ?? 0;
  const max = allXw.max ?? 0.2;
  const t = max === min ? 0.5 : Math.max(0, Math.min(1, (xw - min) / (max - min)));

  let lo = HEAT_STOPS[0], hi = HEAT_STOPS[HEAT_STOPS.length - 1];
  for (let i = 0; i < HEAT_STOPS.length - 1; i++) {
    if (t >= HEAT_STOPS[i].t && t <= HEAT_STOPS[i+1].t) {
      lo = HEAT_STOPS[i]; hi = HEAT_STOPS[i+1]; break;
    }
  }
  const seg = hi.t === lo.t ? 0.5 : (t - lo.t) / (hi.t - lo.t);
  const [r,g,b] = lo.rgb.map((c,i) => Math.round(lerp(c, hi.rgb[i], seg)));
  return `rgb(${r},${g},${b})`;
}

// xW colour for gradient bar (absolute scale 0→1)
function xwToColorAbsolute(t) {
  let lo = HEAT_STOPS[0], hi = HEAT_STOPS[HEAT_STOPS.length - 1];
  for (let i = 0; i < HEAT_STOPS.length - 1; i++) {
    if (t >= HEAT_STOPS[i].t && t <= HEAT_STOPS[i+1].t) {
      lo = HEAT_STOPS[i]; hi = HEAT_STOPS[i+1]; break;
    }
  }
  const seg = hi.t === lo.t ? 0.5 : (t - lo.t) / (hi.t - lo.t);
  const [r,g,b] = lo.rgb.map((c,i) => Math.round(lerp(c, hi.rgb[i], seg)));
  return `rgb(${r},${g},${b})`;
}

// Build CSS gradient stops for the legend
function buildGradient() {
  return HEAT_STOPS.map(s => `${xwToColorAbsolute(s.t)} ${(s.t * 100).toFixed(0)}%`).join(', ');
}

// ═══════════════════════════════════════════════════════════════════════
// DANGER ZONE — Good Length + Off Stump
// ═══════════════════════════════════════════════════════════════════════
function isDangerZone(d) {
  return d.pitch_zone === 'GOOD_LENGTH';
}

// ═══════════════════════════════════════════════════════════════════════
// PITCH MAP COMPONENT
// ═══════════════════════════════════════════════════════════════════════
export default function PitchMap({ deliveries = [] }) {
  const [hoveredId, setHoveredId] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [bowlerFilter, setBowlerFilter] = useState('ALL'); // ALL | PACE | SPIN
  const svgRef = useRef(null);

  // ── Edge case: no data ───────────────────────────────────────────────
  if (!deliveries || deliveries.length === 0) {
    return <EmptyState icon="🎯" title="No Pitch Data" description="Pitch zone data is not available for this match." />;
  }

  // ── Bowler type detection ────────────────────────────────────────────
  const bowlerTypes = useMemo(() => {
    const types = new Set(deliveries.map(d => d.bowler_type ?? 'PACE'));
    return types;
  }, [deliveries]);

  const showFilterButtons = bowlerTypes.size > 1;

  // ── Filter deliveries ────────────────────────────────────────────────
  const filteredDeliveries = useMemo(() => {
    if (bowlerFilter === 'ALL') return deliveries;
    return deliveries.filter(d => (d.bowler_type ?? 'PACE') === bowlerFilter);
  }, [deliveries, bowlerFilter]);

  // ── Compute xW range for heat scale ─────────────────────────────────
  const xwRange = useMemo(() => {
    if (!filteredDeliveries.length) return { min: 0, max: 0.2 };
    const vals = filteredDeliveries.map(d => d.xW ?? 0);
    return { min: Math.min(...vals), max: Math.max(...vals) };
  }, [filteredDeliveries]);

  // ── Compute dot positions ─────────────────────────────────────────────
  const dots = useMemo(() => filteredDeliveries.map(d => {
    const { mX, mY } = getDeliveryCoords(d);
    return {
      id: d.id,
      svgX: metreToSvgX(mX),
      svgY: metreToSvgY(mY),
      color: xwToColor(d.xW ?? 0, xwRange),
      delivery: d,
    };
  }), [filteredDeliveries, xwRange]);

  // ── Danger zone stats (live from filtered dots) ───────────────────────
  const dangerStats = useMemo(() => {
    const danger = filteredDeliveries.filter(isDangerZone);
    if (!danger.length) return null;
    const avgXW = danger.reduce((s,d) => s + (d.xW ?? 0), 0) / danger.length;
    const avgXR = danger.reduce((s,d) => s + (d.xR ?? 0), 0) / danger.length;
    return { count: danger.length, avgXW, avgXR };
  }, [filteredDeliveries]);

  // ── SVG zone boundary lines (derived from constants, not eyeballed) ──
  const zoneBoundaryYs = Object.values(LENGTH_ZONES).map(z => ({
    label: null,
    svgY: metreToSvgY(z.min),
  }));

  // ── Tooltip handler ──────────────────────────────────────────────────
  const handleMouseEnter = useCallback((dot, e) => {
    setHoveredId(dot.id);
    const d = dot.delivery;
    setTooltip({
      svgX: dot.svgX,
      svgY: dot.svgY,
      text: [
        `Over ${d.over}.${d.ball}  ${d.bowler} → ${d.batter}`,
        `Zone: ${d.pitch_zone ?? '—'}`,
        `xR: ${(d.xR ?? 0).toFixed(2)}  xW: ${(d.xW ?? 0).toFixed(3)}  ${d.shot_intent ?? ''}`,
        `False shot: ${d.is_false_shot ? 'Yes' : 'No'}`,
      ],
    });
  }, []);

  const handleMouseLeave = useCallback(() => {
    setHoveredId(null);
    setTooltip(null);
  }, []);

  // ── Pitch SVG drawing coords ─────────────────────────────────────────
  const pitchLeft   = metreToSvgX(-HALF_WIDTH);
  const pitchRight  = metreToSvgX( HALF_WIDTH);
  const pitchTop    = metreToSvgY(PITCH_LENGTH_M);
  const pitchBottom = metreToSvgY(0);

  const svgOffStumpX   = metreToSvgX(OFF_STUMP_M);
  const svgMidStumpX   = metreToSvgX(MID_STUMP_M);
  const svgLegStumpX   = metreToSvgX(LEG_STUMP_M);
  const svgBattingY    = metreToSvgY(BATTING_CREASE_M);
  const svgPoppingY    = metreToSvgY(POPPING_CREASE_M);
  const svgBowlingY    = metreToSvgY(BOWLING_CREASE_M);

  return (
    <div className="card" style={{ minWidth: 0 }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <span className="card-title">Pitch Map</span>
          <div style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
            marginTop: '2px',
            maxWidth: '280px',
            lineHeight: 1.4,
          }}>
            Delivery landing coordinates coloured by xW
            <br />
            <span style={{ color: '#dc2626' }}>darker red</span> = higher wicket probability
          </div>
        </div>

        {/* Bowler filter */}
        {showFilterButtons && (
          <div style={{ display: 'flex', gap: 'var(--space-1)', marginLeft: 'var(--space-2)' }}>
            {['ALL', 'PACE', 'SPIN'].map(f => (
              <button
                key={f}
                onClick={() => setBowlerFilter(f)}
                style={{
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  border: '1px solid',
                  borderColor: bowlerFilter === f ? 'var(--accent-teal)' : 'var(--border-default)',
                  background: bowlerFilter === f ? 'rgba(20,184,166,0.15)' : 'transparent',
                  color: bowlerFilter === f ? 'var(--accent-teal)' : 'var(--text-secondary)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {f}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── SVG Pitch ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--space-3) 0', position: 'relative' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          width={SVG_W}
          height={SVG_H}
          style={{ overflow: 'visible' }}
        >
          <defs>
            {/* Pitch grain texture */}
            <pattern id="pitchGrain" patternUnits="userSpaceOnUse" width="4" height="4">
              <path d="M0,4 L4,0" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            </pattern>
            {/* Pulse animation for hovered dot */}
            <style>{`
              @keyframes pitchPulse {
                0%   { r: 6; opacity: 0.8; }
                50%  { r: 10; opacity: 0.3; }
                100% { r: 6; opacity: 0.8; }
              }
              .pulse-ring { animation: pitchPulse 1.2s ease-in-out infinite; }
            `}</style>
          </defs>

          {/* Pitch surface */}
          <rect
            x={pitchLeft} y={pitchTop}
            width={pitchRight - pitchLeft}
            height={pitchBottom - pitchTop}
            fill="#1a2e1a"
            rx="4"
          />
          {/* Grain texture overlay */}
          <rect
            x={pitchLeft} y={pitchTop}
            width={pitchRight - pitchLeft}
            height={pitchBottom - pitchTop}
            fill="url(#pitchGrain)"
            rx="4"
          />

          {/* Zone boundary lines */}
          {Object.entries(LENGTH_ZONES).map(([name, zone]) => {
            const y = metreToSvgY(zone.min);
            if (y < pitchTop - 2 || y > pitchBottom + 2) return null;
            return (
              <g key={name}>
                <line
                  x1={pitchLeft} y1={y}
                  x2={pitchRight} y2={y}
                  stroke="rgba(255,255,255,0.2)"
                  strokeWidth="0.5"
                />
                <text
                  x={pitchLeft - 4}
                  y={y + (name === 'BOUNCER' ? 8 : 0)}
                  textAnchor="end"
                  fill="rgba(255,255,255,0.35)"
                  fontSize="7"
                  fontFamily="var(--font-mono)"
                  dominantBaseline="middle"
                >
                  {name.replace('_',' ').replace('_',' ')}
                </text>
              </g>
            );
          })}

          {/* Batting crease */}
          <line
            x1={pitchLeft} y1={svgBattingY}
            x2={pitchRight} y2={svgBattingY}
            stroke="#ffffff" strokeWidth="1.5"
          />
          {/* Popping crease */}
          <line
            x1={pitchLeft} y1={svgPoppingY}
            x2={pitchRight} y2={svgPoppingY}
            stroke="#ffffff" strokeWidth="1.5"
          />
          {/* Bowling crease */}
          <line
            x1={pitchLeft} y1={svgBowlingY}
            x2={pitchRight} y2={svgBowlingY}
            stroke="#ffffff" strokeWidth="1.5"
          />

          {/* Stump lines */}
          {[svgOffStumpX, svgMidStumpX, svgLegStumpX].map((sx, i) => (
            <line
              key={i}
              x1={sx} y1={pitchTop}
              x2={sx} y2={pitchBottom}
              stroke="rgba(255,255,255,0.55)"
              strokeWidth="1"
              strokeDasharray="4 3"
            />
          ))}

          {/* Stump labels at batting end */}
          <text x={svgOffStumpX} y={svgBattingY + 11} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="7" fontFamily="var(--font-mono)">Off</text>
          <text x={svgMidStumpX} y={svgBattingY + 11} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="7" fontFamily="var(--font-mono)">Mid</text>
          <text x={svgLegStumpX} y={svgBattingY + 11} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="7" fontFamily="var(--font-mono)">Leg</text>

          {/* Delivery dots */}
          {dots.map(dot => {
            const isHovered = hoveredId === dot.id;
            return (
              <g key={dot.id}
                onMouseEnter={e => handleMouseEnter(dot, e)}
                onMouseLeave={handleMouseLeave}
                style={{ cursor: 'pointer' }}
              >
                {/* Pulse ring on hover */}
                {isHovered && (
                  <circle
                    className="pulse-ring"
                    cx={dot.svgX}
                    cy={dot.svgY}
                    r={6}
                    fill="none"
                    stroke={dot.color}
                    strokeWidth="1.5"
                    opacity="0.5"
                  />
                )}
                <circle
                  cx={dot.svgX}
                  cy={dot.svgY}
                  r={isHovered ? 6 : 4}
                  fill={dot.color}
                  fillOpacity={isHovered ? 1.0 : 0.70}
                  stroke="#ffffff"
                  strokeWidth="0.8"
                />
              </g>
            );
          })}

          {/* SVG tooltip */}
          {tooltip && (() => {
            const lines = tooltip.text;
            const boxW = 200;
            const boxH = lines.length * 14 + 12;
            // Flip left if near right edge
            const rawX = tooltip.svgX + 10;
            const bx = rawX + boxW > SVG_W ? tooltip.svgX - boxW - 10 : rawX;
            const by = Math.max(pitchTop, Math.min(tooltip.svgY - boxH / 2, pitchBottom - boxH));
            return (
              <g style={{ pointerEvents: 'none' }}>
                <rect x={bx} y={by} width={boxW} height={boxH}
                  fill="var(--bg-elevated)" stroke="var(--accent-teal)"
                  strokeWidth="1" rx="4" opacity="0.97" />
                {lines.map((line, i) => (
                  <text
                    key={i}
                    x={bx + 8}
                    y={by + 10 + i * 14}
                    fill={i === 0 ? 'var(--text-primary)' : 'var(--text-secondary)'}
                    fontSize={i === 0 ? '9.5' : '8.5'}
                    fontWeight={i === 0 ? '600' : '400'}
                    fontFamily="var(--font-mono)"
                    dominantBaseline="hanging"
                  >
                    {line}
                  </text>
                ))}
              </g>
            );
          })()}
        </svg>
      </div>

      {/* ── xW colour legend bar ────────────────────────────────────── */}
      <div style={{ padding: '0 var(--space-4) var(--space-2)' }}>
        <div style={{
          height: '8px',
          borderRadius: '4px',
          background: `linear-gradient(to right, ${buildGradient()})`,
          marginBottom: '4px',
        }} />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '10px',
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
        }}>
          <span style={{ color: '#1e40af' }}>xW 0.0 (safe)</span>
          <span style={{ color: '#0d9488' }}>0.05</span>
          <span style={{ color: '#f59e0b' }}>0.10</span>
          <span style={{ color: '#dc2626' }}>0.20+ (danger)</span>
        </div>
      </div>

      {/* ── Danger zone stat ────────────────────────────────────────── */}
      <div style={{
        margin: '0 var(--space-4) var(--space-3)',
        padding: 'var(--space-2) var(--space-3)',
        background: 'rgba(220,38,38,0.07)',
        border: '1px solid rgba(220,38,38,0.25)',
        borderRadius: 'var(--radius-sm)',
        fontSize: '11px',
        fontFamily: 'var(--font-mono)',
        color: 'var(--text-secondary)',
        lineHeight: 1.5,
      }}>
        {dangerStats ? (
          <>
            <span style={{ color: '#dc2626', fontWeight: 600 }}>⚠ Good Length: </span>
            {dangerStats.count} deliveries &nbsp;·&nbsp;
            avg xW <span style={{ color: '#f59e0b' }}>{dangerStats.avgXW.toFixed(3)}</span> &nbsp;·&nbsp;
            avg xR <span style={{ color: 'var(--accent-teal)' }}>{dangerStats.avgXR.toFixed(2)}</span>
          </>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>No deliveries in danger zone</span>
        )}
      </div>
    </div>
  );
}
