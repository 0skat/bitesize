export type WordCategory =
  | "fast"
  | "happy"
  | "sad"
  | "fire"
  | "water"
  | "big"
  | "small"
  | "thinking"
  | "scary"
  | "default";

export const CATEGORY_STYLES: Record<
  WordCategory,
  { color: string; animClass: string; extraClass?: string }
> = {
  fast: {
    color: "#c7d2fe",
    animClass: "word-fast",
    extraClass: "font-semibold tracking-tight",
  },
  happy: {
    color: "#fbbf24",
    animClass: "word-happy",
    extraClass: "font-medium",
  },
  sad: {
    color: "#6b7280",
    animClass: "word-sad",
    extraClass: "italic",
  },
  fire: {
    color: "#fb923c",
    animClass: "word-fire",
    extraClass: "font-semibold",
  },
  water: {
    color: "#38bdf8",
    animClass: "word-water",
  },
  big: {
    color: "#f1f5f9",
    animClass: "word-big",
    extraClass: "font-bold tracking-wide",
  },
  small: {
    color: "#94a3b8",
    animClass: "word-small",
    extraClass: "text-sm",
  },
  thinking: {
    color: "#a78bfa",
    animClass: "word-thinking",
    extraClass: "italic",
  },
  scary: {
    color: "#f87171",
    animClass: "word-scary",
    extraClass: "font-semibold",
  },
  default: {
    color: "#e2e8f0",
    animClass: "word-default",
  },
};

