// Ryan6VRC/Overlay/Mosaic -- a censor mosaic over a buried point: a disc of whole cells on a billboard
// plane through the anchor, each cell coloured from the scene behind its centre through a grab pass. The
// disc's edge is a staircase of cells, never a smooth clip, and the grid has real depth in a headset.
//
// Ours outright; placement is anchor_placement.hlsl's, shared with Reticle.
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
        _Radius("Radius (m)", Range(0.02, 0.5)) = 0.1125
        _Cell_Size("Cell size (m)", Range(0.005, 0.2)) = 0.022
        _Min_Cell_Degrees("Min cell angular size (deg)", Range(0, 5)) = 0.4
        _Max_Degrees("Max disc angular size (deg)", Range(1, 60)) = 30
        _Tint("Tint (alpha = opacity)", Color) = (1, 1, 1, 1)
        _Hide("Hide", Range(0, 1)) = 0

        [Header(Placement)]
        // Depth bias (anchor_placement.hlsl): the disc stays at the anchor and only its depth test is
        // taken this far toward the viewer, so cloth nearer than that does not hide it while a hand or a
        // wall in front clips it fragment by fragment.
        _Pull("Depth-test pull toward viewer (m)", Range(0, 0.5)) = 0.15

        [Header(Near fade)]
        _Fade_Near("Gone below (m)", Range(0, 1)) = 0.095
        _Fade_Far("Full above (m)", Range(0, 2)) = 0.19
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
            ZTest LEqual

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
