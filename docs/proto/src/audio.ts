interface StemChannel {
  buffer: AudioBuffer;
  source: AudioBufferSourceNode | null;
  gain: GainNode;
}

export class AudioEngine {
  private ctx!: AudioContext;

  // Mix mode (single track)
  private mixSource: AudioBufferSourceNode | null = null;
  private mixBuffer: AudioBuffer | null = null;

  // Stems mode (6 tracks)
  private stems: Map<string, StemChannel> = new Map();

  private startedAt = 0;
  private offset = 0;
  private _playing = false;
  private _mode: 'mix' | 'stems' = 'mix';

  /** Load a single mixed audio file (existing behaviour). */
  async load(url: string): Promise<void> {
    this.stop();
    this.ctx = new AudioContext();
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    this.mixBuffer = await this.ctx.decodeAudioData(arrayBuffer);
    this.stems.clear();
    this._mode = 'mix';
    this.offset = 0;
  }

  /** Load individual stem MP3s for synchronized multi-track playback. */
  async loadStems(baseUrl: string, stemNames: string[]): Promise<void> {
    this.stop();
    if (!this.ctx) this.ctx = new AudioContext();

    this.stems.clear();
    this._mode = 'stems';

    try {
      const results = await Promise.all(
        stemNames.map(async (name) => {
          const resp = await fetch(`${baseUrl}/${name}.mp3`);
          if (!resp.ok) throw new Error(`Failed to load ${name}.mp3`);
          const ab = await resp.arrayBuffer();
          const buffer = await this.ctx.decodeAudioData(ab);
          return { name, buffer };
        }),
      );

      for (const { name, buffer } of results) {
        const gain = this.ctx.createGain();
        gain.connect(this.ctx.destination);
        this.stems.set(name, { buffer, source: null, gain });
      }
    } catch (e) {
      // Fallback to mix mode — stems unavailable
      console.warn('Stem loading failed, falling back to mix mode:', e);
      this.stems.clear();
      this._mode = 'mix';
    }

    this.offset = 0;
  }

  play(): void {
    if (this._playing) return;

    if (this._mode === 'stems' && this.stems.size > 0) {
      this.playStemsMode();
    } else if (this.mixBuffer) {
      this.playMixMode();
    } else {
      return;
    }

    this._playing = true;
  }

  private playMixMode(): void {
    if (!this.mixBuffer) return;
    this.mixSource = this.ctx.createBufferSource();
    this.mixSource.buffer = this.mixBuffer;
    this.mixSource.connect(this.ctx.destination);
    this.mixSource.start(0, this.offset);
    this.startedAt = this.ctx.currentTime - this.offset;
    this.mixSource.onended = () => { this._playing = false; };
  }

  private playStemsMode(): void {
    // Start all stems simultaneously with a small lookahead for sync
    const startTime = this.ctx.currentTime + 0.05;

    for (const [, ch] of this.stems) {
      const src = this.ctx.createBufferSource();
      src.buffer = ch.buffer;
      src.connect(ch.gain);
      src.start(startTime, this.offset);
      ch.source = src;
    }

    this.startedAt = startTime - this.offset;

    // Use the first stem's source for onended
    const first = this.stems.values().next().value;
    if (first?.source) {
      first.source.onended = () => { this._playing = false; };
    }
  }

  pause(): void {
    if (!this._playing) return;
    this.offset = this.currentTime;

    if (this._mode === 'stems') {
      for (const [, ch] of this.stems) {
        ch.source?.stop();
        ch.source = null;
      }
    } else {
      this.mixSource?.stop();
    }

    this._playing = false;
  }

  private stop(): void {
    if (this._playing) {
      this.pause();
    }
    this.offset = 0;
  }

  /** Set gain for a single stem (0 = mute, 1 = unmute). No-op in mix mode. */
  setStemGain(stemName: string, gain: number): void {
    const ch = this.stems.get(stemName);
    if (ch) {
      ch.gain.gain.setTargetAtTime(gain, this.ctx.currentTime, 0.02);
    }
  }

  get currentTime(): number {
    if (this._playing) return this.ctx.currentTime - this.startedAt;
    return this.offset;
  }

  get playing(): boolean { return this._playing; }
  get mode(): 'mix' | 'stems' { return this._mode; }
}
