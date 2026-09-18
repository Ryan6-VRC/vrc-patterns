#ifndef ANCHOR_PLACEMENT_INCLUDED
#define ANCHOR_PLACEMENT_INCLUDED

// Where a marker for a BURIED point gets drawn. Reticle and Mosaic both mark a measured point that sits
// inside a body or behind cloth (a contact sender's origin), and both must read as placed in the world in a
// headset rather than as a hole punched through it. One home for the billboard, the pull and the fade the
// two share.
//
// Everything moves along the line from the stereo-CENTRE eye to the anchor and no other: it keeps the
// marker over the anchor as the viewer sees it, and the centre eye (stereo_camera.hlsl) keeps the result
// identical in both eyes. Neither placement reads a depth texture, so neither needs a DepthLight.
//
// Fixed pull (Reticle) -- the geometry moves _Pull metres toward the viewer, so the eyes converge in front
//                         of what buried the point and disparity agrees with draw order. It floats off a
//                         bare surface by the same distance.
// Depth bias (Mosaic)  -- the geometry stays AT the anchor and only the depth-test value is pulled, so the
//                         eyes converge behind the surface the marker is painted over. A reticle and a
//                         mosaic on one anchor therefore sit _Pull apart in depth.

#include "UnityCG.cginc"
#include "stereo_camera.hlsl"

uniform float _Pull;
uniform float _Fade_Near;
uniform float _Fade_Far;

struct AnchorPlacement
{
    float3 anchor_ws;
    // Where the geometry goes.
    float3 placed_ws;
    // Where the depth TEST is taken. Equal to placed_ws except under depth bias.
    float3 depth_proxy_ws;
    bool bias_only;
    // Billboard basis: right and up as the viewer sees them, world-up so head roll does not turn the marker.
    float3 right_ws;
    float3 up_ws;
    // Centre eye to placed_ws.
    float dist;
    // 0 inside _Fade_Near, 1 beyond _Fade_Far. The whole marker fades as one, because a per-fragment fade
    // leaves a large overlay filling the view at arm's length.
    float fade;
};

AnchorPlacement place_anchor(bool bias_only)
{
    AnchorPlacement o;
    o.anchor_ws = float3(unity_ObjectToWorld._m03, unity_ObjectToWorld._m13, unity_ObjectToWorld._m23);

    float3 center_ws = dbg_camera_center_ws();
    float3 to_eye = center_ws - o.anchor_ws;
    float anchor_dist = max(length(to_eye), 1e-4);
    float3 fwd = to_eye / anchor_dist;

    float3 right = cross(fwd, float3(0, 1, 0));
    float right_len = length(right);
    // Looking straight down or up the world axis: any horizontal right will do, it only must not be NaN.
    right = right_len > 1e-3 ? right / right_len : float3(1, 0, 0);
    o.right_ws = right;
    o.up_ws = cross(right, fwd);

    // Never pull the marker closer to the face than the distance it has fully faded in at.
    float pull = min(max(_Pull, 0), max(anchor_dist - _Fade_Far, 0));

    float3 pulled_ws = o.anchor_ws + fwd * pull;
    o.placed_ws = bias_only ? o.anchor_ws : pulled_ws;
    o.depth_proxy_ws = pulled_ws;
    o.bias_only = bias_only;
    o.dist = max(distance(center_ws, o.placed_ws), 1e-4);
    o.fade = smoothstep(_Fade_Near, max(_Fade_Far, _Fade_Near + 1e-3), o.dist);
    return o;
}

/// Clip position for a world point on the placed billboard, with the depth-test value taken from the
/// matching point on the depth proxy plane (identical unless under depth bias).
float4 anchor_clip_position(AnchorPlacement p, float3 offset_ws)
{
    float4 clip = mul(UNITY_MATRIX_VP, float4(p.placed_ws + offset_ws, 1));
    if (!p.bias_only) return clip;
    float4 proxy = mul(UNITY_MATRIX_VP, float4(p.depth_proxy_ws + offset_ws, 1));
    clip.z = proxy.z / max(proxy.w, 1e-4) * clip.w;
    return clip;
}

/// A world size held between two angular sizes, given in degrees of the viewer's field, edge to edge.
float anchor_clamp_angular(float size, float dist, float min_degrees, float max_degrees)
{
    float lo = 2 * dist * tan(radians(min_degrees * 0.5));
    float hi = max(2 * dist * tan(radians(max_degrees * 0.5)), lo);
    return clamp(size, lo, hi);
}

#endif // ANCHOR_PLACEMENT_INCLUDED
