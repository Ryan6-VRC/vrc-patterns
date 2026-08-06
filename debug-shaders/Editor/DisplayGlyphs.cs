using System;
using System.Text;
using UnityEngine;

namespace Ryan6Vrc.Patterns.DebugShaders.Editor
{
    /// <summary>
    /// The wire format for <c>Ryan6VRC/Overlay/DebugDisplay</c>: a 6-bit uppercase glyph charset, the
    /// author-time string→float label packing, and the per-entry format bitfield. This type is the
    /// CANON for all three — the MSDF atlas is generated from <see cref="Charset"/> (never from a
    /// committed copy of it), the shader's HLSL unpack mirrors <see cref="TryEncodeLabel"/>, and the
    /// <c>vrc-patterns/debug-shaders</c> README quotes the arithmetic. Pure math, no Unity asset access,
    /// so it is the NUnit-tested core the two doors (<see cref="SetDisplayEntry"/>,
    /// <see cref="ReportDisplay"/>) and the material inspector all sit on.
    ///
    /// <para><b>Why a shader carries strings at all.</b> There is no runtime mechanism for a clip to
    /// drive text: ShaderLab has no string property type, <c>Material</c> has no string setter, animator
    /// parameters are Float/Int/Bool/Trigger, and animation curves carry floats. Labels are therefore
    /// author-time by construction, and a label packed into a material property costs nothing at
    /// runtime — which is the design, not a limitation.</para>
    ///
    /// <para><b>Three chars per component, not four — and the reason is not float32.</b> Twelve chars at
    /// 6 bits is 72 bits. Four-per-component (24 bits) is exactly float32's integer-exact ceiling
    /// (2^24), so it round-trips through a <c>Vector4</c> perfectly well in isolation. It does NOT
    /// survive the toolchain: d4rkAvatarOptimizer bakes material properties into generated shader
    /// source as text via <c>$"{float}"</c> (<c>d4rkAvatarOptimizer.cs:4565</c>), which is
    /// <c>float.ToString()</c> — "G7", 7 significant digits — so 16777215 re-parses as 16777220 and all
    /// four packed chars change. Three-per-component caps a component at
    /// <see cref="MaxComponent"/> = 262143: six digits, G7-safe verbatim, and it needs nothing proven
    /// about Unity's own serializer.
    ///
    /// That path is NOT always live — <c>:4443</c> gates it, <c>:236</c> restricts it to
    /// StandaloneWindows64, and of the shipped presets only "Shader Toggles" and "Full" enable it — so
    /// the argument for 18 bits is COST, not certainty: twelve chars either way, and spending <c>.w</c>
    /// frees the format bitfield into its own property, which is tidier regardless. Do not restate this
    /// as a guaranteed failure.</para>
    /// </summary>
    public static class DisplayGlyphs
    {
        // ── The charset (canon) ─────────────────────────────────────────────────────────────────────

