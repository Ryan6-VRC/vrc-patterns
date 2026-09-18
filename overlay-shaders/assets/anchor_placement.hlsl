#ifndef ANCHOR_PLACEMENT_INCLUDED
#define ANCHOR_PLACEMENT_INCLUDED

// Where a marker for a BURIED point gets drawn. Reticle and Mosaic both mark a measured point that sits
// inside a body or behind cloth (a contact sender's origin), and both must read as placed in the world in a
// headset rather than as a hole punched through it. One home, because the two must agree exactly: a mosaic
// and a reticle on the same anchor land on the same plane.
//
// THE RULE EVERYTHING HERE SERVES: stereo disparity and draw order must tell the same story. Drawing a
// quad at the buried point with its depth test defeated makes the eyes converge BEHIND a surface the quad
// is painted over, and that conflict is what reads as wrong. So the marker is genuinely MOVED toward the
// viewer, along the line from the stereo-CENTRE eye to the anchor, until it is in front of what buried it.
// Along that line and no other: it keeps the marker over the anchor as the viewer sees it, and the centre
// eye (stereo_camera.hlsl) keeps the moved position identical in both eyes.
//
// Placement 0, fixed pull   -- move by _Pull metres. No depth texture needed; floats off a bare surface.
// Placement 1, depth bias   -- geometry stays AT the anchor and only the depth-test value is pulled. This
//                              is the conflict described above, kept as a measurable candidate.
// Placement 2, surface snap -- read the depth texture along the line and stop just in front of the nearest
//                              surface inside _Snap_Window. Buried deeper than the window (a wall, not a
//                              skirt) reports occluded instead of tunnelling out.
//
// THE SNAP SAMPLES EYE 0 ONLY, FROM THE VERTEX STAGE, and that is the whole trick. Each eye's depth
// texture sees a different surface point behind the same anchor, so a per-eye answer would place the two
// eyes' quads at different distances. One eye's slice, read explicitly, gives every vertex in both eyes the
// same number.
//
// DEPTH IS IGNORED IN MIRRORS. A mirror camera renders no depth texture of its own, so the global still
// holds the main camera's; placement 2 falls back to placement 0 there, and the fragment-side helpers
// below report "nothing in front".

#include "UnityCG.cginc"
#include "stereo_camera.hlsl"
#include "depth_reconstruct.hlsl"

uniform float _Placement;
uniform float _Pull;
uniform float _Use_Depth;
uniform float _Snap_Window;
uniform float _Snap_Gap;
uniform float _Snap_Tap_Radius;
uniform float _Fade_Near;
uniform float _Fade_Far;
uniform float _VRChatMirrorMode;

struct AnchorPlacement
{
    float3 anchor_ws;
    // Where the geometry goes.
    float3 placed_ws;
    // Where the depth TEST is taken. Equal to placed_ws except under placement 1.
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
    // 1 when the snap found the anchor buried deeper than the window.
    float occluded;
};

bool anchor_depth_usable()
{
    return _Use_Depth > 0.5 && _VRChatMirrorMode == 0;
}

/// Eye depth of the nearest surface in front of `point_ws` as eye 0 sees it, or a huge value for sky.
float anchor_eye0_scene_depth(float3 point_ws, out float point_depth)
{
    #if defined(USING_STEREO_MATRICES)
        float4 clip = mul(unity_StereoMatrixVP[0], float4(point_ws, 1));
    #else
        float4 clip = mul(UNITY_MATRIX_VP, float4(point_ws, 1));
    #endif
    point_depth = clip.w;
    if (clip.w <= 1e-4) return 1e6;
    // ComputeScreenPos's uv. It equals depth_reconstruct.hlsl's SV_Position * texel size whenever the
    // camera renders to a texture (_ProjectionParams.x = -1), which every VRChat camera does.
    float2 uv = float2(clip.x, clip.y * _ProjectionParams.x) / clip.w * 0.5 + 0.5;

    #if defined(UNITY_STEREO_INSTANCING_ENABLED) || defined(UNITY_STEREO_MULTIVIEW_ENABLED)
        float raw = _CameraDepthTexture.SampleLevel(sampler_CameraDepthTexture, float3(uv, 0), 0).r;
    #else
        float raw = SAMPLE_DEPTH_TEXTURE_LOD(_CameraDepthTexture, float4(uv, 0, 0));
    #endif

    if (any(uv < 0) || any(uv > 1) || raw < 0.0001) return 1e6;
    return LinearEyeDepth(raw);
}

