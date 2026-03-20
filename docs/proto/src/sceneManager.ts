import type { StemName, StemFrame } from './types';
import { Scene } from './scenes/base';

const SWIPE_THRESHOLD = 50;
const DOT_ACTIVE = '#C9A96E';
const DOT_INACTIVE = '#7B5EA7';

const STEM_PILLS: { stem: StemName; label: string; color: string }[] = [
  { stem: 'drums',  label: 'DRUMS',  color: '#7B5EA7' },
  { stem: 'bass',   label: 'BASS',   color: '#5B8A6E' },
  { stem: 'vocals', label: 'VOCALS', color: '#C9A96E' },
  { stem: 'other',  label: 'OTHER',  color: '#A084C8' },
  { stem: 'piano',  label: 'PIANO',  color: '#FFD700' },
  { stem: 'guitar', label: 'GUITAR', color: '#00CED1' },
];

export class SceneManager {
  private currentIndex = 0;
  private scenes: Scene[];
  private canvas: HTMLCanvasElement;
  private dots: HTMLElement;
  private stemEnabled: Record<StemName, boolean> = {
    drums: true, bass: true, vocals: true, other: true, piano: true, guitar: true,
  };
  private pillEls: Map<StemName, HTMLElement> = new Map();
  private onStemToggle: ((stem: StemName, enabled: boolean) => void) | null = null;

  // Swipe/drag state
  private touchStartX = 0;
  private dragStartX = 0;
  private isDragging = false;

  constructor(canvas: HTMLCanvasElement, scenes: Scene[], onStemToggle?: (stem: StemName, enabled: boolean) => void) {
    this.onStemToggle = onStemToggle ?? null;
    this.canvas = canvas;
    this.scenes = scenes;

    // ── Stem toggle pills ─────────────────────────────────────────────
    const pillBar = document.createElement('div');
    pillBar.style.cssText = `
      position: fixed; bottom: 100px; left: 50%; transform: translateX(-50%);
      display: flex; gap: 8px; z-index: 20; flex-wrap: wrap; justify-content: center;
    `;
    document.body.appendChild(pillBar);

    for (const { stem, label, color } of STEM_PILLS) {
      const pill = document.createElement('button');
      pill.textContent = label;
      pill.style.cssText = `
        border-radius: 20px; padding: 6px 14px; cursor: pointer;
        font-family: 'Jost', sans-serif; font-size: 11px; font-weight: 300;
        letter-spacing: 0.1em; transition: all 0.2s ease;
        background: ${color}cc; color: #fff; border: 1.5px solid ${color};
      `;
      pill.addEventListener('click', () => {
        this.stemEnabled[stem] = !this.stemEnabled[stem];
        this.updatePill(stem, color);
        this.onStemToggle?.(stem, this.stemEnabled[stem]);
      });
      pillBar.appendChild(pill);
      this.pillEls.set(stem, pill);
    }

    // ── Dot indicators ────────────────────────────────────────────────
    this.dots = document.createElement('div');
    this.dots.style.cssText = `
      position: fixed; bottom: 72px; left: 50%; transform: translateX(-50%);
      display: flex; gap: 10px; z-index: 20;
    `;
    document.body.appendChild(this.dots);

    for (let i = 0; i < scenes.length; i++) {
      const dot = document.createElement('span');
      dot.style.cssText = `
        width: 10px; height: 10px; border-radius: 50%; cursor: pointer;
        border: 1.5px solid ${DOT_INACTIVE}; transition: all 0.3s ease;
      `;
      dot.addEventListener('click', () => this.goTo(i));
      this.dots.appendChild(dot);
    }

    this.updateDots();
    this.bindSwipe();
    this.scenes[0].mount(canvas);
  }

  private updatePill(stem: StemName, color: string): void {
    const pill = this.pillEls.get(stem);
    if (!pill) return;
    if (this.stemEnabled[stem]) {
      pill.style.background = `${color}cc`;
      pill.style.color = '#fff';
    } else {
      pill.style.background = 'transparent';
      pill.style.color = `${color}99`;
    }
  }

  private bindSwipe(): void {
    this.canvas.addEventListener('touchstart', (e) => {
      this.touchStartX = e.touches[0].clientX;
    }, { passive: true });

    this.canvas.addEventListener('touchend', (e) => {
      const dx = e.changedTouches[0].clientX - this.touchStartX;
      if (Math.abs(dx) > SWIPE_THRESHOLD) {
        this.swipe(dx < 0 ? 'left' : 'right');
      }
    });

    this.canvas.addEventListener('mousedown', (e) => {
      this.dragStartX = e.clientX;
      this.isDragging = true;
    });

    this.canvas.addEventListener('mouseup', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.dragStartX;
      if (Math.abs(dx) > SWIPE_THRESHOLD) {
        this.swipe(dx < 0 ? 'left' : 'right');
      }
      this.isDragging = false;
    });
  }

  swipe(direction: 'left' | 'right'): void {
    const next = direction === 'left'
      ? Math.min(this.currentIndex + 1, this.scenes.length - 1)
      : Math.max(this.currentIndex - 1, 0);
    if (next !== this.currentIndex) this.goTo(next);
  }

  goTo(index: number): void {
    if (index === this.currentIndex || index < 0 || index >= this.scenes.length) return;
    this.scenes[this.currentIndex].unmount();
    this.currentIndex = index;
    this.scenes[this.currentIndex].mount(this.canvas);
    this.updateDots();
  }

  private updateDots(): void {
    const children = this.dots.children;
    for (let i = 0; i < children.length; i++) {
      const dot = children[i] as HTMLElement;
      if (i === this.currentIndex) {
        dot.style.background = DOT_ACTIVE;
        dot.style.borderColor = DOT_ACTIVE;
      } else {
        dot.style.background = 'transparent';
        dot.style.borderColor = DOT_INACTIVE;
      }
    }
  }

  render(frames: Record<StemName, StemFrame>, elapsed: number): void {
    const ctx = this.canvas.getContext('2d')!;
    const w = this.canvas.width;
    const h = this.canvas.height;
    this.scenes[this.currentIndex].render(frames, ctx, w, h, elapsed, this.stemEnabled);
  }
}
