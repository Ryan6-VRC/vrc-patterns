// Ryan6VRC/Overlay/TransClip -- a depth wall with a front-face shell: the family's crystal sphere, which also
// writes depth early so every transparent material behind its surface is skipped. Put your head inside it
// and the view renders geometry only, with no shell in the way.
//
// TransClip is short for transparent-clip, and keeps the name of the lilToon alpha-clip material it
// replaces recognizable while saying what the effect is rather than how that material reached it -- an alpha
// near zero under a cutout queue, which is the mechanism this shader stops needing.
//
// Ours outright. Unlike its three siblings this member has no lereldarion/unity-shaders ancestor: upstream's
// two ColorMask 0 passes (Overlay_Debug_Lighting.shader) set and clear a stencil and share nothing with a
// depth prepass. What it inherits from the family is the shared includes -- crystal_shell.hlsl's shell and
// rim, stereo_camera.hlsl's stereo-correct camera positions -- both of which are ours as well. The family's
// ancestry is real and travels with those files; it does not reach this shader's own two passes. Full split
// in the entry README.
//
// Namespaced under Ryan6VRC/ rather than plain Overlay/ for the family's reason: upstream ships an Overlay/*
// family in a VPM package a consumer could install alongside this one, and a name collision resolves
// arbitrarily.

