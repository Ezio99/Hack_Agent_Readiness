import React from 'react';
import { C, F } from '../theme/tokens';

/** A floating browser window: quiet dark chrome, the page path in the address pill, an optional badge (e.g. "Recorded"). */
export const CHROME_H = 46;
export function BrowserWindow({ width, height, path, badge, children, style, site = 'Larkspur Community College' }: {
  width: number; height: number; path: string; site?: string; badge?: React.ReactNode; children: React.ReactNode; style?: React.CSSProperties;
}) {
  return <div style={{ position: 'absolute', width, height: height + CHROME_H, borderRadius: 16, overflow: 'hidden', background: C.sheet,
    boxShadow: '0 50px 140px rgba(0,0,0,.6), 0 12px 32px rgba(0,0,0,.35)', outline: `1px solid ${C.rule}`, ...style }}>
    <div style={{ height: CHROME_H, display: 'flex', alignItems: 'center', gap: 18, padding: '0 18px', background: '#161614', borderBottom: `1px solid ${C.rule}` }}>
      <div style={{ display: 'flex', gap: 8 }}>{[0, 1, 2].map(i => <span key={i} style={{ width: 11, height: 11, borderRadius: 6, background: 'rgba(237,234,227,.16)' }} />)}</div>
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <div style={{ minWidth: 360, padding: '6px 18px', borderRadius: 999, background: 'rgba(237,234,227,.06)', color: C.ink2, fontFamily: F.mono, fontSize: 15,
          textAlign: 'center', letterSpacing: '.01em' }}>{site}<span style={{ color: C.ink3 }}>{'  ·  '}{path}</span></div>
      </div>
      <div style={{ minWidth: 60, display: 'flex', justifyContent: 'flex-end' }}>{badge}</div>
    </div>
    <div style={{ position: 'relative', width, height, overflow: 'hidden', background: '#FBFAF6' }}>{children}</div>
  </div>;
}
