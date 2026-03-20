export class AudioEngine {
  private ctx!:   AudioContext;
  private source: AudioBufferSourceNode | null = null;
  private buffer: AudioBuffer | null = null;
  private startedAt = 0;
  private offset    = 0;
  private _playing  = false;

  async load(url: string): Promise<void> {
    this.stop();
    this.ctx = new AudioContext();
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    this.buffer = await this.ctx.decodeAudioData(arrayBuffer);
    this.offset = 0;
  }

  play(): void {
    if (!this.buffer || this._playing) return;
    this.source = this.ctx.createBufferSource();
    this.source.buffer = this.buffer;
    this.source.connect(this.ctx.destination);
    this.source.start(0, this.offset);
    this.startedAt = this.ctx.currentTime - this.offset;
    this._playing = true;
    this.source.onended = () => { this._playing = false; };
  }

  pause(): void {
    if (!this._playing) return;
    this.offset = this.currentTime;
    this.source?.stop();
    this._playing = false;
  }

  private stop(): void {
    if (this._playing) {
      this.source?.stop();
      this._playing = false;
    }
    this.offset = 0;
  }

  get currentTime(): number {
    if (this._playing) return this.ctx.currentTime - this.startedAt;
    return this.offset;
  }

  get playing(): boolean { return this._playing; }
}
