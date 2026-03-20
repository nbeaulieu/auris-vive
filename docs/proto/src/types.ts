export type StemName = 'drums' | 'bass' | 'vocals' | 'other' | 'piano' | 'guitar';

export interface StemFrame {
  energy:      number;
  brightness:  number;
  onset:       number;
  warmth:      number;
  texture:     number;
  flux:        number;
  pitch_curve: number;
}

export interface CurvesData {
  slug:             string;
  duration_s:       number;
  frame_rate:       number;
  n_frames:         number;
  stems:            Record<StemName, Record<keyof StemFrame, number[]>>;
  stems_available?: boolean;
}