        /// <summary>
        /// The 63 atlas glyphs. Index IS the glyph ID, so reordering this string invalidates every
        /// committed label and the atlas together. ID 63 is <see cref="Space"/>, which is deliberately
        /// NOT in the table — see below.
        ///
        /// <para><b>The order is codepoint-ascending because msdf-atlas-gen lays a uniform grid out in
        /// codepoint order, not in charset-file order.</b> Measured, not assumed: a first atlas generated
        /// from a hand-ordered table came back with <c>! # $ % &amp; ( ) *</c> in row 0 and
        /// <c>+ , - . / 0 1 2</c> in row 1 regardless of the order requested, which would have rendered
        /// every glyph as a different character. So the table follows the generator rather than fighting
        /// it, and <see cref="Charset_Is_Strictly_Codepoint_Ascending"/> is the machine guard against
        /// someone later "tidying" it back into a human-pleasing grouping.</para>
        ///
        /// <para><b>What the ancestor actually constrains is the arithmetic, not the IDs.</b> An earlier
        /// draft claimed IDs 0–12 were inherited verbatim. They are not, and they need not be:
        /// <c>format_coord</c> only requires that the ten digits be CONTIGUOUS (which ASCII guarantees
        /// under any codepoint sort) and that each named glyph have some known ID. Both hold here with
        /// the digits at 13–22. The ancestor's own 14/15/16 were <c>X</c>/<c>Y</c>/<c>Z</c> solely
        /// because it hard-coded axis prefixes, which author-time labels replace.</para>
        ///
        /// <para><b>Space has no cell.</b> <c>Font::sdf()</c> early-returns on the sentinel and never
        /// samples the atlas for it, so spending a cell would be waste — and it could not have one
        /// anyway: U+0020 is the lowest codepoint in the set, so a codepoint sort would drag it to ID 0
        /// where it would collide with a real glyph. Excluding it is what lets the sentinel stay at 63.</para>
        ///
        /// <para>Uppercase only, and MONOSPACE is a hard requirement rather than a preference: the
        /// fixed-cell atlas grid and every advance in the layout arithmetic assume one advance width
        /// for all glyphs.</para>
        /// </summary>
        public const string Charset =
            "!#$%&()*" +                     //  0–7   punctuation below '+'
            "+,-./" +                        //  8–12  sign, comma, minus, point, slash
            "0123456789" +                   // 13–22  digits — contiguous, which is all the arithmetic needs
            ":" +                            // 23     the label separator
            "<=>?@" +                        // 24–28
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +   // 29–54  letters
            "[]^_" +                         // 55–58
            "|~" +                           // 59–60
            "°" +                            // 61
            "∞";                             // 62     the overflow sentinel

        /// <summary>Bits per glyph. 6 → 64 slots, which is what the regenerated atlas holds.</summary>
        public const int Bits = 6;

        /// <summary>Glyph-ID mask, and the ID of the space sentinel — they coincide at 63 by design,
        /// mirroring the ancestor's 5-bit <c>space = mask</c> idiom so an all-bits-set component reads
        /// as blank rather than as a glyph.</summary>
        public const int Mask = (1 << Bits) - 1;

        /// <summary>Space sentinel, and the only ID with no atlas cell. <c>Font::sdf()</c> early-returns
        /// on it, so a space costs no sample.</summary>
        public const int Space = Mask;

        /// <summary>The glyph the shader emits when a value cannot be printed — magnitude past the
        /// exact-integer ceiling, infinity, or NaN. The ancestor had this escape and an earlier draft of
        /// the spec dropped it while keeping the constant; it is wired here so that cannot recur.</summary>
        public const int Infinity = 62;

        /// <summary>Glyph IDs the shader names directly, and the ONLY thing the HLSL side needs from this
        /// table — it never sees the alphabetic half, because labels arrive pre-encoded. Positions follow
        /// from the codepoint order (<see cref="Charset"/>) rather than being chosen; the tests pin them
        /// so a charset edit that moves one fails loudly instead of silently reprinting every number in
        /// the wrong glyphs.</summary>
        public const int Plus = 8, Minus = 10, Dot = 11, Zero = 13, Colon = 23, LetterA = 29;

        // ── Label packing ───────────────────────────────────────────────────────────────────────────

        /// <summary>Chars per label. Not arbitrary: 4 components × <see cref="CharsPerComponent"/>.</summary>
        public const int MaxLabelChars = 12;

        /// <summary>Chars packed into each of <c>.x/.y/.z/.w</c>, LSB-first.</summary>
        public const int CharsPerComponent = 3;

        /// <summary>Largest value a packed component can hold: 2^18 − 1. Six decimal digits, so it
        /// survives a "G7" text round-trip verbatim (see the type remarks).</summary>
        public const int MaxComponent = (1 << (Bits * CharsPerComponent)) - 1;