AnchorPlacement place_anchor()
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
    float pull_limit = max(anchor_dist - _Fade_Far, 0);
    float pull = min(max(_Pull, 0), pull_limit);
    o.occluded = 0;

    int placement = (int)round(_Placement);
    if (placement == 2 && !anchor_depth_usable()) placement = 0;

    if (placement == 2)
    {
        // Five taps a few centimetres apart: one pixel at a cloth edge flickers between skirt and thigh
        // frame to frame, and the nearest of five moves less than any one of them.
        float3 tap_offsets[5] = { float3(0, 0, 0), right, -right, o.up_ws, -o.up_ws };
        float nearest = 1e6;
        float anchor_depth = 1;
        int buried = 0;
        for (int i = 0; i < 5; i++)
        {
            float tap_depth;
            float scene = anchor_eye0_scene_depth(o.anchor_ws + tap_offsets[i] * _Snap_Tap_Radius, tap_depth);
            if (i == 0) anchor_depth = max(tap_depth, 1e-4);
            float in_front_by = tap_depth - scene;
            if (in_front_by > _Snap_Window) buried++;
            else if (in_front_by > 0) nearest = min(nearest, scene);
        }

        if (buried >= 3)
        {
            o.occluded = 1;
            pull = 0;
        }
        else
        {
            // _Pull is not consulted here: the depth texture decides how far. Eye-0 depth ratios stand in
            // for centre-eye distance ratios; the two rays are a few degrees apart at any distance the
            // marker is visible from. The window is view depth; along the ray it is longer by the same
            // ratio, so the cap is scaled the same way.
            float target_depth = min(nearest, anchor_depth) - _Snap_Gap;
            float ray_per_depth = anchor_dist / anchor_depth;
            pull = clamp(anchor_dist * (1 - target_depth / anchor_depth), 0, (_Snap_Window + _Snap_Gap) * ray_per_depth);
            // A surface nearer than the fade-in distance cannot be reached without entering the near
            // fade; drawing short of it would bury the marker again, so hide instead.
            if (pull > pull_limit) { o.occluded = 1; pull = 0; }
        }
    }

    float3 pulled_ws = o.anchor_ws + fwd * pull;
    o.placed_ws = placement == 1 ? o.anchor_ws : pulled_ws;
    o.depth_proxy_ws = pulled_ws;
    o.bias_only = placement == 1;
    o.dist = max(distance(center_ws, o.placed_ws), 1e-4);
    o.fade = smoothstep(_Fade_Near, max(_Fade_Far, _Fade_Near + 1e-3), o.dist);
    return o;
}

/// Clip position for a world point on the placed billboard, with the depth-test value taken from the
/// matching point on the depth proxy plane (identical unless placement is 1).
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

/// SV_Position.xy of a world point in the eye being rendered -- the inverse of
/// DepthReconstruction::clip_position, so the two agree on which pixel a point lands in.
float2 anchor_pixel_of(float3 point_ws)
{
    float4 clip = mul(UNITY_MATRIX_VP, float4(point_ws, 1));
    return ((clip.xy / clip.w) * float2(1, -1) * 0.5 + 0.5) * _ScreenParams.xy;
}

/// How far in front of the anchor the scene surface under `pixel` is, in metres along the eye ray.
/// Positive = something is in front of the anchor; negative = the scene is behind it. Fragment stage only.
float anchor_scene_in_front_by(float4 fragment_sv_position, float2 pixel, float3 anchor_ws)
{
    DepthReconstruction dr = DepthReconstruction::init(fragment_sv_position);
    float3 scene_vs = dr.position_vs(pixel - fragment_sv_position.xy);
    float3 scene_ws = mul(unity_MatrixInvV, float4(scene_vs, 1)).xyz;
    float3 eye_ws = dbg_camera_eye_ws();
    return distance(eye_ws, anchor_ws) - distance(eye_ws, scene_ws);
}

#endif // ANCHOR_PLACEMENT_INCLUDED