// Comprehensive word → category dictionary
const WORD_MAP: Record<string, WordCategory> = {
  // ── FAST / ACTION ──────────────────────────────────────────
  run: "fast", running: "fast", runs: "fast",
  fly: "fast", flying: "fast", flies: "fast",
  rush: "fast", rushing: "fast",
  speed: "fast", speeding: "fast",
  quick: "fast", quickly: "fast",
  fast: "fast", faster: "fast", fastest: "fast",
  dash: "fast", dashing: "fast",
  sprint: "fast", sprinting: "fast",
  swift: "fast", swiftly: "fast",
  rapid: "fast", rapidly: "fast",
  zoom: "fast", zooming: "fast",
  bolt: "fast", bolting: "fast",
  race: "fast", racing: "fast",
  hurry: "fast", hurrying: "fast",
  instantly: "fast", immediate: "fast", immediately: "fast",
  snap: "fast", snapping: "fast",
  leap: "fast", leaping: "fast",
  shoot: "fast", shooting: "fast",
  surge: "fast", surging: "fast",

  // ── HAPPY / POSITIVE ────────────────────────────────────────
  joy: "happy", joyful: "happy", joyfully: "happy",
  love: "happy", loving: "happy", loved: "happy",
  bright: "happy", brighter: "happy", brightest: "happy",
  wonderful: "happy", wonderfully: "happy",
  amazing: "happy", amazingly: "happy",
  beautiful: "happy", beautifully: "happy",
  fantastic: "happy", fantastically: "happy",
  incredible: "happy", incredibly: "happy",
  delight: "happy", delightful: "happy", delightfully: "happy",
  celebrate: "happy", celebrating: "happy", celebration: "happy",
  bliss: "happy", blissful: "happy",
  radiant: "happy", radiantly: "happy",
  sunshine: "happy", sunny: "happy",
  laugh: "happy", laughing: "happy", laughter: "happy",
  smile: "happy", smiling: "happy",
  gleam: "happy", gleaming: "happy",
  glow: "happy", glowing: "happy",
  sparkle: "happy", sparkling: "happy",
  happy: "happy", happily: "happy", happiness: "happy",
  thrill: "happy", thrilling: "happy", thrilled: "happy",
  magic: "happy", magical: "happy", magically: "happy",
  perfect: "happy", perfectly: "happy",
  awesome: "happy", brilliantly: "happy",
  exciting: "happy", excited: "happy", excitement: "happy",
  stunning: "happy", stunningly: "happy",
  magnificent: "happy", magnificently: "happy",
  ecstasy: "happy", ecstatic: "happy",

  // ── SAD / MELANCHOLY ────────────────────────────────────────
  sad: "sad", sadly: "sad", sadness: "sad",
  lost: "sad", losing: "sad",
  broken: "sad", breaking: "sad",
  lonely: "sad", loneliness: "sad", alone: "sad",
  dark: "sad", darkness: "sad",
  sorrow: "sad", sorrowful: "sad",
  grief: "sad", grieving: "sad",
  despair: "sad", despairing: "sad",
  hollow: "sad",
  empty: "sad", emptiness: "sad",
  fade: "sad", fading: "sad",
  dim: "sad", dimly: "sad",
  cold: "sad", coldness: "sad",
  wither: "sad", withering: "sad",
  pain: "sad", painful: "sad", painfully: "sad",
  tears: "sad", crying: "sad", cry: "sad",
  miss: "sad", missing: "sad",
  gone: "sad", goodbye: "sad",
  forget: "sad", forgotten: "sad",
  regret: "sad", regretful: "sad",
  hurt: "sad", hurting: "sad",
  silence: "sad", silent: "sad",
  abandoned: "sad",
  heavy: "sad",
  gray: "sad", grey: "sad",
  melancholy: "sad",

  // ── FIRE / HEAT / ENERGY ────────────────────────────────────
  fire: "fire", fiery: "fire", fired: "fire",
  burn: "fire", burning: "fire", burns: "fire", burned: "fire",
  spark: "fire", sparking: "fire", sparked: "fire",
  electric: "fire", electricity: "fire", electrifying: "fire",
  intense: "fire", intensely: "fire", intensity: "fire",
  flame: "fire", flames: "fire", flaming: "fire",
  heat: "fire", heated: "fire", heating: "fire",
  blaze: "fire", blazing: "fire",
  scorch: "fire", scorching: "fire",
  ignite: "fire", igniting: "fire", ignited: "fire",
  explosive: "fire", explode: "fire", explosion: "fire",
  fierce: "fire", fiercely: "fire", ferocious: "fire",
  searing: "fire", sear: "fire",
  passion: "fire", passionate: "fire", passionately: "fire",
  inferno: "fire",
  volcanic: "fire", volcano: "fire",
  rage: "fire", raging: "fire",
  fury: "fire", furious: "fire", furiously: "fire",
  hot: "fire", boiling: "fire",
  energy: "fire", energetic: "fire",
  power: "fire", powerful: "fire", powerfully: "fire",
  force: "fire", forceful: "fire",
  volatile: "fire", blazes: "fire",

  // ── WATER / CALM / FLOW ─────────────────────────────────────
  flow: "water", flowing: "water", flows: "water",
  wave: "water", waves: "water", waving: "water",
  gentle: "water", gently: "water", gentleness: "water",
  calm: "water", calmly: "water", calmness: "water",
  ocean: "water", oceanic: "water",
  river: "water", rivers: "water",
  stream: "water", streaming: "water", streams: "water",
  ripple: "water", rippling: "water", ripples: "water",
  serene: "water", serenely: "water", serenity: "water",
  smooth: "water", smoothly: "water",
  drift: "water", drifting: "water", drifts: "water",
  tide: "water", tides: "water",
  fluid: "water", fluidity: "water",
  tranquil: "water", tranquility: "water",
  rain: "water", rainfall: "water", raining: "water",
  lake: "water", lakes: "water",
  sea: "water", seas: "water",
  water: "water", waterfall: "water",
  pool: "water",
  melt: "water", melting: "water",
  soothe: "water", soothing: "water",
  peace: "water", peaceful: "water", peacefully: "water",
  still: "water", stillness: "water",
  quiet: "water", quietly: "water",
  easy: "water", easily: "water",
  breath: "water", breathe: "water", breathing: "water",

  // ── BIG / VAST / GRAND ──────────────────────────────────────
  universe: "big", universal: "big",
  infinite: "big", infinity: "big", infinitely: "big",
  vast: "big", vastly: "big", vastness: "big",
  enormous: "big", enormously: "big",
  huge: "big", hugely: "big",
  massive: "big", massively: "big",
  colossal: "big", colossally: "big",
  immense: "big", immensely: "big", immensity: "big",
  grand: "big", grandly: "big", grandeur: "big",
  epic: "big", epically: "big",
  boundless: "big",
  cosmic: "big", cosmically: "big",
  galactic: "big", galaxy: "big",
  eternal: "big", eternity: "big",
  monumental: "big", monumentally: "big",
  legendary: "big",
  extraordinary: "big", extraordinarily: "big",
  overwhelming: "big", overwhelmingly: "big",
  unimaginable: "big",
  astronomical: "big",

  // ── SMALL / TINY / DELICATE ─────────────────────────────────
  tiny: "small", tinier: "small", tiniest: "small",
  little: "small", smaller: "small", smallest: "small",
  micro: "small", microscopic: "small",
  small: "small",
  whisper: "small", whispering: "small", whispered: "small",
  miniature: "small",
  subtle: "small", subtly: "small", subtlety: "small",
  slight: "small", slightly: "small",
  delicate: "small", delicately: "small", delicacy: "small",
  minute: "small",
  barely: "small",
  faint: "small", faintly: "small",
  thin: "small",
  lightly: "small",
  soft: "small", softly: "small", softness: "small",
  fragile: "small", fragility: "small",
  tender: "small", tenderly: "small", tenderness: "small",

  // ── THINKING / WONDERING ────────────────────────────────────
  think: "thinking", thinking: "thinking", thought: "thinking", thoughts: "thinking",
  wonder: "thinking", wondering: "thinking",
  ponder: "thinking", pondering: "thinking",
  perhaps: "thinking",
  maybe: "thinking",
  consider: "thinking", considering: "thinking",
  reflect: "thinking", reflecting: "thinking", reflection: "thinking",
  imagine: "thinking", imagining: "thinking", imagination: "thinking",
  contemplate: "thinking", contemplating: "thinking", contemplation: "thinking",
  curious: "thinking", curiosity: "thinking",
  question: "thinking", questioning: "thinking",
  hypothesis: "thinking", hypothesize: "thinking",
  theory: "thinking", theorize: "thinking",
  explore: "thinking", exploring: "thinking", exploration: "thinking",
  discover: "thinking", discovering: "thinking", discovery: "thinking",
  seek: "thinking", seeking: "thinking",
  understand: "thinking", understanding: "thinking",
  realize: "thinking", realizing: "thinking", realization: "thinking",
  perceive: "thinking", perceiving: "thinking", perception: "thinking",
  analyze: "thinking", analyzing: "thinking", analysis: "thinking",
  reason: "thinking", reasoning: "thinking",
  dream: "thinking", dreaming: "thinking",
  envision: "thinking", envisioning: "thinking",
  speculate: "thinking", speculating: "thinking", speculation: "thinking",
  suppose: "thinking", supposing: "thinking",
  believe: "thinking", believing: "thinking", belief: "thinking",

  // ── SCARY / TENSE / URGENT ──────────────────────────────────
  danger: "scary", dangerous: "scary", dangerously: "scary",
  fear: "scary", fearful: "scary", fearfully: "scary",
  warning: "scary", warn: "scary",
  urgent: "scary", urgently: "scary", urgency: "scary",
  alert: "scary", alerted: "scary",
  threat: "scary", threatening: "scary", threatens: "scary",
  critical: "scary", critically: "scary",
  panic: "scary", panicking: "scary", panicked: "scary",
  terror: "scary", terrifying: "scary", terrified: "scary",
  chaos: "scary", chaotic: "scary",
  crisis: "scary",
  emergency: "scary",
  catastrophe: "scary", catastrophic: "scary",
  horror: "scary", horrifying: "scary", horrible: "scary",
  nightmare: "scary",
  fatal: "scary", fatally: "scary",
  deadly: "scary",
  collapse: "scary", collapsing: "scary",
  destruction: "scary", destroy: "scary", destroying: "scary",
  shatter: "scary", shattering: "scary",
  crash: "scary", crashing: "scary",
  doom: "scary", doomed: "scary",
  attack: "scary", attacking: "scary",
  scream: "scary", screaming: "scary",
  shock: "scary", shocking: "scary",
};

export function categorize(word: string): WordCategory {
  const clean = word.toLowerCase().replace(/[^a-z]/g, "");
  return WORD_MAP[clean] ?? "default";
}

// Tokenize text into word + whitespace tokens
export interface Token {
  type: "word" | "space";
  text: string;
}

export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  // Split on whitespace boundaries, keeping the delimiters
  const parts = text.split(/(\s+)/);
  for (const part of parts) {
    if (!part) continue;
    if (/^\s+$/.test(part)) {
      tokens.push({ type: "space", text: part });
    } else {
      // Handle punctuation attached to words — split trailing punctuation
      const match = part.match(/^([a-zA-Z'-]+)([^a-zA-Z'-]*)$/);
      if (match) {
        tokens.push({ type: "word", text: match[1] });
        if (match[2]) tokens.push({ type: "space", text: match[2] });
      } else {
        tokens.push({ type: "word", text: part });
      }
    }
  }
  return tokens;
}
