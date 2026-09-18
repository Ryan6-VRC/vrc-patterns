#ifndef RETICLE_CORE_INCLUDED
#define RETICLE_CORE_INCLUDED

// Reticle.shader's vertex and fragment stages, shared by its MAIN and GHOST passes. The two differ only in
// their depth test and in the GHOST pass defining RETICLE_GHOST_PASS, which dims and stripes the result.

#include "UnityCG.cginc"
#include "anchor_placement.hlsl"

uniform half4 _Color;
uniform float _Size;
uniform float _Style;
uniform float _Min_Degrees;
uniform float _Max_Degrees;
uniform float _Line_Width;
uniform float _Spin;
uniform float _Pulse;
uniform float _Acquire;
uniform float _Acquire_Scale;
uniform float _Depth_Fade;
uniform float _Ghost_Strength;
uniform float _Hide;

struct VertexInput
{
    float4 position_os : POSITION;
    float2 uv : TEXCOORD0;
    UNITY_VERTEX_INPUT_INSTANCE_ID
};

struct FragmentInput
{
    float4 position : SV_POSITION;
    // Plane coordinates, -1..1 across the drawn quad.
    float2 p : PLANE_POS;
    nointerpolation float3 anchor_ws : ANCHOR_WS;
    nointerpolation float fade : FADE;
    UNITY_VERTEX_OUTPUT_STEREO
};

void reticle_vertex(VertexInput input, out FragmentInput output)
{
    UNITY_SETUP_INSTANCE_ID(input);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

    AnchorPlacement place = place_anchor();
    output.anchor_ws = place.anchor_ws;

    float acquire = saturate(_Acquire);
    // Scale-in on latch: the quad grows to hold the enlarged reticle, the fragment draws it enlarged.
    float grow = lerp(_Acquire_Scale, 1, smoothstep(0, 1, acquire));
    float size = anchor_clamp_angular(_Size, place.dist, _Min_Degrees, _Max_Degrees) * grow;

    float visible = place.fade * acquire * (1 - saturate(_Hide));
    #if defined(RETICLE_GHOST_PASS)
        visible *= saturate(_Ghost_Strength);
    #else
        visible *= 1 - place.occluded;
    #endif
    output.fade = place.fade;

    if (visible <= 0.001)
    {
        output.position = float4(0, 0, 0, 0);
        output.p = 0;
        output.fade = 0;
        return;
    }

    output.p = (input.uv - 0.5) * 2;
    float3 offset_ws = (place.right_ws * output.p.x + place.up_ws * output.p.y) * (size * 0.5);
    output.position = anchor_clip_position(place, offset_ws);
}

// Signed-distance strokes, in plane units. Each returns coverage 0..1 anti-aliased over one pixel plus the
// authored width, so thin lines stay at least a pixel wide at any distance.
float stroke(float d, float half_width, float aa)
{
    return 1 - smoothstep(half_width, half_width + aa, abs(d));
}

float2 rotate2(float2 v, float a)
{
    float s, c;
    sincos(a, s, c);
    return float2(c * v.x - s * v.y, s * v.x + c * v.y);
}

half4 reticle_fragment(FragmentInput input) : SV_Target
{
    UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

    float2 p = input.p;
    float aa = fwidth(p.x) * 0.75;
    float hw = max(_Line_Width, aa);
    float r = length(p);
    float t = _Time.y;

    float acquire = smoothstep(0, 1, saturate(_Acquire));
    // The un-acquired reticle is drawn a quarter turn off and spins into place.
    float settle = (1 - acquire) * 1.5708;
    float2 ap = abs(p);
    float2 q = rotate2(p, t * _Spin + settle);
    float ang = atan2(q.y, q.x);
    float dot_ = 1 - smoothstep(0.04, 0.04 + aa, r);
    float shape = 0;

    int style = (int)round(_Style);
    if (style == 1)
    {
        // Corners: four L brackets on a square, plus the dot. Nothing spins; the acquire settle rotates it in.
        float2 c = abs(rotate2(p, settle));
        float on_edge = stroke(max(c.x, c.y) - 0.85, hw, aa);
        float near_corner = step(0.5, min(c.x, c.y));
        shape = max(on_edge * near_corner, dot_);
    }
    else if (style == 2)
    {
        // Radar: two thin rings and a sweeping wedge that fades behind its leading edge.
        shape = max(stroke(r - 0.5, hw * 0.7, aa), stroke(r - 0.92, hw * 0.7, aa));
        float sweep_ang = frac(-ang / 6.2832);
        float wedge = pow(1 - sweep_ang, 6) * step(r, 0.9) * 0.6;
        shape = max(shape, max(wedge, dot_));
    }
    else if (style == 3)
    {
        // Chevrons: four triangles on the axes pointing in, inside a spinning dashed ring.
        float2 a = float2(max(ap.x, ap.y), min(ap.x, ap.y));
        float tri = step(a.y, (a.x - 0.45) * 0.6) * step(0.45, a.x) * step(a.x, 0.72);
        float dashes = stroke(r - 0.92, hw, aa) * step(0.5, frac(ang / 6.2832 * 12));
        shape = max(max(tri, dashes), dot_);
    }
    else if (style == 4)
    {
        // Minimal: a gapped cross and one orbiting dash.
        float cross_ = stroke(min(ap.x, ap.y), hw * 0.8, aa) * step(0.18, max(ap.x, ap.y)) * step(max(ap.x, ap.y), 0.7);
        float dash = stroke(r - 0.85, hw, aa) * step(abs(frac(ang / 6.2832) - 0.5), 0.08);
        shape = max(max(cross_, dash), dot_);
    }
    else
    {
        // Classic: ring, four ticks gapped off it, dot, and four spinning arc brackets outside.
        shape = stroke(r - 0.5, hw, aa);
        float tick = stroke(min(ap.x, ap.y), hw, aa) * step(0.62, max(ap.x, ap.y)) * step(max(ap.x, ap.y), 0.86);
        float arc_gate = step(abs(frac(ang / 1.5708 + 0.5) - 0.5), 0.34);
        shape = max(max(shape, tick), max(dot_, stroke(r - 0.88, hw, aa) * arc_gate));
    }

    float pulse = 1 + _Pulse * sin(t * 6.2832);
    float alpha = shape * _Color.a * input.fade * saturate(_Acquire) * pulse;

    #if defined(RETICLE_GHOST_PASS)
        // Striped in plane space, not screen space: a screen-space pattern has no disparity of its own.
        alpha *= saturate(_Ghost_Strength) * step(0.5, frac(p.y * 8));
    #else
        if (_Depth_Fade > 0.5 && anchor_depth_usable())
        {
            float in_front = anchor_scene_in_front_by(input.position, input.position.xy, input.anchor_ws);
            // Fully faded by the window's edge, starting to go from half of it.
            alpha *= 1 - smoothstep(_Snap_Window * 0.5, _Snap_Window, in_front);
        }
    #endif

    // Additive: rgb carries the alpha, so nothing can black out the view.
    return half4(_Color.rgb * alpha, 0);
}

#endif // RETICLE_CORE_INCLUDED
