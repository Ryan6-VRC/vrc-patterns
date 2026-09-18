// Ryan6VRC/Overlay/Reticle -- an additive targeting reticle billboarded over a buried point: a gapped
// cross, a centre dot and one orbiting dash, drawn at a size that stays readable across a room, that
// scales in on acquire and fades out before it can fill the viewer's face.
//
// Ours outright. It shares the family's stereo-centre camera (stereo_camera.hlsl), and puts the placement
// question -- where to draw a marker for a point inside a body -- in anchor_placement.hlsl, which Mosaic
// shares. It reads no depth texture.
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
        // Fixed pull (anchor_placement.hlsl): the reticle is drawn this far toward the viewer from the
        // anchor, and occluded by whatever is in front of that position.
        _Pull("Pull toward viewer (m)", Range(0, 0.5)) = 0.15
        // Strength of the GHOST pass, which draws only where the MAIN pass is occluded (ZTest Greater),
        // dim and striped, so a reticle behind cloth or a wall stays findable. 0 disables it.
        _Ghost_Strength("Ghost strength", Range(0, 1)) = 0.35

        [Header(Near fade)]
        // Distance from the viewer's centre eye to the placed reticle. Also the floor on how close the pull
        // may bring it.
        _Fade_Near("Gone below (m)", Range(0, 1)) = 0.095
        _Fade_Far("Full above (m)", Range(0, 2)) = 0.19

        [Header(Far fade)]
        // Past this the angular floor would otherwise hold the reticle readable at any range; a marker
        // across a hall is noise, so it fades out between these two distances.
        _Far_Fade_Start("Fading from (m)", Range(1, 50)) = 8
        _Far_Fade_End("Gone beyond (m)", Range(1, 50)) = 10
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
            ZTest LEqual

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
