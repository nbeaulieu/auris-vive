import type { CurvesData, StemName } from './types';
import { AudioEngine } from './audio';
import { CurvePlayer } from './curvePlayer';
import { CanvasRenderer } from './renderer';
import { WaveRenderer } from './renderers/wave';
import { STEM_COLOURS } from './palette';

const STEM_ORDER: StemName[] = ['drums', 'bass', 'vocals', 'other', 'piano', 'guitar'];

let audio: AudioEngine;
let curvePlayer: CurvePlayer | null = null;
let canvasRenderer: CanvasRenderer | null = null;
let startTime = 0;

const canvas  = document.getElementById('canvas') as HTMLCanvasElement;
const playBtn = document.getElementById('play-btn') as HTMLButtonElement;
const songSel = document.getElementById('song-select') as HTMLSelectElement;
const status  = document.getElementById('status') as HTMLElement;

function resizeCanvas(): void {
  canvas.width  = window.innerWidth * devicePixelRatio;
  canvas.height = window.innerHeight * devicePixelRatio;
  canvas.style.width  = window.innerWidth + 'px';
  canvas.style.height = window.innerHeight + 'px';
}

async function discoverSlugs(): Promise<string[]> {
  // Discover available songs by fetching a manifest or trying known slugs.
  // We'll try to fetch an index file first; if absent, fall back to songs.json slugs.
  try {
    const resp = await fetch('data/index.json');
    if (resp.ok) {
      return await resp.json() as string[];
    }
  } catch { /* fall through */ }

  // Fallback: try known slugs from the select options already in HTML
  // This path won't be hit in practice — export-curves.py writes index.json
  return [];
}

async function loadSong(slug: string): Promise<void> {
  status.textContent = `Loading ${slug}…`;
  playBtn.disabled = true;

  // Stop current playback
  if (audio?.playing) audio.pause();

  const curvesResp = await fetch(`data/${slug}/curves.json`);
  if (!curvesResp.ok) {
    status.textContent = `Failed to load curves for ${slug}`;
    return;
  }
  const curvesData = await curvesResp.json() as CurvesData;

  await audio.load(`data/${slug}/audio.mp3`);

  curvePlayer = new CurvePlayer(curvesData);

  const renderers = STEM_ORDER.map(
    stem => new WaveRenderer(stem, STEM_COLOURS[stem]),
  );
  canvasRenderer = new CanvasRenderer(canvas, renderers);

  startTime = 0;
  playBtn.disabled = false;
  playBtn.textContent = '▶ Play';
  status.textContent = curvesData.slug;
}

function tick(): void {
  if (curvePlayer && canvasRenderer) {
    const t = audio.currentTime;
    const frames = curvePlayer.frameAt(t);
    const elapsed = audio.playing ? t : startTime;
    canvasRenderer.render(frames, elapsed);
  }
  requestAnimationFrame(tick);
}

async function init(): Promise<void> {
  audio = new AudioEngine();
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  const slugs = await discoverSlugs();
  if (slugs.length === 0) {
    status.textContent = 'No songs found — run export-curves.py first';
    return;
  }

  // Populate selector
  songSel.innerHTML = '';
  for (const slug of slugs) {
    const opt = document.createElement('option');
    opt.value = slug;
    opt.textContent = slug;
    songSel.appendChild(opt);
  }

  songSel.addEventListener('change', () => {
    loadSong(songSel.value);
  });

  playBtn.addEventListener('click', () => {
    if (!curvePlayer) return;
    if (audio.playing) {
      audio.pause();
      playBtn.textContent = '▶ Play';
    } else {
      audio.play();
      startTime = performance.now() / 1000;
      playBtn.textContent = '⏸ Pause';
    }
  });

  // Load first song
  await loadSong(slugs[0]);

  // Start render loop
  requestAnimationFrame(tick);
}

init();
