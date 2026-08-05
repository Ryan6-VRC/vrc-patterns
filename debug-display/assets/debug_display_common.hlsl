#ifndef DEBUG_DISPLAY_COMMON_INCLUDED
#define DEBUG_DISPLAY_COMMON_INCLUDED

// Shared substrate for Ryan6VRC/Overlay/DebugDisplay: font metrics, MSDF sampling, stereo-correct camera
// helpers, the label/format unpack, value formatting, and the cell-grid layout. Both passes include this,
// matching the ancestor's own overlay_common.hlsl idiom -- so splitting out a genuinely text-only shader
// later is an added file rather than a refactor.
//
// Provenance: derived from lereldarion/unity-shaders (MIT, (c) 2025 Lereldarion), ancestor
// Shaders/Overlay_HUD.shader. The Font metric ratios and median()/sdf_blend_with_aa() are upstream's; the
// 6-bit charset, the entry grid, the per-entry value sources, and the three display modes are ours.
// See the entry README for the line-by-line split.

#include "UnityCG.cginc"

// ── Camera, stereo-correct ──────────────────────────────────────────────────────────────────────────
//
// THE ANCESTOR'S GUARD IS DEAD CODE IN VRCHAT AND WE FIX IT HERE. Upstream tests
// `#ifdef UNITY_SINGLE_PASS_STEREO`, which is the deprecated double-wide path. VRChat PC runs single-pass
// INSTANCED: HLSLSupport.cginc:26-27 defines UNITY_STEREO_INSTANCING_ENABLED from STEREO_INSTANCING_ON,
// and UnityShaderVariables.cginc:10-12 folds that into USING_STEREO_MATRICES -- under which line 24 has
// already redefined _WorldSpaceCameraPos to unity_StereoWorldSpaceCameraPos[unity_StereoEyeIndex].
//
// So upstream's two helpers both fall through to a PER-EYE position. The eye one is right by accident;
// the centre one is not, and the billboard plane's normal comes from it, which means the plane orients
// differently per eye and the text's stereo disparity corresponds to no fixed plane at all. Poiyomi gets
// this right the same way (CGI_PoiHelpers.cginc:68-74).
float3 dd_camera_eye_ws()
{
    #if defined(USING_STEREO_MATRICES)
        return unity_StereoWorldSpaceCameraPos[unity_StereoEyeIndex];
    #else
        return _WorldSpaceCameraPos.xyz;
    #endif
}

float3 dd_camera_center_ws()
{
    #if defined(USING_STEREO_MATRICES)
        return 0.5 * (unity_StereoWorldSpaceCameraPos[0] + unity_StereoWorldSpaceCameraPos[1]);
    #else
        return _WorldSpaceCameraPos.xyz;
    #endif
}

// VRChat-set globals. DECLARED HERE AND DELIBERATELY NOT IN Properties: a material property of the same
// name makes Unity serialize a value into every material, leaving no unset state for SetGlobalFloat to
// fill, so the material's stale value would win forever. Poiyomi declares them the same way. Semantics
// are a managed echo of lilToon's declaration -- re-read that source if a VRChat release moves them.
//   _VRChatCameraMode: 0 normal, 1 VR handheld cam, 2 desktop handheld cam, 3 screenshot/photo
//   _VRChatMirrorMode: 0 normal, 1 mirror (VR), 2 mirror (desktop)
uniform float _VRChatCameraMode;
uniform float _VRChatMirrorMode;

// ── MSDF sampling (upstream) ────────────────────────────────────────────────────────────────────────

UNITY_DECLARE_TEX2D(_MSDF_Glyph_Atlas);

float dd_screenspace_scale_of_uv(float2 uv)
{
    float2 dx = ddx_fine(uv);
    float2 dy = ddy_fine(uv);
    const float2 screenspace_uv_scales = sqrt((dx * dx) + (dy * dy));
    return 0.5 * (screenspace_uv_scales.x + screenspace_uv_scales.y);
}

float dd_sdf_blend_with_aa(float sdf, float screenspace_scale_of_uv)
{
    const float w = 0.5 * screenspace_scale_of_uv;
    return smoothstep(-w, w, -sdf);
}

// ── Font ────────────────────────────────────────────────────────────────────────────────────────────