        /// <summary>
        /// The all-space label — every component <see cref="MaxComponent"/>. This is the shader's
        /// Properties default, and it has to be: a zeroed <c>Vector4</c> decodes as glyph 0 twelve
        /// times, so a fresh material would print <c>++++++++++++</c>.
        /// </summary>
        public static Vector4 BlankLabel =>
            new Vector4(MaxComponent, MaxComponent, MaxComponent, MaxComponent);

        /// <summary>
        /// Packs a label string into the four components of a material <c>Vector</c> property.
        /// Uppercases its input — the charset is uppercase-only — and REPORTS that in
        /// <paramref name="note"/> rather than doing it silently, since a silent case change is still a
        /// change the author did not ask for.
        ///
        /// <para>Returns false, naming the offender, on a string longer than
        /// <see cref="MaxLabelChars"/> or containing a character outside <see cref="Charset"/>. It does
        /// not substitute a fallback glyph: a wrong label that renders is worse than a refusal, because
        /// the display's whole job is to be trusted.</para>
        /// </summary>
        public static bool TryEncodeLabel(string label, out Vector4 packed, out string error, out string note)
        {
            packed = BlankLabel;
            error = null;
            note = null;

            var raw = label ?? string.Empty;
            var upper = raw.ToUpperInvariant();
            if (!string.Equals(raw, upper, StringComparison.Ordinal))
                note = "uppercased '" + raw + "' -> '" + upper + "'";

            if (upper.Length > MaxLabelChars)
            {
                error = "label '" + upper + "' is " + upper.Length + " chars, max " + MaxLabelChars;
                return false;
            }

            var ids = new int[MaxLabelChars];
            for (int i = 0; i < MaxLabelChars; i++) ids[i] = Space;

            for (int i = 0; i < upper.Length; i++)
            {
                // Space is the sentinel and has no atlas cell, so it resolves ahead of the table lookup
                // rather than through it. An interior space in a label is legitimate ("A B") and must
                // survive; only trailing ones are indistinguishable from unused slots.
                int id = upper[i] == ' ' ? Space : Charset.IndexOf(upper[i]);
                if (id < 0)
                {
                    error = "char '" + upper[i] + "' (index " + i + " of '" + upper +
                            "') is not in the charset";
                    return false;
                }
                ids[i] = id;
            }

            var v = new float[4];
            for (int c = 0; c < 4; c++)
            {
                int acc = 0;
                for (int k = 0; k < CharsPerComponent; k++)
                    acc |= (ids[c * CharsPerComponent + k] & Mask) << (k * Bits);
                v[c] = acc;
            }
            packed = new Vector4(v[0], v[1], v[2], v[3]);
            return true;
        }

        /// <summary>
        /// Decodes a packed label back to a string, trailing spaces trimmed. The read door's reason to
        /// exist: a packed label is <c>262143</c> in any raw inspector dump, so without this an agent
        /// can neither observe a display before changing it nor verify it after.
        /// </summary>
        public static string DecodeLabel(Vector4 packed)
        {
            var sb = new StringBuilder(MaxLabelChars);
            for (int c = 0; c < 4; c++)
            {
                int acc = (int)packed[c];
                for (int k = 0; k < CharsPerComponent; k++)
                {
                    int id = (acc >> (k * Bits)) & Mask;
                    // ID 63 is the sentinel; anything else past the table is a corrupt component (a
                    // hand-typed property, or a label that survived a lossy serialization round-trip).
                    // Both read as blank rather than throwing — a report door must survive bad input.
                    sb.Append(id < Charset.Length ? Charset[id] : ' ');
                }
            }
            return sb.ToString().TrimEnd(' ');
        }

        // ── Format bitfield ─────────────────────────────────────────────────────────────────────────

        /// <summary>Field widths and shifts for the per-entry format float, LSB-first. 14 bits total,
        /// max 16383 — five digits, so G7-safe and float32-exact.</summary>
        public const int DecimalsBits = 3, PaletteBits = 2, RpadBits = 4, SourceBits = 5;
        public const int DecimalsShift = 0, PaletteShift = 3, RpadShift = 5, SourceShift = 9;

