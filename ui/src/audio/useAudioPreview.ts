import { useCallback, useEffect, useRef, useState } from 'react';

import { meta } from '../data';
import type { Filter, FilterType } from '../data/types';

/**
 * Pink noise through the published filters, as a rough ear check.
 *
 * Rough is the operative word, and the UI says so: WebAudio runs at whatever
 * rate the output device is using -- usually 48 kHz, sometimes 44.1 -- while
 * these filters were designed and their headroom verified at 44.1 kHz. It also
 * uses the browser's own biquads rather than ours. It is here to let you hear
 * the tilt change as you move the slider, not to measure anything.
 */
const BIQUAD_TYPE: Record<FilterType, BiquadFilterType> = {
  'Low Shelf': 'lowshelf',
  'High Shelf': 'highshelf',
  Peak: 'peaking',
};

const NOISE_SECONDS = 4;

function pinkNoise(context: AudioContext): AudioBuffer {
  const buffer = context.createBuffer(1, context.sampleRate * NOISE_SECONDS, context.sampleRate);
  const data = buffer.getChannelData(0);
  // Paul Kellet's economy pink-noise filter: white noise through a bank of
  // one-pole sections, which lands within about 0.5 dB of -3 dB/octave.
  let b0 = 0;
  let b1 = 0;
  let b2 = 0;
  let b3 = 0;
  let b4 = 0;
  let b5 = 0;
  let b6 = 0;
  for (let i = 0; i < data.length; i += 1) {
    const white = Math.random() * 2 - 1;
    b0 = 0.99886 * b0 + white * 0.0555179;
    b1 = 0.99332 * b1 + white * 0.0750759;
    b2 = 0.969 * b2 + white * 0.153852;
    b3 = 0.8665 * b3 + white * 0.3104856;
    b4 = 0.55 * b4 + white * 0.5329522;
    b5 = -0.7616 * b5 - white * 0.016898;
    data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.05;
    b6 = white * 0.115926;
  }
  return buffer;
}

interface Graph {
  context: AudioContext;
  source: AudioBufferSourceNode;
  preamp: GainNode;
  bands: BiquadFilterNode[];
  /** The preamp each side of the comparison plays at, in dB. */
  gains: { filtered: number; flat: number };
  /** Mirrors the `bypassed` state, where callbacks can read it unstaled. */
  bypassed: boolean;
}

/**
 * A biquad slot per published band, allocated once and kept for the life of
 * the graph.
 *
 * Every served preset is either the pass-through, which has no filters at all,
 * or a full set of `bandCount` — so the slot count is a property of the data
 * rather than a guess. Allocating them up front is what lets the slider move
 * between any two levels while playing, including onto and off the reference
 * rung: a slot with nothing to do is set to 0 dB gain, which is unity for
 * every filter type here, instead of the graph being rebuilt or the update
 * being skipped.
 */
const BAND_SLOTS = meta.bandCount;

/** Write `filters` into the slots, neutralizing any the preset does not use. */
function applyFilters(bands: BiquadFilterNode[], filters: Filter[]): void {
  bands.forEach((node, i) => {
    const filter = filters[i];
    if (!filter) {
      // Both lines matter. A fresh BiquadFilterNode is a *lowpass* at 350 Hz,
      // and `gain` does nothing to a lowpass — leaving the type alone would
      // have made the pass-through preset the muffled one. A peaking section
      // at 0 dB is unity at every frequency, whatever its frequency and Q.
      node.type = 'peaking';
      node.gain.value = 0;
      return;
    }
    node.type = BIQUAD_TYPE[filter.type];
    node.frequency.value = filter.frequency;
    node.gain.value = filter.gain;
    node.Q.value = filter.q;
  });
}

export function useAudioPreview() {
  const graph = useRef<Graph | null>(null);
  const [playing, setPlaying] = useState(false);
  const [bypassed, setBypassed] = useState(false);
  const [sampleRate, setSampleRate] = useState<number | null>(null);

  const stop = useCallback(() => {
    const current = graph.current;
    graph.current = null;
    setPlaying(false);
    setBypassed(false);
    if (!current) {
      return;
    }
    current.source.stop();
    void current.context.close();
  }, []);

  const start = useCallback(
    (filters: Filter[], headroomDb: number, bypassDb: number) => {
    const context = new AudioContext();
    // iOS Safari can hand back a suspended context even when it was created
    // inside the click that asked for it, and a suspended context plays
    // nothing without complaining.
    void context.resume();
    const source = context.createBufferSource();
    source.buffer = pinkNoise(context);
    source.loop = true;

    const preamp = context.createGain();
    preamp.gain.value = 10 ** (headroomDb / 20);
    const gains = { filtered: headroomDb, flat: bypassDb };

    const bands = Array.from({ length: BAND_SLOTS }, () => context.createBiquadFilter());
    applyFilters(bands, filters);

    const chain: AudioNode[] = [source, ...bands, preamp, context.destination];
    chain.forEach((node, i) => {
      const next = chain[i + 1];
      if (next) {
        node.connect(next);
      }
    });

    source.start();
    graph.current = { context, source, preamp, bands, gains, bypassed: false };
    setSampleRate(context.sampleRate);
    setBypassed(false);
    setPlaying(true);
  }, []);

  /** Retune a running graph, so dragging the slider is audible immediately. */
  const update = useCallback(
    (filters: Filter[], headroomDb: number, bypassDb: number) => {
      const current = graph.current;
      if (!current) {
        return;
      }
      current.gains = { filtered: headroomDb, flat: bypassDb };
      // Whichever side is audible has to follow the slider. Reading the flag
      // off the graph rather than the `bypassed` state keeps this correct
      // without making the callback depend on it -- a stale closure here would
      // silently drag the wrong gain onto the wrong side.
      current.preamp.gain.value =
        10 ** ((current.bypassed ? bypassDb : headroomDb) / 20);
      applyFilters(current.bands, filters);
    },
    [],
  );

  /**
   * Take the filters out of the path, and move the preamp to the published
   * bypass figure as they go.
   *
   * That second half is what makes this a comparison rather than a volume
   * change, and it used to be missing: the preamp stayed put on the theory
   * that the compensation is 0 dB at 1 kHz, so the midrange would hold still
   * by itself. Listening says otherwise -- flat at the same preamp reads
   * about half a decibel smaller in scale at 75 dB and more than a decibel
   * smaller at 60 -- which is the whole reason `bypass_headroom_db` exists.
   * Using it here makes the page's own A/B the one the tables describe.
   */
  const setBypass = useCallback((next: boolean) => {
    setBypassed(next);
    const current = graph.current;
    if (!current) {
      return;
    }
    current.bypassed = next;
    current.preamp.gain.value =
      10 ** ((next ? current.gains.flat : current.gains.filtered) / 20);
    const head = current.bands[0];
    current.source.disconnect();
    current.source.connect(next || !head ? current.preamp : head);
  }, []);

  useEffect(() => stop, [stop]);

  return { playing, bypassed, sampleRate, start, stop, update, setBypass };
}