struct Font
{
    // Emitted by tools/generate_atlas.ps1 from the charset canon (DisplayGlyphs.Charset), NOT hand-typed.
    // Regenerating the atlas re-emits these; a mismatch garbles every glyph uniformly, which is why the
    // generator prints them and the entry README records the run that produced the committed PNG.
    static const float2 atlas_size_px = float2(256, 256);
    static const float2 cell_size_px = float2(23, 29);
    static const float atlas_distance_range_px = 2;
    static const uint grid_columns = 8;

    static const float2 glyph_bottom_left_em = float2(-0.02144944, -0.10227937);
    static const float2 glyph_top_right_em = float2(0.62144944, 0.71595558);
    static const float2 glyph_size_em = glyph_top_right_em - glyph_bottom_left_em;

    // px-per-em. This IS the generator's -size argument: msdf-atlas-gen's -size is pixels-per-em, so the
    // number transfers directly and is uniform across both axes "due to monospace". The ancestor derived
    // the same 34.22 as (cell_size_px - 1) / glyph_size_em; taking it from the generator instead retires
    // that fragile 1px-margin assumption.
    static const float em_to_px = 34.22;

    static const float advance_px = 0.6 * em_to_px;          // advance_em from the atlas JSON
    static const float ascender_px = 1.005 * em_to_px;       // ascender_em
    static const float glyph_left_px = glyph_bottom_left_em.x * em_to_px;
    static const float2 glyph_bbox_px = float2(advance_px, glyph_size_em.y * em_to_px);

    // 15% vertical line padding. Promoted from a local inside the ancestor's draw_glyphs_10x3 into a Font
    // static, because the cell arithmetic now needs it: a cell is layout_bbox_px.y tall while a glyph box
    // is only glyph_bbox_px.y, and the difference is a band that must be REJECTED rather than sampled
    // (see dd_glyph_band_offset).
    static const float line_pad = 1.15;
    static const float2 layout_bbox_px = float2(glyph_bbox_px.x, glyph_bbox_px.y * line_pad);

    // 6-bit charset. Only these IDs are named on the shader side -- the alphabetic half is never needed
    // here, because labels arrive pre-encoded from the packer. Values follow from the charset's
    // codepoint order (msdf-atlas-gen lays the uniform grid out by codepoint, not by charset-file order),
    // and DisplayGlyphs.cs is their canon; the C# tests pin them.
    static const uint bits = 6;
    static const uint mask = (1u << bits) - 1u;
    static const uint space = mask;      // 63 -- the sentinel, and the one ID with no atlas cell
    static const uint plus = 8;
    static const uint minus = 10;
    static const uint dot = 11;
    static const uint zero = 13;         // digits are contiguous from here, which is all the arithmetic needs
    static const uint infinity = 62;

    static float median(float3 msd) { return max(min(msd.r, msd.g), min(max(msd.r, msd.g), msd.b)); }

    float2 sampling_offset_px;
    uint sampling_atlas_id;
    float scale;
    float inverse_scale;

    static Font init(float font_size)
    {
        Font r;
        r.inverse_scale = font_size / ascender_px;
        r.scale = 1.0 / r.inverse_scale;
        r.sampling_offset_px = float2(0, 0);
        r.sampling_atlas_id = space;
        return r;
    }

    float sdf()
    {
        if (sampling_atlas_id == space) return 1000.0;
        const uint atlas_row = sampling_atlas_id / grid_columns;
        const uint atlas_column = sampling_atlas_id - atlas_row * grid_columns;
        // Glyph 0 sits in the TOP-left cell -- verified against the emitted atlas, which is what
        // -yorigin bottom produces. Hence atlas_size_px.y - cell*(row+1) rather than cell*row.
        const float2 atlas_offset_px = float2(atlas_column * cell_size_px.x,
                                              atlas_size_px.y - cell_size_px.y * (atlas_row + 1)) + 0.5;
        const float2 glyph_offset_px = sampling_offset_px - float2(glyph_left_px, 0);
        const float tex_sd = median(UNITY_SAMPLE_TEX2D_LOD(
            _MSDF_Glyph_Atlas, (glyph_offset_px + atlas_offset_px) / atlas_size_px, 0).rgb) - 0.5;
        const float tex_sd_pixel = -tex_sd * 2 * atlas_distance_range_px;
        return inverse_scale * tex_sd_pixel;
    }
};