        /// <summary>Maximum decimals. The 3-bit field reaches 7; 5 is the arithmetic limit the shader's
        /// fractional multiplier holds exactly, so values above it are refused rather than clamped.</summary>
        public const int MaxDecimals = 5;

        /// <summary>Maximum rpad the 4-bit field can carry. The USABLE maximum is smaller and depends on
        /// cell width — see <see cref="MaxUsableRpad"/>.</summary>
        public const int MaxRpad = (1 << RpadBits) - 1;

        /// <summary>Value glyphs the shader reserves per entry.</summary>
        public const int ValueGlyphs = 10;

        // ── Value formatting (the shader's arithmetic, in C# so it can be tested) ────────────────────

        /// <summary>
        /// Powers of ten, bounded at 10^9 — the largest that fits a <c>uint</c> (10^10 exceeds 2^32).
        /// The bound is load-bearing: an earlier version stopped at 10^6, which made
        /// <see cref="DigitCount"/> score four spurious increments for any value ≥ 10^6
        /// (<c>DigitCount(1234567)</c> returned 10) and made every place value at index ≥ 6 read the
        /// millions digit, so 1234567 printed as 1111234567.
        /// </summary>
        public static uint Pow10(int k)
        {
            uint r = 1u;
            for (int i = 0; i < 9; i++) { if (i < k) r *= 10u; }
            return r;
        }

        /// <summary>Decimal digit count of <paramref name="v"/>, minimum 1 (zero has one digit).</summary>
        public static uint DigitCount(uint v)
        {
            uint d = 1u;
            for (int i = 0; i < 9; i++) { if (v >= Pow10(i + 1)) d++; }
            return d;
        }

        /// <summary>
        /// The glyph ID for column <paramref name="n"/> of the value field, counted from the RIGHT
        /// (0 = rightmost). This is the canonical implementation; the shader's
        /// <c>dd_value_glyph_at</c> and the inspector's preview both mirror it, and
        /// <c>DisplayValueFormatTests</c> is what keeps all three honest — the HLSL is otherwise
        /// unreachable by any test, and both bugs the bound above describes lived there.
        ///
        /// <para><b>Width is checked, not just magnitude.</b> A value whose rendered form needs more
        /// than <see cref="ValueGlyphs"/> columns returns the overflow glyph rather than being
        /// truncated. That guard is why the minus sign cannot go missing: the sign is emitted LAST
        /// (at <c>m == digits</c>), so without it an over-wide negative dropped its sign and printed a
        /// confident positive — <c>-1234.5</c> at 5 decimals rendered <c>1234.50000</c>.</para>
        /// </summary>
        public static uint ValueGlyphAt(float value, int decimals, int n)
        {
            float a = Math.Abs(value);
            bool neg = value < 0f;

            // Phrased !(a < ceiling) so NaN lands here too: every comparison against NaN is false, so a
            // NaN would otherwise reach the cast as 0 and print a confident "0.00".
            if (!(a < 16777216.0f)) return OverflowGlyph(neg, n);

            // The format field is 3 bits so it decodes 0..7, but only 0..5 is exact and
            // TryPackFormat refuses above 5. A hand-edited or debug-inspector write can still land 6 or
            // 7 here, so clamp to the same ceiling rather than computing digits we cannot represent.
            // The shader clamps identically.
            if (decimals > MaxDecimals) decimals = MaxDecimals;
            if (decimals < 0) decimals = 0;

            uint mult = Pow10(decimals);
            uint ip = (uint)Math.Floor(a);
            uint fp = (uint)Math.Floor((a - Math.Floor(a)) * mult + 0.5f);
            if (fp >= mult) { fp -= mult; ip += 1u; }   // rounding can carry: 1.999 at 2dp is 2.00

            uint digits = DigitCount(ip);
            uint needed = digits + (decimals > 0 ? (uint)decimals + 1u : 0u) + (neg ? 1u : 0u);
            if (needed > (uint)ValueGlyphs) return OverflowGlyph(neg, n);

            if (decimals > 0)
            {
                if (n < decimals) return (uint)Zero + ((fp / Pow10(n)) % 10u);
                if (n == decimals) return Dot;
            }

            int m = n - decimals - (decimals > 0 ? 1 : 0);   // m == 0 is the units digit
            if (m < 0) return (uint)Space;
            if (m < (int)digits) return (uint)Zero + ((ip / Pow10(m)) % 10u);
            if (m == (int)digits && neg) return Minus;
            return (uint)Space;
        }

