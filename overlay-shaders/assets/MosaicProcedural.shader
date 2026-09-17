// Ryan6VRC/Overlay/MosaicProcedural -- Mosaic.shader without its grab pass: the same disc of whole cells
// on the same placed plane, each cell coloured by a hash over a two-colour palette that re-rolls at
// _Proc_Rate. Costs nothing per frame beyond its own quad, reads as "censored" rather than as a blur of
// what is behind it, and is the fallback where a grab pass is not worth paying for.
//
// Ours outright; see Mosaic.shader and anchor_placement.hlsl. Properties are Mosaic's minus nothing --
// a material converts between the two shaders without losing a value.

Shader "Ryan6VRC/Overlay/MosaicProcedural"
{
    Properties
    {
        [Header(Look)]
        _Radius("Radius (m)", Range(0.02, 0.5)) = 0.15
        _Cell_Size("Cell size (m)", Range(0.005, 0.2)) = 0.03
        _Min_Cell_Degrees("Min cell angular size (deg)", Range(0, 5)) = 0.4
        _Max_Degrees("Max disc angular size (deg)", Range(1, 60)) = 30
        _Tint("Tint (alpha = opacity)", Color) = (1, 1, 1, 1)
        [ToggleUI] _Grid_World_Snap("Snap grid to world lattice", Float) = 0
        _Hide("Hide", Range(0, 1)) = 0

        [Header(Palette)]
        _Proc_Color_A("Color A", Color) = (0.95, 0.80, 0.72, 1)
        _Proc_Color_B("Color B", Color) = (0.75, 0.55, 0.50, 1)
        // Re-rolls per second. 0 freezes the pattern.
        _Proc_Rate("Re-roll rate (Hz)", Range(0, 30)) = 4

        [Header(Placement)]
        [Enum(Fixed pull, 0, Depth bias, 1, Surface snap, 2)] _Placement("Placement", Float) = 0
        _Pull("Pull toward viewer (m)", Range(0, 0.5)) = 0.15
        [Enum(UnityEngine.Rendering.CompareFunction)] _ZTest("ZTest", Float) = 4

        [Header(Depth)]
        [ToggleUI] _Use_Depth("Use depth texture", Float) = 0
        _Snap_Window("Window (m)", Range(0, 0.5)) = 0.3
        _Snap_Gap("Gap in front of surface (m)", Range(0, 0.05)) = 0.01
        _Snap_Tap_Radius("Snap tap radius (m)", Range(0, 0.1)) = 0.02
        [ToggleUI] _Cell_Occlusion("Per-cell occlusion", Float) = 0
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
            #define MOSAIC_PROCEDURAL
            #include "mosaic_core.hlsl"
            ENDCG
        }
    }
}
