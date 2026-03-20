import type { CurvesData, StemName } from './types';
import { AudioEngine } from './audio';
import { CurvePlayer } from './curvePlayer';
import { SceneManager } from './sceneManager';
import { WaveScene } from './scenes/waveScene';
import { GardenScene } from './scenes/gardenScene';
import { CCOverlay } from './ccOverlay';

const STEM_NAMES: StemName[] = ['drums', 'bass', 'vocals', 'other', 'piano', 'guitar'];

let audio: AudioEngine;
let curvePlayer: CurvePlayer | null = null;
let sceneManager: SceneManager | null = null;
let ccOverlay: CCOverlay | null = null;
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
  try {
    const resp = await fetch('data/index.json');
    if (resp.ok) {
      return await resp.json() as string[];
    }
  } catch { /* fall through */ }
  return [];
}

async function loadSong(slug: string): Promise<void> {
  status.textContent = `Loading ${slug}…`;
  playBtn.disabled = true;

  if (audio?.playing) audio.pause();

  const curvesResp = await fetch(`data/${slug}/curves.json`);
  if (!curvesResp.ok) {
    status.textContent = `Failed to load curves for ${slug}`;
    return;
  }
  const curvesData = await curvesResp.json() as CurvesData;

  // Load stems if available, otherwise fall back to mix
  if (curvesData.stems_available) {
    await audio.loadStems(`data/${slug}/stems`, STEM_NAMES);
    // If stem loading failed, loadStems falls back internally — load mix as backup
    if (audio.mode !== 'stems') {
      await audio.load(`data/${slug}/audio.mp3`);
    }
  } else {
    await audio.load(`data/${slug}/audio.mp3`);
  }

  curvePlayer = new CurvePlayer(curvesData);

  if (!sceneManager) {
    sceneManager = new SceneManager(canvas, [
      new WaveScene(),
      new GardenScene(),
    ], (stem, enabled) => {
      audio.setStemGain(stem, enabled ? 1 : 0);
    });
  }

  if (!ccOverlay) {
    ccOverlay = new CCOverlay();
  }
  await ccOverlay.load(`data/${slug}/transcript.json`);

  startTime = 0;
  playBtn.disabled = false;
  playBtn.textContent = '▶ Play';
  status.textContent = `${curvesData.slug}${audio.mode === 'stems' ? ' [stems]' : ''}`;
}

function tick(): void {
  if (curvePlayer && sceneManager) {
    const t = audio.currentTime;
    const frames = curvePlayer.frameAt(t);
    const elapsed = audio.playing ? t : startTime;
    sceneManager.render(frames, elapsed);
    ccOverlay?.update(t);
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

  await loadSong(slugs[0]);
  requestAnimationFrame(tick);
}

init();