        static uint OverflowGlyph(bool neg, int n)
        {
            if (n == 0) return Infinity;
            if (n == 1 && neg) return Minus;
            return Space;
        }

        /// <summary>
        /// The value field rendered left-to-right as text, exactly as the shader draws it — including
        /// the overflow glyph and the leading spaces. What the inspector previews and what the tests
        /// compare against <c>string.Format</c>, so the preview cannot disagree with the shader.
        /// </summary>
        public static string FormatValue(float value, int decimals)
        {
            var sb = new StringBuilder(ValueGlyphs);
            for (int n = ValueGlyphs - 1; n >= 0; n--)
            {
                uint id = ValueGlyphAt(value, decimals, n);
                sb.Append(id == Space ? ' ' : Charset[(int)id]);
            }
            return sb.ToString();
        }

        /// <summary>
        /// The largest rpad that leaves the value inside its own cell, given a cell width in glyph
        /// advances. The value's left edge sits at <c>cell_w_adv − rpad − ValueGlyphs</c>, so past this
        /// the value slides off the left of its cell and vanishes with NO on-screen diagnostic — which
        /// is why the bound is enforced here and previewed in the inspector rather than left to the
        /// 4-bit field's range.
        /// </summary>
        public static int MaxUsableRpad(float cellWidthAdvances)
        {
            int bound = (int)Math.Floor(cellWidthAdvances) - ValueGlyphs;
            return Mathf.Clamp(bound, 0, MaxRpad);
        }

        /// <summary>
        /// Where an entry's number comes from. A source earns a slot ONLY where an animator cannot
        /// measure the value — everything else uses <see cref="ValueSource.Animator"/> and a float
        /// property, which a plain clip curve drives (the shader is unlocked, so there is no Poiyomi
        /// <c>Animated</c>-tag step).
        ///
        /// <para>This enum is the canon for the source IDs; the shader's <c>switch</c> ladder and the
        /// entry README's table are echoes of it. IDs are wire values — never renumber, only append.</para>
        ///
        /// <para><b>Stage split.</b> <see cref="WorldX"/>..<see cref="Elevation"/> derive from
        /// <c>unity_ObjectToWorld</c> and are computed in the VERTEX stage, because
        /// <c>UnityInstancing.cginc</c> redefines that matrix through <c>unity_InstanceID</c>, which only
        /// <c>UNITY_SETUP_INSTANCE_ID</c> assigns and only in the vertex stage — a fragment-stage read
        /// compiles clean and silently returns instance 0's transform. The rest are camera/time/VRChat
        /// globals, read per-fragment.</para>
        /// </summary>
        public enum ValueSource
        {
            /// <summary>The entry's own <c>_E{i}_Value</c> float — the animation target. Default.</summary>
            Animator = 0,
            WorldX = 1, WorldY = 2, WorldZ = 3,
            ScaleX = 4, ScaleY = 5, ScaleZ = 6,
            /// <summary>Compass bearing of the object's +Z basis, 0° at world +Z increasing toward +X.
            /// This convention is OURS — the ancestor ships a compass form but that package is not on
            /// disk here, so we do not claim to match its convention.</summary>
            Azimuth = 7,
            Elevation = 8,
            /// <summary>Distance from the stereo-centre camera to the object origin. Measured by the
            /// OBSERVING client, so it reads inter-client distance directly. Deliberately NOT the
            /// ancestor's depth-texture rangefinder, whose own comment reads "Cannot detect presence of
            /// Depth texture, this may be garbage" — that texture is not reliably present on avatars.</summary>
            CameraDistance = 9,
            CameraFarPlane = 10,
            /// <summary>The observing client's smoothed frame rate, <c>unity_DeltaTime.w</c>. Unreachable
            /// by any animator parameter.</summary>
            ObserverFps = 11,
            TimeSeconds = 12,
            /// <summary>VRChat globals. Values are a managed echo of lilToon's declaration; re-read that
            /// source if a VRChat release moves them. Declared HLSL-only in the shader, never in
            /// Properties — a material property of the same name shadows the global and freezes it.</summary>
            VRChatCameraMode = 13,
            VRChatMirrorMode = 14,
            StereoEyeIndex = 15,
        }

