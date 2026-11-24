// Ryan6VRC/Overlay/AOBlock -- removes the world's ambient occlusion inside a sphere of influence, behind the
// family's crystal shell. The paste half of a pair: AOBlockCopy saves the frame before the AO composite, and
// this shader, queued just after it, blends that copy back over every surface inside the sphere. It restores
// what was drawn, so it is exact for any AO implementation and does nothing in a world without one.
//
// Needs an AOBlockCopy material drawn by the same camera in the same frame (see that shader's header).

Shader "Ryan6VRC/Overlay/AOBlock"
{
    Properties
    {
        // GammaCrystal's area-of-effect block, name for name: metres at unit scale, multiplied by the
        // object's mean axis scale unless scale-relative is off.
        [ToggleUI] _AoE_Scale_Relative("Scale with object", Float) = 1
        _AoE_MinDistance("Full strength (m)", Float) = 1
        _AoE_MaxDistance("Zero strength (m)", Float) = 2

        // The family's shell block, name for name and default for default.
        [Toggle(_SHELL_ON)] _Shell_Enabled("Shell enabled", Float) = 1
        [HDR] _Shell_Reflection_Color("Color / Mask", Color) = (1,1,1,1)
        [NoScaleOffset] _Shell_ReflectionCube("Reflection cubemap", Cube) = "" {}
        _Shell_Reflection_Strength("Reflectance", Range(0, 4)) = 1
        _Shell_Reflection_Smoothness("Smoothness", Range(0, 1)) = 0.7
        _Shell_Reflection_BlurMaxMip("Blur max mip (LOD steps)", Range(0, 6)) = 6

        [HDR] _Shell_Rim_Color("Color / Alpha", Color) = (1,1,1,0.05)
        _Shell_Rim_Strength("Strength", Range(0, 4)) = 1
        _Shell_Rim_Border("Border", Range(0, 1)) = 0.6
        _Shell_Rim_Blur("Blur", Range(0.001, 1)) = 0.7
        _Shell_Rim_FresnelPower("Fresnel Power", Range(0.05, 8)) = 4
        _Shell_Rim_VRParallaxStrength("VR Parallax Strength", Range(0, 1)) = 1

        // Shell only. The paste never draws in a mirror, whatever this is.
        [ToggleUI] _HideInMirror("Hide in mirror", Float) = 0
    }

    SubShader
    {
        Tags
        {
            // LOAD-BEARING. 2501 is the first queue after the AO composite, so the paste lands before any
            // transparent draws and every transparent then blends over the restored surface as it would
            // have over the occluded one.
            "Queue" = "Geometry+501"
            "RenderType" = "Transparent"
            "VRCFallback" = "Hidden"
            "PreviewType" = "Sphere"
            "IgnoreProjector" = "True"
            // GammaCrystal's reason: the paste reads the object matrix for the sphere centre and scale.
            "DisableBatching" = "True"
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 1: AO_RESTORE
        //
        // The proxy sphere is flattened onto the far plane and drawn ZTest Greater, so a fragment survives
        // only where the depth buffer holds something nearer than the far plane: a pixel some surface was
        // drawn to. Sky pixels fail, which matters because the copy was taken before the skybox drew and
        // holds no sky. That guard reads the real depth buffer, so it holds with no depth texture at all.
        //
        // Which surviving pixels are INSIDE the sphere is read from _CameraDepthTexture. A world that runs
        // AO has one, since the AO is computed from it; in a world without, the membership is noise and the
        // paste writes back colours nothing has changed.
        // ────────────────────────────────────────────────────────────────────────────────────────────
        Pass
        {
            Name "AO_RESTORE"

            Blend SrcAlpha OneMinusSrcAlpha
            Cull Front
            ZWrite Off
            ZTest Greater
            ColorMask RGB

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)

            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma vertex restore_vertex_stage
            #pragma fragment restore_fragment_stage

            #include "UnityCG.cginc"
            #include "depth_reconstruct.hlsl"

            uniform float _AoE_Scale_Relative;
            uniform float _AoE_MinDistance;
            uniform float _AoE_MaxDistance;
            uniform float _VRChatMirrorMode;

            // TEX2D, not the SCREENSPACE pair: GammaCrystal's declaration, for GammaCrystal's reason.
            UNITY_DECLARE_TEX2D(_AOBlockPreAOTexture);

            struct RestoreVertexInput
            {
                float4 position_os : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct RestoreFragmentInput
            {
                float4 position : SV_POSITION;
                float4 grab_screen_pos : GRAB_SCREEN_POS;
                nointerpolation float3 sphere_center_ws : SPHERE_CENTER;
                nointerpolation float aoe_scale : AOE_SCALE;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            float aoe_scale_factor()
            {
                if (_AoE_Scale_Relative == 0) return 1.0;
                float3 axes = float3(length(unity_ObjectToWorld._m00_m10_m20),
                                     length(unity_ObjectToWorld._m01_m11_m21),
                                     length(unity_ObjectToWorld._m02_m12_m22));
                return (axes.x + axes.y + axes.z) / 3.0;
            }

            void restore_vertex_stage(RestoreVertexInput input, out RestoreFragmentInput output)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                output.sphere_center_ws = float3(
                    unity_ObjectToWorld._m03,
                    unity_ObjectToWorld._m13,
                    unity_ObjectToWorld._m23
                );
                output.aoe_scale = aoe_scale_factor();

                // A mirror render has no AO composite to undo and no depth texture to place pixels with.
                if (_VRChatMirrorMode != 0)
                {
                    output.position = float4(0, 0, 0, 0);
                    output.grab_screen_pos = float4(0, 0, 0, 0);
                    return;
                }

                // GammaCrystal's proxy: every vertex pushed out to the zero-strength radius, so any closed
                // mesh hosts this.
                float3 vertex_ws = mul(unity_ObjectToWorld, input.position_os).xyz;
                float3 dir_ws = vertex_ws - output.sphere_center_ws;
                float dist_ws = length(dir_ws);
                if (dist_ws > 0.001)
                {
                    vertex_ws = output.sphere_center_ws
                              + (dir_ws / dist_ws) * (_AoE_MaxDistance * output.aoe_scale);
                }

                float4 position_cs = mul(UNITY_MATRIX_VP, float4(vertex_ws, 1.0));
                output.grab_screen_pos = ComputeGrabScreenPos(position_cs);

                // Onto the far plane. x, y and w are untouched, so the screen footprint and the clip
                // against the camera plane are the proxy's own.
            #if defined(UNITY_REVERSED_Z)
                position_cs.z = 0;
            #else
                position_cs.z = position_cs.w;
            #endif
                output.position = position_cs;
            }

            half4 restore_fragment_stage(RestoreFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                DepthReconstruction dr = DepthReconstruction::init(input.position);
                float4 vs_result = dr.position_vs_checked();
                clip(vs_result.w - 0.5);

                float3 pixel_ws = mul(unity_MatrixInvV, float4(vs_result.xyz, 1)).xyz;

                float aoe_min = _AoE_MinDistance * input.aoe_scale;
                float aoe_max = max(_AoE_MaxDistance * input.aoe_scale, aoe_min + 0.001);
                float strength = 1.0 - smoothstep(aoe_min, aoe_max, distance(pixel_ws, input.sphere_center_ws));
                clip(strength - 1.0 / 255.0);

                half4 pre_ao = UNITY_SAMPLE_TEX2D_LOD(
                    _AOBlockPreAOTexture,
                    input.grab_screen_pos.xy / input.grab_screen_pos.w,
                    0
                );

                // Finite and non-negative, as GammaCrystal clamps its grab.
                return half4(clamp(pre_ao.rgb, 0.0, 64000.0), strength);
            }
            ENDCG
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 2: CRYSTAL_SHELL
        //
        // The family's shell, verbatim. It draws at 2501 with no depth write, so a transparent behind the
        // sphere blends over the shell rather than under it.
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

            half4 shell_fragment_stage(ShellFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

            #if !defined(_SHELL_ON)
                return half4(0, 0, 0, 0);
            #else
                return half4(shell_rgb(input.normal_ws, input.position_ws), 0);
            #endif
            }
            ENDCG
        }
    }
}
