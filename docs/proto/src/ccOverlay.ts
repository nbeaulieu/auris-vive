interface Word {
  word: string;
  start: number;
  end: number;
}

interface Transcript {
  slug: string;
  language: string;
  words: Word[];
}

/**
 * CC overlay — shows synced lyrics from Whisper transcription.
 * Positioned above stem pills, large Cormorant Garamond text.
 */
export class CCOverlay {
  private words: Word[] = [];
  private enabled = false;
  private available = false;
  private el: HTMLElement;
  private btn: HTMLButtonElement;

  constructor() {
    // CC text display
    this.el = document.createElement('div');
    this.el.style.cssText = `
      position: fixed; bottom: 150px; left: 50%; transform: translateX(-50%);
      font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 300;
      color: #E8E0D5; text-align: center; z-index: 15;
      pointer-events: none; opacity: 0; transition: opacity 0.3s ease;
      max-width: 80vw; letter-spacing: 0.02em;
    `;
    document.body.appendChild(this.el);

    // CC toggle button
    this.btn = document.createElement('button');
    this.btn.textContent = 'CC';
    this.btn.style.cssText = `
      display: none; position: fixed; bottom: 32px; right: 20px;
      background: rgba(123, 94, 167, 0.25); border: 1px solid rgba(123, 94, 167, 0.5);
      color: #E8E0D5; font-family: 'Jost', sans-serif; font-weight: 300;
      font-size: 12px; padding: 4px 10px; border-radius: 4px; cursor: pointer;
      letter-spacing: 0.08em; z-index: 20; transition: background 0.2s;
    `;
    this.btn.addEventListener('click', () => this.toggle());
    document.body.appendChild(this.btn);
  }

  async load(url: string): Promise<void> {
    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        this.available = false;
        this.btn.style.display = 'none';
        return;
      }
      const data = await resp.json() as Transcript;
      this.words = data.words;
      this.available = this.words.length > 0;
      this.btn.style.display = this.available ? 'block' : 'none';
    } catch {
      this.available = false;
      this.btn.style.display = 'none';
    }
  }

  toggle(): void {
    if (!this.available) return;
    this.enabled = !this.enabled;
    this.el.style.opacity = this.enabled ? '1' : '0';
    this.btn.style.background = this.enabled
      ? 'rgba(123, 94, 167, 0.5)'
      : 'rgba(123, 94, 167, 0.25)';
  }

  update(currentTime: number): void {
    if (!this.enabled || !this.available) return;

    // Find words active at currentTime (show up to 3)
    const active = this.words.filter(
      w => currentTime >= w.start - 0.1 && currentTime <= w.end + 0.2,
    );
    const visible = active.slice(-3);

    if (visible.length === 0) {
      this.el.textContent = '';
      return;
    }

    this.el.textContent = visible.map(w => w.word).join(' ');
  }
}
