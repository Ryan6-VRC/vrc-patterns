#ifndef MOSAIC_CORE_INCLUDED
#define MOSAIC_CORE_INCLUDED

// Mosaic.shader's stages.
//
// THE GRID LIVES ON A WORLD-SPACE PLANE, NEVER ON THE SCREEN. A screen-aligned cell grid has zero
// disparity, so in a headset it reads as locked to the head, at infinity, while the scene swims under it.
// Here the cells are metres on a billboard plane through the placed anchor, so the grid sits at that
// plane's depth in both eyes; each eye samples its own colour behind each cell's centre, and the cell
// membership test (is this cell inside the disc) is on the plane, identical in both eyes -- which is what
// makes the quantized edge stereo-stable.

#include "UnityCG.cginc"
#include "anchor_placement.hlsl"

uniform float _Radius;
uniform float _Cell_Size;
uniform float _Min_Cell_Degrees;
uniform float _Max_Degrees;
uniform float _Grid_World_Snap;
uniform float _Cell_Occlusion;
uniform float _Hug;
uniform float _Hug_Back;
uniform half4 _Tint;
uniform float _Hide;

// TEX2D, not the screenspace array pair: a BiRP GrabPass target is not rebound as an array under
// single-pass instanced. GammaCrystal's declaration, measured in a headset; do not "fix" from macros.
UNITY_DECLARE_TEX2D(_MosaicGrabTexture);

struct VertexInput
{
    float4 position_os : POSITION;
    float2 uv : TEXCOORD0;
    UNITY_VERTEX_INPUT_INSTANCE_ID
};

struct FragmentInput
{
    float4 position : SV_POSITION;
    // Plane coordinates in metres from the placed anchor.
    float2 p : PLANE_POS;
    nointerpolation float3 placed_ws : PLACED_WS;
    nointerpolation float3 anchor_ws : ANCHOR_WS;
    nointerpolation float3 right_ws : RIGHT_WS;
    nointerpolation float3 up_ws : UP_WS;
    // x = cell size, y = radius, both metres on the plane after the angular clamps.
    nointerpolation float2 grid : GRID;
    // Grid origin offset in plane metres, so a cell edge can sit on a world lattice.
    nointerpolation float2 grid_origin : GRID_ORIGIN;
    nointerpolation float fade : FADE;
    UNITY_VERTEX_OUTPUT_STEREO
};

void mosaic_vertex(VertexInput input, out FragmentInput output)
{
    UNITY_SETUP_INSTANCE_ID(input);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

    AnchorPlacement place = place_anchor();
    output.placed_ws = place.placed_ws;
    output.anchor_ws = place.anchor_ws;
    output.right_ws = place.right_ws;
    output.up_ws = place.up_ws;
    output.fade = place.fade * (1 - saturate(_Hide));

    float visible = output.fade * (1 - place.occluded);
    if (visible <= 0.001)
    {
        output.position = float4(0, 0, 0, 0);
        output.p = 0;
        output.grid = 0;
        output.grid_origin = 0;
        output.fade = 0;
        return;
    }

    // The cell has an angular floor so far cells never shrink below a pixel or two; the disc has an
    // angular ceiling so a near one cannot fill the view. Both per object, never per fragment.
    float cell = max(_Cell_Size, 2 * place.dist * tan(radians(_Min_Cell_Degrees * 0.5)));
    float radius = min(_Radius, place.dist * tan(radians(_Max_Degrees * 0.5)));
    output.grid = float2(cell, radius);

    // World snap: the grid origin sits on the lattice the plane's own axes cut through the anchor, so a
    // moving anchor makes cells pop rather than slide. Off, the grid moves with the anchor.
    float2 lattice = float2(dot(place.placed_ws, place.right_ws), dot(place.placed_ws, place.up_ws));
    output.grid_origin = _Grid_World_Snap > 0.5 ? -frac(lattice / cell) * cell : 0;

    float extent = (radius + cell) * 2;
    output.p = (input.uv - 0.5) * extent;
    float3 offset_ws = place.right_ws * output.p.x + place.up_ws * output.p.y;
    output.position = anchor_clip_position(place, offset_ws);
}

half3 mosaic_grab(float3 point_ws)
{
    float4 clip = mul(UNITY_MATRIX_VP, float4(point_ws, 1));
    float4 grab = ComputeGrabScreenPos(clip);
    return UNITY_SAMPLE_TEX2D_LOD(_MosaicGrabTexture, grab.xy / grab.w, 0).rgb;
}

half4 mosaic_fragment(FragmentInput input) : SV_Target
{
    UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

    float cell = input.grid.x;
    float radius = input.grid.y;

    float2 idx = floor((input.p - input.grid_origin) / cell + 0.5);
    float2 centre = idx * cell + input.grid_origin;
    // Membership by cell centre: the disc's edge is a staircase of whole cells.
    if (length(centre) > radius) discard;

    float3 centre_ws = input.placed_ws + input.right_ws * centre.x + input.up_ws * centre.y;

    if (anchor_depth_usable())
    {
        // Eye 0's depth for both tests, like the snap: a per-eye read lets a cell on a silhouette pass in
        // one eye and drop in the other, which is rivalry on exactly the edge this grid exists to hold.
        float anchor_depth, cell_depth;
        anchor_eye0_scene_depth(input.anchor_ws, anchor_depth);
        float scene = anchor_eye0_scene_depth(centre_ws, cell_depth);
        float in_front = anchor_depth - scene;
        // Something well in front of the anchor under this cell -- a wall, a hand -- hides the whole
        // cell, never a fragment of it.
        if (_Cell_Occlusion > 0.5 && in_front > _Snap_Window) discard;
        // Hug: nothing under this cell near the anchor's depth, so it is looking past the body.
        if (_Hug > 0.5 && -in_front > _Hug_Back) discard;
    }

    // Four taps inside the cell, averaged: one tap on a hard edge shimmers as the anchor moves.
    float q = cell * 0.25;
    half3 color = mosaic_grab(centre_ws + input.right_ws * q + input.up_ws * q)
                + mosaic_grab(centre_ws - input.right_ws * q + input.up_ws * q)
                + mosaic_grab(centre_ws + input.right_ws * q - input.up_ws * q)
                + mosaic_grab(centre_ws - input.right_ws * q - input.up_ws * q);
    color *= 0.25;

    return half4(color * _Tint.rgb, input.fade * _Tint.a);
}

#endif // MOSAIC_CORE_INCLUDED
