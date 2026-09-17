// Ryan6VRC/Overlay/Mosaic -- a censor mosaic over a buried point: a disc of whole cells on a billboard
// plane through the placed anchor, each cell coloured from the scene behind its centre through a grab
// pass. The edge is a staircase of cells, never a smooth clip, and the grid has real depth in a headset.
//
// Ours outright; placement is anchor_placement.hlsl's, shared with Reticle. MosaicProcedural.shader is
// the same shader without the grab pass, for a palette-coloured mosaic at no framebuffer cost.
//
// Host mesh: a Unity Quad. The quad is a vertex supply only; see Reticle.shader.
//
// THE GRAB PASS IS NAMED, so every Mosaic instance in view shares one framebuffer copy per camera per
// frame -- and therefore no mosaic sees another mosaic drawn the same frame. One copy is still one full
// per-eye framebuffer read; disable the renderer rather than leaving an empty mosaic drawing.

Shader "Ryan6VRC/Overlay/Mosaic"
{
    Properties
    {
        [Header(Look)]
        // Metres on the plane. Radius is the disc; cell is the mosaic block. Both have angular clamps.
        _Radius("Radius (m)", Range(0.02, 0.5)) = 0.15
        _Cell_Size("Cell size (m)", Range(0.005, 0.2)) = 0.03
        _Min_Cell_Degrees("Min cell angular size (deg)", Range(0, 5)) = 0.4
        _Max_Degrees("Max disc angular size (deg)", Range(1, 60)) = 30
        _Tint("Tint (alpha = opacity)", Color) = (1, 1, 1, 1)
        // On, cell edges sit on a world lattice and pop as the anchor moves; off, the grid rides the anchor.
        [ToggleUI] _Grid_World_Snap("Snap grid to world lattice", Float) = 0
        _Hide("Hide", Range(0, 1)) = 0

        [Header(Placement)]
        [Enum(Fixed pull, 0, Depth bias, 1, Surface snap, 2)] _Placement("Placement", Float) = 0
        _Pull("Pull toward viewer (m)", Range(0, 0.5)) = 0.15
        // LEqual clips cells fragment by fragment against what is in front; Always leaves occlusion to
        // the per-cell depth test below, which needs the depth texture.
        [Enum(UnityEngine.Rendering.CompareFunction)] _ZTest("ZTest", Float) = 4

        [Header(Depth)]
        [ToggleUI] _Use_Depth("Use depth texture", Float) = 0
        _Snap_Window("Window (m)", Range(0, 0.5)) = 0.3
        _Snap_Gap("Gap in front of surface (m)", Range(0, 0.05)) = 0.01
        _Snap_Tap_Radius("Snap tap radius (m)", Range(0, 0.1)) = 0.02
        // Drop a whole cell when the scene under its centre is in front of the anchor by more than the
        // window. This is what makes occlusion quantized instead of clipped.
        [ToggleUI] _Cell_Occlusion("Per-cell occlusion", Float) = 0
        // Drop a whole cell when the scene under its centre is behind the anchor by more than _Hug_Back:
        // the mosaic then follows the body's silhouette instead of covering the wall behind it.
        [ToggleUI] _Hug("Hug body", Float) = 0
        _Hug_Back("Hug depth behind anchor (m)", Range(0, 0.5)) = 0.15

        [Header(Near fade)]
        _Fade_Near("Gone below (m)", Range(0, 1)) = 0.25
        _Fade_Far("Full above (m)", Range(0, 2)) = 0.5
    }

    SubShader
    {
        Tags
        {
            "Queue" = "Overlay"
            "RenderType" = "Overlay"
            "VRCFallback" = "Hidden"
            "IgnoreProjector" = "True"
            "DisableBatching" = "True"
        }

        GrabPass { "_MosaicGrabTexture" }

        Pass
        {
            Name "MOSAIC"
            Blend SrcAlpha OneMinusSrcAlpha
            Cull Off
            ZWrite Off
            ZTest [_ZTest]

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)
            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma vertex mosaic_vertex
            #pragma fragment mosaic_fragment
            #include "mosaic_core.hlsl"
            ENDCG
        }
    }
}