// ── Label unpack ────────────────────────────────────────────────────────────────────────────────────

#define DD_MAX_LABEL_CHARS 12
#define DD_CHARS_PER_COMPONENT 3
#define DD_VALUE_GLYPHS 10
#define DD_MAX_ENTRIES 12

// Mirrors DisplayGlyphs.TryEncodeLabel: 3 chars per float4 component, LSB-first, 6 bits each. Three and
// not four because a 24-bit component does not survive d4rkAvatarOptimizer's text round-trip of material
// properties (float.ToString() is G7); 18 bits caps at 262143, six digits, which does.
// n is unsigned deliberately: the compiler warns that signed integer divides "may be much slower, try
// using uints if possible", and a label column is never negative.
uint dd_label_glyph_at(float4 packed, uint n)
{
    uint c = n / (uint)DD_CHARS_PER_COMPONENT;
    uint k = n - c * (uint)DD_CHARS_PER_COMPONENT;
    uint acc = (uint)packed[c];
    return (acc >> (k * Font::bits)) & Font::mask;
}

// ── Format bitfield unpack ──────────────────────────────────────────────────────────────────────────

// Mirrors DisplayGlyphs.TryPackFormat, LSB-first: decimals(3) palette(2) rpad(4) source(5) = 14 bits.
void dd_unpack_format(float packed, out uint decimals, out uint palette, out uint rpad, out uint source)
{
    uint bits = (uint)packed;
    decimals = bits & 7u;
    palette = (bits >> 3u) & 3u;
    rpad = (bits >> 5u) & 15u;
    source = (bits >> 9u) & 31u;
}

// ── Value formatting ────────────────────────────────────────────────────────────────────────────────

uint dd_pow10(uint k)
{
    uint r = 1u;
    [unroll]
    for (uint i = 0u; i < 6u; i++) { if (i < k) r *= 10u; }
    return r;
}

uint dd_digit_count(uint v)
{
    uint d = 1u;
    [unroll]
    for (uint i = 0u; i < 9u; i++) { if (v >= dd_pow10(i + 1u)) d++; }
    return d;
}

// Returns the glyph for column `n` of the value field, counted from the RIGHT (0 = rightmost).
//
// Resolved directly rather than by formatting into a local array. The ancestor built a uint glyphs[10]
// and packed it into interpolants, which only worked because its three rows were per-object constants; a
// generalized grid must format per-fragment (a vertex does not know its cell -- the cell index comes from
// frame_uv, which in two of three modes only exists after the fragment-stage ray-trace). Doing it per
// column keeps that O(1) with no dynamically-indexed local array, which is what would otherwise land in
// an indexable temp and cost occupancy.
//
// PRECISION: the ancestor computed (uint)(abs(pos) * 10^decimals), so digits were exact only while
// |value| * 10^d < 2^24 -- 167.77 at 5 decimals. It got away with fixed 2 decimals at avatar scale; we
// ship _Time.y, _ProjectionParams.z and arbitrary animator floats, so the parts are split and the
// multiply never leaves the exact range. Retained ceiling: integer part exact to 16,777,215, decimals
// always exact.
uint dd_value_glyph_at(float value, uint decimals, int n)
{
    float a = abs(value);
    bool neg = value < 0.0;

    // The escape the ancestor had and an earlier draft of the spec dropped while keeping the constant.
    // Phrased as !(a < ceiling) so NaN lands here too -- every comparison against NaN is false, so a NaN
    // would otherwise reach (uint)NaN == 0 and print "0.00", which is a lie where a diagnostic belongs.
    if (!(a < 16777216.0))
    {
        if (n == 0) return Font::infinity;
        if (n == 1 && neg) return Font::minus;
        return Font::space;
    }

    uint mult = dd_pow10(decimals);
    uint ip = (uint)floor(a);
    uint fp = (uint)floor(frac(a) * (float)mult + 0.5);
    // Rounding the fraction can carry: 1.999 at 2 decimals rounds to 2.00, not 1.100.
    if (fp >= mult) { fp -= mult; ip += 1u; }

    if (decimals > 0u)
    {
        if (n < (int)decimals) return Font::zero + ((fp / dd_pow10((uint)n)) % 10u);
        if (n == (int)decimals) return Font::dot;
    }

    // m == 0 is the units digit.
    int m = n - (int)decimals - (decimals > 0u ? 1 : 0);
    if (m < 0) return Font::space;
    uint digits = dd_digit_count(ip);
    if (m < (int)digits) return Font::zero + ((ip / dd_pow10((uint)m)) % 10u);
    if (m == (int)digits && neg) return Font::minus;
    return Font::space;
}

