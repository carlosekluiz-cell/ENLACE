'use client';

import { useEffect, useRef } from 'react';

interface GeoCanvasProps {
  className?: string;
  variant?: 'hero' | 'subtle';
}

export default function GeoCanvas({ className = '', variant = 'hero' }: GeoCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const draw = () => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
      const w = rect.width;
      const h = rect.height;

      ctx.clearRect(0, 0, w, h);

      // Radial gradient background glow
      const grad = ctx.createRadialGradient(w * 0.6, h * 0.5, 0, w * 0.6, h * 0.5, w * 0.5);
      if (variant === 'hero') {
        grad.addColorStop(0, 'rgba(99,102,241,0.08)');
        grad.addColorStop(0.5, 'rgba(5,150,105,0.03)');
        grad.addColorStop(1, 'transparent');
      } else {
        grad.addColorStop(0, 'rgba(99,102,241,0.04)');
        grad.addColorStop(1, 'transparent');
      }
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      // Generate tower nodes in Brazil-shaped clusters (offset right)
      const nodes: Array<{ x: number; y: number; s: number; type: string }> = [];
      const density = variant === 'hero' ? 1 : 0.5;
      const clusters = [
        { cx: w * 0.7, cy: h * 0.2, r: 120, n: Math.floor(60 * density) },
        { cx: w * 0.8, cy: h * 0.4, r: 100, n: Math.floor(70 * density) },
        { cx: w * 0.65, cy: h * 0.55, r: 110, n: Math.floor(55 * density) },
        { cx: w * 0.6, cy: h * 0.7, r: 90, n: Math.floor(45 * density) },
        { cx: w * 0.5, cy: h * 0.8, r: 70, n: Math.floor(30 * density) },
      ];

      for (const c of clusters) {
        for (let i = 0; i < c.n; i++) {
          const a = Math.random() * Math.PI * 2;
          const r = Math.random() * c.r;
          const type = Math.random() > 0.75 ? 'opportunity' : 'tower';
          nodes.push({
            x: c.cx + Math.cos(a) * r,
            y: c.cy + Math.sin(a) * r,
            s: 1 + Math.random() * 2.5,
            type,
          });
        }
      }

      // Draw connections
      ctx.lineWidth = 0.4;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 50) {
            ctx.strokeStyle =
              a.type === 'opportunity' || b.type === 'opportunity'
                ? 'rgba(5,150,105,0.1)'
                : 'rgba(99,102,241,0.06)';
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // Draw nodes with glow
      for (const n of nodes) {
        const color =
          n.type === 'opportunity' ? 'rgba(52,211,153,0.7)' : 'rgba(129,140,248,0.5)';
        const glow =
          n.type === 'opportunity' ? 'rgba(5,150,105,0.15)' : 'rgba(99,102,241,0.08)';
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.s + 4, 0, Math.PI * 2);
        ctx.fillStyle = glow;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.s, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }
    };

    // Use a stable seed by drawing once
    draw();

    const handleResize = () => draw();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [variant]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
    />
  );
}