Shader "Ryan6VRC/Overlay/TransClip"
{
    Properties
    {
        // No [Header] anywhere in this block: the material inspector draws its own sections, and Unity
        // renders a property's header inside whichever section drew it, so a header would title the fold
        // twice.

        // The family's shell block, name for name and default for default: this shell IS the debug crystal
        // shell, so a value that differs from a sibling's is drift, not tuning.
        [Toggle(_SHELL_ON)] _Shell_Enabled("Shell enabled", Float) = 1
        [HDR] _Shell_Reflection_Color("Color / Mask", Color) = (1,1,1,1)
        [NoScaleOffset] _Shell_ReflectionCube("Reflection cubemap", Cube) = "" {}
        _Shell_Reflection_Strength("Reflectance", Range(0, 4)) = 1
        _Shell_Reflection_Smoothness("Smoothness", Range(0, 1)) = 0.7
        // See DebugOverlay: ranged to 6 rather than the ancestor's 10, because a Specular-convolved chain is
        // already near-flat there and the slider's top third was dead travel.
        _Shell_Reflection_BlurMaxMip("Blur max mip (LOD steps)", Range(0, 6)) = 6

        [HDR] _Shell_Rim_Color("Color / Alpha", Color) = (1,1,1,0.05)
        _Shell_Rim_Strength("Strength", Range(0, 4)) = 1
        _Shell_Rim_Border("Border", Range(0, 1)) = 0.6
        _Shell_Rim_Blur("Blur", Range(0.001, 1)) = 0.7
        _Shell_Rim_FresnelPower("Fresnel Power", Range(0.05, 8)) = 4
        _Shell_Rim_VRParallaxStrength("VR Parallax Strength", Range(0, 1)) = 1
    }

    SubShader
    {
        Tags
        {
            // THE ONE KNOB THAT DECIDES WHAT GETS CLIPPED, and the only queue in the family that is not
            // Overlay. Geometry+440 = 2440, which sorts before AlphaTest (2450) and before Transparent
            // (3000), so the wall's depth is already in the buffer when either kind draws and both are
            // clipped -- the default. Move the MATERIAL to 2451..2999 to clip
            // transparents only and let cutout materials through; that is a per-material override
            // (m_CustomRenderQueue), reached from the inspector's Rendering > Render Queue field, never an
            // edit here. The wall only ever removes what draws AFTER it: a material queued at or before the
            // wall's own queue has already written its colour and cannot be erased, which is why opaque
            // geometry (Geometry, 2000) is never affected at any value here, and why lowering the queue
            // buys nothing -- it only narrows the set of later queues the wall reaches.
            "Queue" = "Geometry+440"
            // Descriptive only -- nothing here is replaced by RenderType and this shader has no ShadowCaster
            // pass, so it contributes nothing to _CameraDepthTexture either. The queue above is the
            // load-bearing tag.
            "RenderType" = "Transparent"
            // Losing this makes a safety-shader client substitute Standard, which would draw an opaque
            // sphere where the whole point is that nothing is drawn.
            "VRCFallback" = "Hidden"
            "PreviewType" = "Sphere"
            "IgnoreProjector" = "True"
            // No "DisableBatching" here, deliberately, and it is the only member of the family without it:
            // neither pass reads the object matrix (GammaCrystal's reason) and neither builds geometry from
            // SV_VertexID (DebugOverlay's reason). Batching two of these together still draws the wall pass
            // for both before the shell pass for both, which is the order the effect needs.
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 1: DEPTH_WALL
        //
        // The whole effect. Cull Off so the nearest surface wins whichever way it faces, ZWrite On to put
        // that depth in the buffer, ColorMask 0 so not one pixel of colour is written -- no rim, no
        // reflection, no tint on any face. That last part is why this is a separate pass rather than a
        // ZWrite On shell: a single two-sided pass writing colour double-blends the back face wherever it
        // rasterises before the front face, giving a per-triangle patchy tint from outside.
        //
        // No _VRChatMirrorMode check, and that is a decision rather than an omission. GammaCrystal
        // suppresses its grading in mirrors because a mirror reflects a scene the bubble has ALREADY graded,
        // so the reflection would be graded twice; nothing here compounds -- a mirror camera renders the
        // scene into its own depth buffer, and the wall either clips the transparents in that render or it
        // does not. Bailing would make the reflection disagree with the direct view about the same volume.
        // The consequence to expect: from a mirror, transparent materials inside the sphere are clipped
        // there too, including the wearer's own.
        // ────────────────────────────────────────────────────────────────────────────────────────────
        Pass
        {
            Name "DEPTH_WALL"

            Cull Off
            ZWrite On
            ZTest LEqual
            ColorMask 0

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)

            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma vertex wall_vertex_stage
            #pragma fragment wall_fragment_stage

            #include "UnityCG.cginc"

            struct WallVertexInput
            {
                float4 position_os : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct WallFragmentInput
            {
                float4 position : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            void wall_vertex_stage(WallVertexInput input, out WallFragmentInput output)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                output.position = UnityObjectToClipPos(input.position_os);
            }

            // Still required under ColorMask 0: the mask discards the write, it does not remove the stage.
            // The stereo setup stays for the same reason -- an unset eye index under single-pass instanced
            // is undefined, not merely unused.
            half4 wall_fragment_stage(WallFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                return half4(0, 0, 0, 0);
            }
            ENDCG
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 2: CRYSTAL_SHELL
        //
        // The family's shell, verbatim: Blend One One, half4(shell_rgb, 0), the same pass DebugOverlay and
        // DebugDisplay draw, so this sphere looks exactly like its siblings and is found the same way. Cull
        // Back with ZWrite Off and the depth wall already holding the nearest surface, so exactly one shell
        // layer survives the depth test per pixel. From inside the sphere no front face points at the
        // camera, so this pass draws nothing at all -- which is the inside-view behaviour, reached by the
        // culling rule rather than by any switch. Not an alpha blend at a low alpha: that reads as no shell
        // at all, and the shell is the family's or it is nothing.
        // ────────────────────────────────────────────────────────────────────────────────────────────
        Pass
        {
            Name "CRYSTAL_SHELL"

            Blend One One
            Cull Back
            ZWrite Off
            ZTest LEqual

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)

            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma shader_feature_local _SHELL_ON
            #pragma vertex shell_vertex_stage
            #pragma fragment shell_fragment_stage

            #include "crystal_shell.hlsl"

            half4 shell_fragment_stage(ShellFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

            #if !defined(_SHELL_ON)
                // Black under Blend One One leaves the framebuffer untouched, so the shell-off variant costs
                // a rasterised fragment and changes nothing. The depth wall is unaffected: it is its own
                // pass and carries no keyword.
                return half4(0, 0, 0, 0);
            #else
                return half4(shell_rgb(input.normal_ws, input.position_ws), 0);
            #endif
            }
            ENDCG
        }
    }

    CustomEditor "Ryan6Vrc.Patterns.DebugShaders.Editor.TransClipShaderGUI"
}