        /// <summary>Highest defined source ID. The 5-bit field reaches 31; 16–31 are reserved for
        /// append-only growth.</summary>
        public const int MaxSource = 15;

        /// <summary>
        /// Packs the per-entry format config. Refuses out-of-range fields naming the offender rather
        /// than clamping — a clamped decimals count prints a different number than the author asked
        /// for, silently.
        /// </summary>
        public static bool TryPackFormat(int decimals, int palette, int rpad, ValueSource source,
                                         out float packed, out string error)
        {
            packed = 0f;
            error = null;

            if (decimals < 0 || decimals > MaxDecimals)
            { error = "decimals " + decimals + " out of range 0.." + MaxDecimals; return false; }
            if (palette < 0 || palette > 3)
            { error = "palette " + palette + " out of range 0..3"; return false; }
            if (rpad < 0 || rpad > MaxRpad)
            { error = "rpad " + rpad + " out of range 0.." + MaxRpad; return false; }
            if ((int)source < 0 || (int)source > MaxSource)
            { error = "source " + (int)source + " out of range 0.." + MaxSource; return false; }

            packed = (decimals << DecimalsShift)
                   | (palette << PaletteShift)
                   | (rpad << RpadShift)
                   | ((int)source << SourceShift);
            return true;
        }

        /// <summary>Unpacks the format float. Mirrors the shader's unpack exactly.</summary>
        public static void UnpackFormat(float packed, out int decimals, out int palette,
                                        out int rpad, out ValueSource source)
        {
            int bits = (int)packed;
            decimals = (bits >> DecimalsShift) & ((1 << DecimalsBits) - 1);
            palette  = (bits >> PaletteShift)  & ((1 << PaletteBits) - 1);
            rpad     = (bits >> RpadShift)     & ((1 << RpadBits) - 1);
            source   = (ValueSource)((bits >> SourceShift) & ((1 << SourceBits) - 1));
        }

        // ── Shader surface ──────────────────────────────────────────────────────────────────────────

        /// <summary>The shader this format belongs to. Namespaced rather than plain <c>Overlay/…</c>:
        /// the Lereldarion ancestor ships an <c>Overlay/*</c> family in a VPM package a consumer could
        /// install alongside ours, and a name collision resolves arbitrarily.</summary>
        public const string ShaderName = "Ryan6VRC/Overlay/DebugDisplay";

        /// <summary>Entries the shader compiles. A shader constant, not a preference: the fragment stage
        /// selects an entry's properties with a <c>switch</c> over this many cases.</summary>
        public const int MaxEntries = 12;

        /// <summary>Property name for an entry's packed label vector.</summary>
        public static string LabelProperty(int entry) { return "_E" + entry + "_Label"; }

        /// <summary>Property name for an entry's packed format float.</summary>
        public static string FormatProperty(int entry) { return "_E" + entry + "_Format"; }

        /// <summary>Property name for an entry's animation-target float. This name IS the binding path a
        /// consumer's clip writes (<c>material._E0_Value</c>), so the entry README publishes it.</summary>
        public static string ValueProperty(int entry) { return "_E" + entry + "_Value"; }
    }
}
