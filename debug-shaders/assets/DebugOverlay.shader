// Ryan6VRC/Overlay/DebugOverlay -- depth-derived surface probes: triangle edges, or reconstructed normals.
//
// Derived from lereldarion/unity-shaders (MIT, (c) 2025 Lereldarion), ancestors Shaders/Overlay_Wireframe.shader
// and Shaders/Overlay_Normals.shader; the two fragment bodies below are upstream's math. Upstream in turn
// credits Neitri (https://github.com/netri/Neitri-Unity-Shaders) for the wireframe idea and d4rkpl4y3r for
// the unity_CameraInvProjection patch that makes depth reconstruction work in BIRP VR -- that patch is what
// depth_reconstruct.hlsl carries. Ours are the crystal shell pass and the merge of the two probes into one
// shader. Full split in the entry README.
//
// The two ancestors were hand-copied into a private project as separate shaders carrying no attribution,
// and had drifted apart from upstream and from each other; restoring the credit is part of what this is for.
//
// Namespaced under Ryan6VRC/ rather than plain Overlay/ because upstream ships an Overlay/* family in a VPM
// package a consumer could install alongside this one, and a name collision resolves arbitrarily.

Shader "Ryan6VRC/Overlay/DebugOverlay"
{
    Properties
    {
        // Wireframe and Normal differ by eleven lines of fragment code over an identical prologue, so they
        // are one shader. NOT named _Overlay_Mode: upstream uses that name for a different axis (mesh /
        // fullscreen / billboard sphere / trail), which this shader also has, as _Overlay_Fullscreen.
        [KeywordEnum(Wireframe, Normal)] _Probe_Mode("Probe mode", Float) = 0

        [Header(Overlay)]
        [ToggleUI] _Overlay_Fullscreen("Force screenspace fullscreen", Float) = 0
        // Kept, not retired: the fullscreen path builds its quad from SV_VertexID, so which four vertices
        // form it is a property of whatever mesh the material was dropped on. The entry ships a sample mesh
        // but the shader is deliberately mesh-independent, so the workaround stays reachable.
        [ToggleUI] _Overlay_Screenspace_Vertex_Reorder("Fix broken fullscreen (mesh vertex order)", Float) = 0

        [Toggle(_SHELL_ON)] _Shell_Enabled("Shell enabled", Float) = 1
        [HDR] _Shell_Reflection_Color("Color / Mask", Color) = (1,1,1,1)
        [NoScaleOffset] _Shell_ReflectionCube("Reflection cubemap", Cube) = "" {}
        _Shell_Reflection_Strength("Reflectance", Range(0, 4)) = 1
        _Shell_Reflection_Smoothness("Smoothness", Range(0, 1)) = 0.7
        // The LOD the perceptual-roughness curve reaches at roughness 1, i.e. what both vendors hardcode as
        // UNITY_SPECCUBE_LOD_STEPS. Ranged to 6 rather than the ancestor's 10 because a Specular-convolved
        // chain is already near-flat there, so the default IS lilToon's remap and the slider only trims blur.
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
            "Queue" = "Overlay"
            "RenderType" = "Overlay"
            // Losing this makes a safety-shader client substitute Standard on a shader with no _MainTex --
            // a far louder failure than the null-cubemap one the owned cubemaps fixed.
            "VRCFallback" = "Hidden"
            "PreviewType" = "Plane"
            "IgnoreProjector" = "True"
            // RESTORED from upstream, which both hand copies had dropped. The reason here is NOT the object
            // matrix (this shader reads none): it is the fullscreen path's `vertex_id < 4`, which assumes
            // the mesh owns its draw call. Batched together with a neighbour, the quad is built from
            // whichever four vertices happen to land first and every later vertex is written NaN, so the
            // neighbour disappears too. In-game the governing batching settings are the VRChat client's
            // build, not ours.
            "DisableBatching" = "True"
        }

        Cull Off
        ZWrite On
        ZTest Less

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 1: the probe
        // ────────────────────────────────────────────────────────────────────────────────────────────
        Pass
        {
            Name "DEBUG_PROBE"

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)

            #pragma target 5.0
            #pragma vertex vertex_stage
            #pragma fragment fragment_stage
            #pragma multi_compile_instancing
            #pragma shader_feature_local _PROBE_MODE_WIREFRAME _PROBE_MODE_NORMAL

            #include "UnityCG.cginc"
            #include "depth_reconstruct.hlsl"

            struct VertexInput
            {
                float4 position_os : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct FragmentInput
            {
                float4 position : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            uniform float _Overlay_Fullscreen;
            uniform float _Overlay_Screenspace_Vertex_Reorder;

            // VRChat-set globals. Declared here and deliberately NOT in Properties: a material property of
            // the same name makes Unity serialize a value into every material, leaving no unset state for
            // SetGlobalFloat to fill, so the material's stale value would win forever.
            uniform float _VRChatMirrorMode;
            uniform float _VRChatCameraMode;

            static const float nan = asfloat(uint(-1));

            void vertex_stage(VertexInput input, uint vertex_id : SV_VertexID, out FragmentInput output)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                // Fullscreen is suppressed in mirrors and in the VRChat camera, so a photo or a mirror
                // shows the probe on its mesh rather than over the whole frame. Deliberate and unchanged
                // from the ancestors -- GammaCrystal in this same entry does NOT suppress itself in the
                // camera, because its effect is a scene grade rather than a frame takeover.
                if (_Overlay_Fullscreen == 1 && _VRChatMirrorMode == 0 && _VRChatCameraMode == 0)
                {
                    if (vertex_id < 4)
                    {
                        float2 ndc = vertex_id & uint2(2, 1) ? 1 : -1;
                        if (_Overlay_Screenspace_Vertex_Reorder && (vertex_id & 1))
                        {
                            ndc.x *= -1;
                        }
                        output.position = float4(ndc, UNITY_NEAR_CLIP_VALUE, 1);
                    }
                    else
                    {
                        output.position = nan.xxxx;
                    }
                }
                else
                {
                    output.position = UnityObjectToClipPos(input.position_os);
                }
            }

            fixed4 fragment_stage(FragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                DepthReconstruction dr = DepthReconstruction::init(input.position);
                float3 vs_0_0 = dr.position_vs();
                float3 vs_m_0 = dr.position_vs(float2(-1, 0));
                float3 vs_0_p = dr.position_vs(float2(0, 1));

            #if defined(_PROBE_MODE_NORMAL)
                // Reconstructed world normal as a normal-map-style colour.
                //
                // GammaToLinearSpace HERE WAS AN INHERITED BUG: upstream writes LinearToGammaSpace, and the
                // hand copy this entry is built from had the conversion inverted, darkening every normal
                // colour non-linearly. The encoding is a 0..1 remap meant to be READ as a colour, so it is
                // the gamma direction that makes the displayed value match the normal it encodes.
                float3 normal_dir_vs = cross(vs_0_p - vs_0_0, vs_m_0 - vs_0_0);
                float3 normal_ws = normalize(mul((float3x3) unity_MatrixInvV, normal_dir_vs));
                return fixed4(LinearToGammaSpace(normal_ws * 0.5 + 0.5), 1);
            #else
                // Triangle edges: three normals from the origin pixel over three quadrants, and the places
                // where they disagree are the edges. Needs no world space at all.
                float3 vs_p_0 = dr.position_vs(float2(1, 0));
                float3 vs_0_m = dr.position_vs(float2(0, -1));

                float3 normal_vs_m_p = normalize(cross(vs_0_p - vs_0_0, vs_m_0 - vs_0_0));
                float3 normal_vs_p_m = normalize(cross(vs_0_m - vs_0_0, vs_p_0 - vs_0_0));
                float3 normal_vs_p_p = normalize(cross(vs_p_0 - vs_0_0, vs_0_p - vs_0_0));

                float3 o = 1;
                float sum_normal_differences = dot(o, abs(normal_vs_p_p - normal_vs_m_p))
                                             + dot(o, abs(normal_vs_p_m - normal_vs_m_p));
                return float4(saturate(sum_normal_differences).xxx, 1);
            #endif
            }
            ENDCG
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 2: CRYSTAL_SHELL
        //
        // A keyword cannot remove a Pass, so with _SHELL_ON off this pass still rasterizes and outputs
        // nothing -- harmless under Blend One One. The shader_feature gates VARIANT COMPILATION, and the
        // body is #if-guarded so the keyword gates the code too rather than only the variant.
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
            #pragma vertex shell_vertex_stage
            #pragma fragment shell_fragment_stage
            #pragma multi_compile_instancing
            #pragma shader_feature_local _SHELL_ON

            #include "crystal_shell.hlsl"

            uniform float _Overlay_Fullscreen;
            uniform float _VRChatMirrorMode;
            uniform float _VRChatCameraMode;

            half4 shell_fragment_stage(ShellFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

            #if !defined(_SHELL_ON)
                return half4(0, 0, 0, 0);
            #else
                // Same condition the probe pass enters fullscreen on: with the mesh abandoned for a
                // full-frame quad there is no shell surface to draw, so drawing one would paint a rim
                // around the screen edge.
                if (_Overlay_Fullscreen == 1 && _VRChatMirrorMode == 0 && _VRChatCameraMode == 0)
                {
                    return half4(0, 0, 0, 0);
                }

                return half4(shell_rgb(input.normal_ws, input.position_ws), 0);
            #endif
            }
            ENDCG
        }
    }

    CustomEditor "Ryan6Vrc.AvatarTools.Editor.DebugOverlayShaderGUI"
}
