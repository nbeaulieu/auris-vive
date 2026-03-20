import type { StemName, StemFrame } from './types';
import { Scene } from './scenes/base';

const SWIPE_THRESHOLD = 50;
const DOT_ACTIVE = '#C9A96E';
const DOT_INACTIVE = '#7B5EA7';

export class SceneManager {
  private currentIndex = 0;
  private scenes: Scene[];
  private canvas: HTMLCanvasElement;
  private dots: HTMLElement;

  // Swipe/drag state
  private touchStartX = 0;
  private dragStartX = 0;
  private isDragging = false;

  constructor(canvas: HTMLCanvasElement, scenes: Scene[]) {
    this.canvas = canvas;
    this.scenes = scenes;

    // Create dot indicators
    this.dots = document.createElement('div');
    this.dots.className = 'scene-dots';
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

  private bindSwipe(): void {
    // Touch
    this.canvas.addEventListener('touchstart', (e) => {
      this.touchStartX = e.touches[0].clientX;
    }, { passive: true });

    this.canvas.addEventListener('touchend', (e) => {
      const dx = e.changedTouches[0].clientX - this.touchStartX;
      if (Math.abs(dx) > SWIPE_THRESHOLD) {
        this.swipe(dx < 0 ? 'left' : 'right');
      }
    });

    // Mouse drag
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
    this.scenes[this.currentIndex].render(frames, ctx, w, h, elapsed);
  }
}
