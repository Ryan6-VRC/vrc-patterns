// Ryan6VRC/Overlay/Reticle -- an additive targeting reticle billboarded over a buried point: a gapped
// cross, a centre dot and one orbiting dash, drawn at a size that stays readable across a room, that
// scales in on acquire and fades out before it can fill the viewer's face.
//
// Ours outright. It shares the family's stereo-centre camera (stereo_camera.hlsl) and d4rkpl4y3r's depth
// reconstruction (depth_reconstruct.hlsl), and puts the placement question -- where to draw a marker for
// a point inside a body -- in anchor_placement.hlsl, which Mosaic shares.
//
// Host mesh: a Unity Quad (uv 0..1 across it). The mesh is only a vertex supply; the billboard is built
// from the object's origin and the viewer, so nothing about the quad's own size or rotation matters.
//
// Namespaced under Ryan6VRC/ rather than plain Overlay/ for the same reason as the rest of the family.

Shader "Ryan6VRC/Overlay/Reticle"
{
    Properties
    {
        [Header(Look)]
        [HDR] _Color("Color (alpha = strength)", Color) = (0.3, 1.0, 0.6, 0.8)
        // Metres at the placed distance, before the angular clamp below.
        _Size("Size (m)", Float) = 0.09
        // Floor and ceiling on the reticle's angular size: the floor keeps it readable across a room, the
        // ceiling keeps a near one from filling the view. Degrees of the viewer's field, edge to edge.
        _Min_Degrees("Min angular size (deg)", Range(0, 20)) = 3
        _Max_Degrees("Max angular size (deg)", Range(1, 60)) = 25
        // In plane units (the reticle spans -1..1), floored at one pixel by the fragment.
        _Line_Width("Line width", Range(0.005, 0.1)) = 0.025
        _Spin("Dash spin (rad/s)", Range(-6, 6)) = 1.2
        _Pulse("Pulse (fraction)", Range(0, 0.5)) = 0.1

        [Header(Acquire)]
        // 0..1, driven by an animator clip on latch: scales in from _Acquire_Scale and spins into place.
        _Acquire("Acquire", Range(0, 1)) = 1
        _Acquire_Scale("Acquire start scale", Range(1, 5)) = 2.5
        // An animator's per-frame off switch. Animate this, not the renderer's enabled flag, when the
        // renderer must keep its bounds registered.
        _Hide("Hide", Range(0, 1)) = 0

        [Header(Placement)]
        // See anchor_placement.hlsl for the three.
        [Enum(Fixed pull, 0, Depth bias, 1, Surface snap, 2)] _Placement("Placement", Float) = 0
        _Pull("Pull toward viewer (m)", Range(0, 0.5)) = 0.15
        // The MAIN pass's depth test. LEqual: the reticle is occluded by whatever is in front of its
        // placed position. Always: never occluded by the depth buffer, leaving occlusion to _Depth_Fade.
        [Enum(UnityEngine.Rendering.CompareFunction)] _ZTest("Main pass ZTest", Float) = 4
        // Strength of the GHOST pass, which draws only where the MAIN pass is occluded (ZTest Greater),
        // dim and striped. 0 disables it.
        _Ghost_Strength("Ghost strength", Range(0, 1)) = 0

        [Header(Depth)]
        // The depth-reading features below are only correct when a depth texture exists (a DepthLight is
        // in the prefab, or the world casts directional shadows). Off, every one of them is inert.
        [ToggleUI] _Use_Depth("Use depth texture", Float) = 0
        // Buried deeper than this behind the nearest surface counts as occluded, not as clothing.
        _Snap_Window("Window (m)", Range(0, 0.5)) = 0.3
        _Snap_Gap("Gap in front of surface (m)", Range(0, 0.05)) = 0.01
        _Snap_Tap_Radius("Snap tap radius (m)", Range(0, 0.1)) = 0.02
        // Per-fragment: fade where the scene is in front of the ANCHOR by more than the window.
        [ToggleUI] _Depth_Fade("Depth fade", Float) = 0

        [Header(Near fade)]
        // Distance from the viewer's centre eye to the placed reticle. Also the floor on how close any
        // placement may pull it.
        _Fade_Near("Gone below (m)", Range(0, 1)) = 0.25
        _Fade_Far("Full above (m)", Range(0, 2)) = 0.5
    }

    SubShader
    {
        Tags
        {
            // After Mosaic (plain Overlay): a reticle on the same anchor draws over the censor rather than
            // being grabbed into it.
            "Queue" = "Overlay+10"
            "RenderType" = "Overlay"
            "VRCFallback" = "Hidden"
            "IgnoreProjector" = "True"
            // The object matrix's translation column is the anchor.
            "DisableBatching" = "True"
        }

        Blend One One
        Cull Off
        ZWrite Off

        Pass
        {
            Name "MAIN"
            ZTest [_ZTest]

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)
            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma vertex reticle_vertex
            #pragma fragment reticle_fragment
            #include "reticle_core.hlsl"
            ENDCG
        }

        Pass
        {
            Name "GHOST"
            ZTest Greater

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)
            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma vertex reticle_vertex
            #pragma fragment reticle_fragment
            #define RETICLE_GHOST_PASS
            #include "reticle_core.hlsl"
            ENDCG
        }
    }
}
