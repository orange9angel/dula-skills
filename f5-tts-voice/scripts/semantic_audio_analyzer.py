#!/usr/bin/env python3
"""
Semantic Audio Analyzer for the F5-TTS voice skill.

Runs **before** edge-tts synthesis and produces two independent control layers:

  1. `prosody`  -> fed into edge-tts via SSML `<prosody>` / `<emphasis>`.
                   Handles what edge-tts does well: 语速、语调、音量、重音.

  2. `post_effect` -> fed into the sox/ffmpeg effect chain.
                      Handles what sox/ffmpeg does well: 音色、EQ、混响、压缩、空间感.

Splitting control this way avoids double-processing speed/pitch and gives each
engine the jobs it is good at:

  - edge-tts controls macro prosody with high-quality neural TTS.
  - sox/ffmpeg shapes timbre/personality and adds final polish.

The analyzer is rule-based, Chinese-first, English fallback, zero dependencies.
"""

import re


class SemanticAudioAnalyzer:
    """Rule-based semantic analyzer that maps text to prosody + post-effect."""

    def __init__(self, language="auto"):
        self.language = language

    # ───────────────────────────────────────────────────────────────────────
    # Public API
    # ───────────────────────────────────────────────────────────────────────

    def analyze(self, text, character_cfg=None):
        """
        Analyze a dialogue line and return prosody + post_effect dicts.

        Returns:
            {
              "prosody": {
                "rate": str,      # e.g. "-5%"
                "pitch": str,     # e.g. "+6%"
                "volume": str,    # e.g. "+5%"
                "emphasis": str | None,  # "strong" | "moderate" | "reduced" | None
              },
              "post_effect": {
                # same keys as personality/effect system
                "pitch": "+0st",  # fine pitch offset applied by sox
                "formant": "0",
                "speed": 1.0,
                "treble": 0,
                "bass": 0,
                "presence": 0,
                "warmth": 0,
                "reverb": 0.0,
                "compression": 0.0,
                ...
              }
            }
        """
        if not text or not text.strip():
            return {"prosody": {}, "post_effect": {}}

        lang = self._detect_language(text) if self.language == "auto" else self.language

        prosody = {}
        post_effect = {}

        self._analyze_punctuation(text, lang, prosody, post_effect)
        self._analyze_emotion_keywords(text, lang, prosody, post_effect)
        self._analyze_rhythm(text, lang, prosody)
        self._analyze_timbre(text, lang, character_cfg, prosody, post_effect)

        return {
            "prosody": self._clamp_prosody(prosody),
            "post_effect": self._clamp_effect(post_effect),
        }

    # ───────────────────────────────────────────────────────────────────────
    # Language detection
    # ───────────────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_language(text):
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        english = len(re.findall(r"[a-zA-Z]", text))
        if chinese > english and chinese > 0:
            return "zh"
        if english > chinese and english > 0:
            return "en"
        return "zh"

    # ───────────────────────────────────────────────────────────────────────
    # Punctuation & intonation
    # ───────────────────────────────────────────────────────────────────────

    def _analyze_punctuation(self, text, lang, prosody, post_effect):
        t = text.strip()
        if not t:
            return

        # Questions / soft particles -> rising intonation, clear slowdown.
        # Also catches particles immediately followed by trailing punctuation,
        # e.g. "...吧！" or "...呢？"
        if t[-1] in "?？" or (lang == "zh" and re.search(r"[吗呢吧嘛][！。]?$", t)):
            prosody["pitch"] = self._add_pct(prosody.get("pitch", "+0%"), "+6%")
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), "-6%")

        # Exclamations -> emphasis and volume, but do not speed up by default.
        if t[-1] in "!！":
            prosody["emphasis"] = "strong"
            prosody["volume"] = self._add_pct(prosody.get("volume", "+0%"), "+6%")
            post_effect["compression"] = post_effect.get("compression", 0) + 0.10
            post_effect["treble"] = post_effect.get("treble", 0) + 1

        # Trailing ellipses / em-dash -> uncertainty, slower, more space
        if re.search(r"\.{3,}|…{1,}|——$", t):
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), "-6%")
            post_effect["reverb"] = post_effect.get("reverb", 0) + 0.12

        # Mid-sentence ellipsis -> hesitation / pause feel
        if re.search(r"\.{2,}|…{1,}", t) and not re.search(r"\.{3,}|…{1,}$", t):
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), "-4%")

        # Demonstrative / explanatory phrases -> slower, more deliberate
        if lang == "zh" and re.search(r"试试|看看|这个|那个|这样|那样|听好", t):
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), "-4%")

        # Many short clauses used to add +3% rate, which made explanatory
        # sentences sound rushed. More clauses usually need more pauses,
        # not faster delivery. We now leave rate unchanged here.
        clause_count = len(re.split(r"[，,。！!？?；;]", t))
        if clause_count >= 5:
            post_effect["compression"] = post_effect.get("compression", 0) + 0.04

    # ───────────────────────────────────────────────────────────────────────
    # Emotion keywords
    # ───────────────────────────────────────────────────────────────────────

    EMOTION_PATTERNS_ZH = {
        "happy": {
            "words": ["哈哈", "嘿嘿", "嘻嘻", "开心", "高兴", "太好", "棒", "耶"],
            "prosody": {"pitch": "+6%", "rate": "+5%", "volume": "+3%"},
            "post_effect": {"treble": 2, "reverb": -0.05, "warmth": 1},
        },
        "sad": {
            "words": ["呜", "呜呜", "难过", "伤心", "哭", "眼泪", "失落", "孤单"],
            "prosody": {"pitch": "-6%", "rate": "-6%", "volume": "-5%"},
            "post_effect": {"reverb": 0.12, "treble": -2, "warmth": 2},
        },
        "angry": {
            "words": ["哼", "生气", "讨厌", "可恶", "混蛋", "烦", "火大", "怒"],
            "prosody": {"pitch": "+3%", "rate": "+7%", "volume": "+5%", "emphasis": "strong"},
            "post_effect": {"compression": 0.14, "bass": 2, "treble": 1},
        },
        "surprised": {
            "words": ["哇", "哎呀", "天哪", "真的吗", "居然", "不会吧", "啊？", "啊!", "啊！"],
            "prosody": {"pitch": "+12%", "rate": "+6%", "volume": "+8%", "emphasis": "strong"},
            "post_effect": {"treble": 3, "compression": 0.08},
        },
        "worried": {
            "words": ["怎么办", "糟糕", "完了", "怕", "担心", "紧张", "万一"],
            "prosody": {"pitch": "+3%", "rate": "+5%", "volume": "-2%"},
            "post_effect": {"reverb": 0.08, "compression": 0.06, "treble": 1},
        },
        "relieved": {
            "words": ["太好了", "终于", "松了一口气", "放心", "幸好", "没事了"],
            "prosody": {"pitch": "-3%", "rate": "-4%", "volume": "-3%"},
            "post_effect": {"reverb": 0.06, "warmth": 1},
        },
        "gentle": {
            "words": ["没关系", "别怕", "慢慢来", "没事", "小心", "温柔"],
            "prosody": {"pitch": "-3%", "rate": "-5%", "volume": "-5%"},
            "post_effect": {"warmth": 2, "compression": -0.05, "reverb": 0.05},
        },
        "proud": {
            "words": ["当然", "没问题", "交给我", "厉害", "看我的", "肯定"],
            "prosody": {"pitch": "-3%", "rate": "-2%", "volume": "+3%"},
            "post_effect": {"presence": 2, "compression": 0.06},
        },
    }

    EMOTION_PATTERNS_EN = {
        "happy": {
            "words": ["haha", "hehe", "yay", "great", "happy", "awesome", "wow"],
            "prosody": {"pitch": "+6%", "rate": "+5%", "volume": "+3%"},
            "post_effect": {"treble": 2, "reverb": -0.05, "warmth": 1},
        },
        "sad": {
            "words": ["sob", "sad", "cry", "sorry", "lonely", "upset", "tears"],
            "prosody": {"pitch": "-6%", "rate": "-6%", "volume": "-5%"},
            "post_effect": {"reverb": 0.12, "treble": -2, "warmth": 2},
        },
        "angry": {
            "words": ["huh", "angry", "hate", "damn", "annoying", "mad", "furious"],
            "prosody": {"pitch": "+3%", "rate": "+7%", "volume": "+5%", "emphasis": "strong"},
            "post_effect": {"compression": 0.14, "bass": 2, "treble": 1},
        },
        "surprised": {
            "words": ["wow", "oh", "what", "really", "no way", "gosh", "ah!"],
            "prosody": {"pitch": "+12%", "rate": "+6%", "volume": "+8%", "emphasis": "strong"},
            "post_effect": {"treble": 3, "compression": 0.08},
        },
        "worried": {
            "words": ["what if", "worried", "nervous", "scared", "anxious", "bad"],
            "prosody": {"pitch": "+3%", "rate": "+5%", "volume": "-2%"},
            "post_effect": {"reverb": 0.08, "compression": 0.06, "treble": 1},
        },
        "relieved": {
            "words": ["finally", "relieved", "safe", "glad", "phew", "okay"],
            "prosody": {"pitch": "-3%", "rate": "-4%", "volume": "-3%"},
            "post_effect": {"reverb": 0.06, "warmth": 1},
        },
        "gentle": {
            "words": ["it's okay", "don't worry", "gentle", "careful", "soft"],
            "prosody": {"pitch": "-3%", "rate": "-5%", "volume": "-5%"},
            "post_effect": {"warmth": 2, "compression": -0.05, "reverb": 0.05},
        },
        "proud": {
            "words": ["of course", "leave it", "definitely", "sure", "proud"],
            "prosody": {"pitch": "-3%", "rate": "-2%", "volume": "+3%"},
            "post_effect": {"presence": 2, "compression": 0.06},
        },
    }

    def _analyze_emotion_keywords(self, text, lang, prosody, post_effect):
        patterns = self.EMOTION_PATTERNS_ZH if lang == "zh" else self.EMOTION_PATTERNS_EN

        for emotion, data in patterns.items():
            score = 0
            for word in data["words"]:
                if lang == "zh":
                    score += text.count(word)
                else:
                    score += len(re.findall(rf"\b{re.escape(word)}\b", text, re.IGNORECASE))

            if score == 0:
                continue

            weight = min(score, 2)

            for key, value in data["prosody"].items():
                if key == "emphasis":
                    # Stronger emotion wins; keep strongest emphasis.
                    current = prosody.get("emphasis")
                    strength = {"reduced": 0, "moderate": 1, "strong": 2}
                    if strength.get(value, 0) > strength.get(current, 0):
                        prosody[key] = value
                else:
                    prosody[key] = self._add_pct(prosody.get(key, "+0%"), self._scale_pct(value, weight))

            for key, value in data["post_effect"].items():
                post_effect[key] = post_effect.get(key, 0) + value * weight

    # ───────────────────────────────────────────────────────────────────────
    # Rhythm
    # ───────────────────────────────────────────────────────────────────────

    def _analyze_rhythm(self, text, lang, prosody):
        char_count = len(re.findall(r"[\u4e00-\u9fff]", text)) if lang == "zh" else len(text.split())

        if char_count > 20:
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), "-3%")
        elif char_count < 6:
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), "+2%")

        repeats = len(re.findall(r"(.)\1{2,}", text))
        if repeats:
            prosody["rate"] = self._add_pct(prosody.get("rate", "+0%"), f"{-3 * repeats}%")
            # Repeated sounds also get a little post-compression for punch.

    # ───────────────────────────────────────────────────────────────────────
    # Timbre
    # ───────────────────────────────────────────────────────────────────────

    def _analyze_timbre(self, text, lang, character_cfg, prosody, post_effect):
        t = text

        # Whisper / secret / fear -> darker, more intimate
        if re.search(r"小声|秘密|悄悄|害怕|恐惧|whisper|secret|afraid", t):
            prosody["volume"] = self._add_pct(prosody.get("volume", "+0%"), "-10%")
            post_effect["treble"] = post_effect.get("treble", 0) - 2
            post_effect["warmth"] = post_effect.get("warmth", 0) + 1

        # Shout / call / cheer -> brighter, more present
        if re.search(r"叫|喊|救命|加油|快来|shout|scream|help", t):
            prosody["volume"] = self._add_pct(prosody.get("volume", "+0%"), "+10%")
            prosody["emphasis"] = "strong"
            post_effect["treble"] = post_effect.get("treble", 0) + 2
            post_effect["presence"] = post_effect.get("presence", 0) + 2
            post_effect["compression"] = post_effect.get("compression", 0) + 0.08

        # Cute register -> younger formant color (sox), slight pitch lift (prosody)
        if re.search(r"嘛|啦|呀|呢|哼|cute|little", t):
            prosody["pitch"] = self._add_pct(prosody.get("pitch", "+0%"), "+3%")
            post_effect["formant"] = self._add_semitones(post_effect.get("formant", "0"), "-0.5")

        # Authority / narration -> slightly older/warmer formant
        if character_cfg and character_cfg.get("role") in ("narrator", "teacher", "adult"):
            post_effect["formant"] = self._add_semitones(post_effect.get("formant", "0"), "+0.3")

    # ───────────────────────────────────────────────────────────────────────
    # Helpers
    # ───────────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_pct(value):
        m = re.match(r"([+-]?\d+(?:\.\d+)?)%", str(value).strip())
        return float(m.group(1)) if m else 0.0

    @staticmethod
    def _format_pct(value):
        value = max(-30, min(30, value))
        sign = "+" if value >= 0 else ""
        return f"{sign}{value:.0f}%"

    @staticmethod
    def _add_pct(a, b):
        total = SemanticAudioAnalyzer._parse_pct(a) + SemanticAudioAnalyzer._parse_pct(b)
        return SemanticAudioAnalyzer._format_pct(total)

    @staticmethod
    def _scale_pct(value, weight):
        return SemanticAudioAnalyzer._format_pct(SemanticAudioAnalyzer._parse_pct(value) * weight)

    @staticmethod
    def _add_semitones(base, delta):
        base_val = SemanticAudioAnalyzer._parse_semitones(base)
        delta_val = SemanticAudioAnalyzer._parse_semitones(delta)
        total = base_val + delta_val
        return f"{total:+.1f}"

    @staticmethod
    def _parse_semitones(value):
        if isinstance(value, (int, float)):
            return float(value)
        m = re.match(r"([+-]?\d+(?:\.\d+)?)st?", str(value).strip())
        return float(m.group(1)) if m else 0.0

    def _clamp_prosody(self, prosody):
        clamps = {
            "rate": (-25, 25),
            "pitch": (-15, 20),
            "volume": (-20, 20),
        }
        for key, (lo, hi) in clamps.items():
            if key in prosody and key != "emphasis":
                val = self._parse_pct(prosody[key])
                prosody[key] = self._format_pct(max(lo, min(hi, val)))
        return prosody

    def _clamp_effect(self, effect):
        clamps = {
            "speed": (0.75, 1.25),
            "compression": (-0.2, 0.35),
            "reverb": (-0.2, 0.3),
            "treble": (-5, 6),
            "bass": (-4, 5),
            "presence": (-3, 4),
            "warmth": (-3, 4),
            "formant": (-1.5, 1.5),
        }
        for key, (lo, hi) in clamps.items():
            if key in effect:
                if key == "formant":
                    effect[key] = max(lo, min(hi, self._parse_semitones(effect[key])))
                else:
                    effect[key] = max(lo, min(hi, effect[key]))
        return effect


# ─────────────────────────────────────────────────────────────────────────
# Convenience entry point
# ─────────────────────────────────────────────────────────────────────────

def analyze_text(text, character_cfg=None, language="auto"):
    analyzer = SemanticAudioAnalyzer(language=language)
    return analyzer.analyze(text, character_cfg)


if __name__ == "__main__":
    samples = [
        "真的吗？那岂不是很厉害！",
        "不要不理我……我在这里啊……",
        "哈哈，他们真的完全没反应！太自由了！",
        "下次不要突然消失，我们会担心的。",
        "What? I can't believe it!",
    ]
    for s in samples:
        print(f"{s!r} -> {analyze_text(s)}")