// ── Value sources ───────────────────────────────────────────────────────────────────────────────────
//
// IDs are the wire values DisplayGlyphs.ValueSource declares; this ladder is an echo of that enum.
//
// Sources 1-8 arrive as vertex-computed interpolants rather than being read here, and that is not a
// preference. UnityInstancing.cginc:343 redefines unity_ObjectToWorld through unity_InstanceID, a static
// uint that only UNITY_SETUP_INSTANCE_ID assigns and only in the vertex stage -- a fragment-stage read
// compiles clean and silently returns instance 0's transform, which is the same class of wrong number
// DisableBatching exists to prevent. The pragma cannot simply go either: multi_compile_instancing is what
// generates STEREO_INSTANCING_ON, hence USING_STEREO_MATRICES, hence working VR.
//   obj_a = (world x, world y, world z, azimuth)
//   obj_b = (scale x, scale y, scale z, elevation)
float dd_resolve_value(uint source, float entry_value, float4 obj_a, float4 obj_b)
{
    switch (source)
    {
        case 0u:  return entry_value;            // the animation target
        case 1u:  return obj_a.x;
        case 2u:  return obj_a.y;
        case 3u:  return obj_a.z;
        case 4u:  return obj_b.x;
        case 5u:  return obj_b.y;
        case 6u:  return obj_b.z;
        case 7u:  return obj_a.w;                // azimuth, degrees
        case 8u:  return obj_b.w;                // elevation, degrees
        case 9u:  return distance(dd_camera_center_ws(), obj_a.xyz);
        case 10u: return _ProjectionParams.z;    // far plane
        case 11u: return unity_DeltaTime.w;      // observer's smoothed fps
        case 12u: return _Time.y;
        case 13u: return _VRChatCameraMode;
        case 14u: return _VRChatMirrorMode;
        case 15u: return (float)unity_StereoEyeIndex;
        default:  return entry_value;            // reserved IDs read as the animator float
    }
}

// Per-object constants for sources 1-8, computed in the vertex stage. Compass convention is OURS: azimuth
// 0 degrees at world +Z increasing toward +X, range 0-360; elevation -90..+90. The ancestor ships a
// compass form but that package is not on disk here, so we do not claim to match its convention. Full
// Euler is deliberately absent -- it needs an arbitrary order convention.
void dd_object_sources(out float4 obj_a, out float4 obj_b)
{
    float3 origin_ws = float3(unity_ObjectToWorld._m03, unity_ObjectToWorld._m13, unity_ObjectToWorld._m23);
    float3 basis_x = float3(unity_ObjectToWorld._m00, unity_ObjectToWorld._m10, unity_ObjectToWorld._m20);
    float3 basis_y = float3(unity_ObjectToWorld._m01, unity_ObjectToWorld._m11, unity_ObjectToWorld._m21);
    float3 basis_z = float3(unity_ObjectToWorld._m02, unity_ObjectToWorld._m12, unity_ObjectToWorld._m22);

    float3 fwd = normalize(basis_z);
    float azimuth = degrees(atan2(fwd.x, fwd.z));
    if (azimuth < 0.0) azimuth += 360.0;
    float elevation = degrees(asin(clamp(fwd.y, -1.0, 1.0)));

    obj_a = float4(origin_ws, azimuth);
    obj_b = float4(length(basis_x), length(basis_y), length(basis_z), elevation);
}

// ── Cell grid ───────────────────────────────────────────────────────────────────────────────────────

// The band between a cell's padded height and its glyph box. Rejecting it is a CORRECTNESS guard, not
// cosmetic padding: Font::sdf() clamps nothing, and atlas_offset_px.y is measured from the cell's top, so
// a sample past the band reads the atlas cell directly above and bleeds that glyph into the top of every
// rendered cell.
float dd_glyph_band_offset()
{
    return (Font::layout_bbox_px.y - Font::glyph_bbox_px.y) * 0.5;
}

#endif // DEBUG_DISPLAY_COMMON_INCLUDED
