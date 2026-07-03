// A faithful port of CPython's `random.Random` MT19937 core — only the pieces the figure DSL
// needs (`random()` → float in [0,1)). The `gas` command scatters particles with a seeded RNG;
// to keep byte-identical SVG parity with the Python reference, the JS port must reproduce
// CPython's exact stream. This is init_by_array + genrand_uint32 + genrand_res53 from
// Modules/_randommodule.c, using Math.imul / >>> 0 for 32-bit unsigned arithmetic.

const N = 624;
const M = 397;
const MATRIX_A = 0x9908b0df;
const UPPER_MASK = 0x80000000;
const LOWER_MASK = 0x7fffffff;

export class MersenneTwister {
  private mt = new Uint32Array(N);
  private index = N + 1;

  constructor(seed: number) {
    this.initByArray(seedToKey(seed));
  }

  private initGenrand(s: number): void {
    this.mt[0] = s >>> 0;
    for (let i = 1; i < N; i++) {
      const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
      this.mt[i] = (Math.imul(1812433253, prev >>> 0) + i) >>> 0;
    }
    this.index = N;
  }

  private initByArray(key: number[]): void {
    this.initGenrand(19650218);
    let i = 1;
    let j = 0;
    let k = Math.max(N, key.length);
    for (; k; k--) {
      const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
      this.mt[i] =
        ((this.mt[i] ^ Math.imul(prev >>> 0, 1664525)) + key[j] + j) >>> 0;
      i++;
      j++;
      if (i >= N) {
        this.mt[0] = this.mt[N - 1];
        i = 1;
      }
      if (j >= key.length) j = 0;
    }
    for (k = N - 1; k; k--) {
      const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
      this.mt[i] = ((this.mt[i] ^ Math.imul(prev >>> 0, 1566083941)) - i) >>> 0;
      i++;
      if (i >= N) {
        this.mt[0] = this.mt[N - 1];
        i = 1;
      }
    }
    this.mt[0] = 0x80000000;
  }

  private genrandUint32(): number {
    const mt = this.mt;
    if (this.index >= N) {
      let kk = 0;
      for (; kk < N - M; kk++) {
        const y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
        mt[kk] = (mt[kk + M] ^ (y >>> 1) ^ (y & 1 ? MATRIX_A : 0)) >>> 0;
      }
      for (; kk < N - 1; kk++) {
        const y = (mt[kk] & UPPER_MASK) | (mt[kk + 1] & LOWER_MASK);
        mt[kk] = (mt[kk + (M - N)] ^ (y >>> 1) ^ (y & 1 ? MATRIX_A : 0)) >>> 0;
      }
      const y = (mt[N - 1] & UPPER_MASK) | (mt[0] & LOWER_MASK);
      mt[N - 1] = (mt[M - 1] ^ (y >>> 1) ^ (y & 1 ? MATRIX_A : 0)) >>> 0;
      this.index = 0;
    }
    let y = mt[this.index++];
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  }

  /** genrand_res53: a double in [0, 1) with 53 bits of resolution — CPython's `random()`. */
  random(): number {
    const a = this.genrandUint32() >>> 5; // 27 bits
    const b = this.genrandUint32() >>> 6; // 26 bits
    return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
  }
}

/** Split an integer seed into little-endian 32-bit words, as CPython's random_seed does. */
function seedToKey(seed: number): number[] {
  let a = BigInt(Math.abs(Math.trunc(seed)));
  if (a === 0n) return [0];
  const key: number[] = [];
  while (a > 0n) {
    key.push(Number(a & 0xffffffffn));
    a >>= 32n;
  }
  return key;
}
