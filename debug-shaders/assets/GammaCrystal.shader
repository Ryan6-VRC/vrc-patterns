// Ryan6VRC/Overlay/GammaCrystal -- a localized grading bubble: gamma, optional linear exposure, optional
// scotopic desaturation, applied to the scene inside a sphere of influence and visible from outside as a
// crystal shell.
//
// Derived from lereldarion/unity-shaders (MIT, (c) 2025 Lereldarion), ancestor
// Shaders/Overlay_Gamma_Adjust.shader (declared there as "Lereldarion/Overlay/Gamma Adjust"; the hand copy
// this is built from cited it as "GammaAdjust", which was never upstream's name). Upstream's is the grab-pass
// gamma idea and the depth reconstruction it shares with the rest of that family -- which in turn carries
// d4rkpl4y3r's unity_CameraInvProjection patch, see depth_reconstruct.hlsl. Ours are the volumetric
// sphere-of-influence model, the exposure and scotopic stages, the core emphasis, the crystal shell, and the
// scale handling below. Full split in the entry README.
//
// Namespaced under Ryan6VRC/ rather than plain Overlay/ because upstream ships an Overlay/* family in a VPM
// package a consumer could install alongside this one, and a name collision resolves arbitrarily.

Shader "Ryan6VRC/Overlay/GammaCrystal"
{
    Properties
    {
        [Header(Gamma)]
        _Gamma_Adjust_Value("Gamma adjust value", Range(-5, 5)) = 0
        [ToggleUI] _Transmit_Emission("Keep pixel values above 1 (emission / bloom)", Float) = 1

        [Header(Exposure)]
        [Toggle(_EXPOSURE_ENABLED)] _Exposure_Enable("Enable linear exposure", Float) = 0
        _Exposure_Value("Exposure value (EV stops)", Range(-5, 5)) = 0

        [Header(Scotopic Desaturation)]
        [Toggle(_SCOTOPIC_ENABLED)] _Scotopic_Enable("Enable scotopic desaturation", Float) = 0
        _Scotopic_Strength("Desaturation strength", Range(0, 1)) = 1
        [HDR] _Scotopic_Tint("Scotopic tint color", Color) = (0.7, 0.8, 1.0, 1)

        [Header(Area of Effect)]
        // The three distances below are metres AT UNIT SCALE, multiplied by the object's mean axis scale.
        // With this off they are absolute metres -- the ancestor's behaviour, and a trap: the shell pass
        // draws the mesh at its real size while the effect stays fixed, so scaling the object (or animating
        // the scale, which is the obvious way to grow a bubble) slides the visible sphere out of the region
        // it is supposed to bound, and the core silhouette stops tracing the mesh it is matched to.
        // Deliberately read off the OBJECT MATRIX, never a mesh radius: every shader in this entry works on
        // whatever mesh it is dropped on.
        [ToggleUI] _AoE_Scale_Relative("Scale the distances below with the object", Float) = 1
        _AoE_MinDistance("Full strength distance (m at unit scale)", Float) = 1
        _AoE_MaxDistance("Zero strength distance (m at unit scale)", Float) = 2
        _Core_Radius("Core radius (m at unit scale, match mesh)", Float) = 0.15
        _Core_Intensity("Core extra intensity", Range(0, 0.5)) = 0.15

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

        [Header(Shell Scene Grading)]
        // 0 = shell fully obeys scene grading (disappears in dark), 1 = shell ignores it (too bright)
        _Shell_Grading_Resist("Grading resistance", Range(0, 1)) = 0.5
    }

    SubShader
    {
        Tags
        {
            "Queue" = "Overlay"
            "RenderType" = "Overlay"
            "VRCFallback" = "Hidden"
            "PreviewType" = "Plane"
            "IgnoreProjector" = "True"
            // LOAD-BEARING HERE, and for the classic reason rather than DebugOverlay's: the effect pass
            // reads the object matrix's translation column as the sphere centre and its basis lengths as
            // the scale. Dynamic batching bakes vertices to world space and leaves unity_ObjectToWorld
            // identity, so a batched bubble would centre on the world origin at unit scale.
            "DisableBatching" = "True"
        }

        GrabPass { "_GammaAdjustGrabTexture" }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 1: the grading, over a localized area of effect
        // ────────────────────────────────────────────────────────────────────────────────────────────
        Pass
        {
            Name "GAMMA_EFFECT"

            Cull Front
            ZWrite Off
            ZTest Always

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)

            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma shader_feature_local _EXPOSURE_ENABLED
            #pragma shader_feature_local _SCOTOPIC_ENABLED
            #pragma vertex vertex_stage
            #pragma fragment fragment_stage

            #include "UnityCG.cginc"
            #include "depth_reconstruct.hlsl"
            // For the stereo-correct camera helper. The shell's own uniforms come with it and go unused in
            // this pass, which costs nothing -- an unreferenced uniform is not bound.
            #include "crystal_shell.hlsl"

            uniform float _Gamma_Adjust_Value;
            uniform float _Transmit_Emission;
            uniform float _AoE_Scale_Relative;
            uniform float _AoE_MinDistance;
            uniform float _AoE_MaxDistance;
            uniform float _Core_Radius;
            uniform float _Core_Intensity;

            #ifdef _EXPOSURE_ENABLED
                uniform float _Exposure_Value;
            #endif

            #ifdef _SCOTOPIC_ENABLED
                uniform float _Scotopic_Strength;
                uniform half4 _Scotopic_Tint;
            #endif

            uniform float _VRChatMirrorMode;

            UNITY_DECLARE_TEX2D(_GammaAdjustGrabTexture);

            struct VertexInput
            {
                float4 position_os : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct FragmentInput
            {
                float4 position : SV_POSITION;
                float4 grab_screen_pos : GRAB_SCREEN_POS;
                nointerpolation float3 sphere_center_ws : SPHERE_CENTER;
                // Carried rather than recomputed so the vertex stage's own re-projection radius and the
                // fragment's distance thresholds cannot disagree.
                nointerpolation float aoe_scale : AOE_SCALE;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            /// Mean of the object's three axis scales, or 1 with scale-relative off. A SINGLE SCALAR, never
            /// per-axis: the area of effect is spherical by construction, so a per-axis factor would ask for
            /// an ellipsoid the rest of the maths cannot express.
            float aoe_scale_factor()
            {
                if (_AoE_Scale_Relative == 0) return 1.0;
                float3 axes = float3(length(unity_ObjectToWorld._m00_m10_m20),
                                     length(unity_ObjectToWorld._m01_m11_m21),
                                     length(unity_ObjectToWorld._m02_m12_m22));
                return (axes.x + axes.y + axes.z) / 3.0;
            }

            void vertex_stage(VertexInput input, out FragmentInput output)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                // Unchanged from the ancestor: the bubble does not render in mirrors at all. DELIBERATELY
                // asymmetric with DebugOverlay, which only suppresses its FULLSCREEN takeover there.
                if (_VRChatMirrorMode != 0)
                {
                    output.sphere_center_ws = float3(0, 0, 0);
                    output.position = float4(0, 0, 0, 0);
                    output.grab_screen_pos = float4(0, 0, 0, 0);
                    output.aoe_scale = 1;
                    return;
                }

                // Sphere center = translation column of the object-to-world matrix.
                output.sphere_center_ws = float3(
                    unity_ObjectToWorld._m03,
                    unity_ObjectToWorld._m13,
                    unity_ObjectToWorld._m23
                );
                output.aoe_scale = aoe_scale_factor();

                // The mesh is a proxy volume, not the effect: every vertex is pushed out onto a sphere of
                // the zero-strength radius, so ANY closed mesh works and its own radius never enters the
                // maths. That is what keeps this shader mesh-independent.
                float3 vertex_ws = mul(unity_ObjectToWorld, input.position_os).xyz;
                float3 dir_ws = vertex_ws - output.sphere_center_ws;
                float dist_ws = length(dir_ws);

                if (dist_ws > 0.001)
                {
                    vertex_ws = output.sphere_center_ws
                              + (dir_ws / dist_ws) * (_AoE_MaxDistance * output.aoe_scale);
                }

                output.position = mul(UNITY_MATRIX_VP, float4(vertex_ws, 1.0));
                output.grab_screen_pos = ComputeGrabScreenPos(output.position);
            }

            half4 fragment_stage(FragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                half4 scene_color = UNITY_SAMPLE_TEX2D_LOD(
                    _GammaAdjustGrabTexture,
                    input.grab_screen_pos.xy / input.grab_screen_pos.w,
                    0
                );

                // Early exit: every effect neutral. The material inspector warns about this state, because
                // on screen it is indistinguishable from a broken install.
                bool has_gamma = abs(_Gamma_Adjust_Value) > 0.001;
                bool has_exposure = false;
                bool has_scotopic = false;

                #ifdef _EXPOSURE_ENABLED
                    has_exposure = abs(_Exposure_Value) > 0.001;
                #endif
                #ifdef _SCOTOPIC_ENABLED
                    has_scotopic = _Scotopic_Strength > 0.001;
                #endif

                if (!has_gamma && !has_exposure && !has_scotopic)
                {
                    return scene_color;
                }

                float3 eye_camera_ws = dbg_camera_eye_ws();
                float3 sphere_ws = input.sphere_center_ws;

                float aoe_min = _AoE_MinDistance * input.aoe_scale;
                float aoe_max = max(_AoE_MaxDistance * input.aoe_scale, aoe_min + 0.001);
                float core_radius = _Core_Radius * input.aoe_scale;

                // ─────────────────────────────────────────────────────────────────────────────────────
                // Volumetric strength.
                //
                // The sphere of influence is treated as a region that absorbs light passing through it.
                // For each pixel we find the closest point on the camera->surface ray SEGMENT to the
                // sphere centre, so objects behind the sphere stay dark (the ray crossed the dense core to
                // reach the camera), objects in front get only what the ray clips, and there is no
                // discontinuity at the boundary.
                // ─────────────────────────────────────────────────────────────────────────────────────
                float closest_dist = 1e6;
                {
                    DepthReconstruction dr = DepthReconstruction::init(input.position);
                    float4 vs_result = dr.position_vs_checked();

                    float3 cam_to_sphere = sphere_ws - eye_camera_ws;

                    if (vs_result.w > 0.5)
                    {
                        float3 pixel_ws = mul(unity_MatrixInvV, float4(vs_result.xyz, 1)).xyz;

                        float3 cam_to_pixel = pixel_ws - eye_camera_ws;
                        float t_surface = length(cam_to_pixel);
                        float3 ray_dir = cam_to_pixel / max(t_surface, 0.0001);

                        float t_projected = dot(cam_to_sphere, ray_dir);
                        float t_clamped = clamp(t_projected, 0.0, t_surface);
                        float3 closest_point = eye_camera_ws + t_clamped * ray_dir;
                        closest_dist = distance(closest_point, sphere_ws);
                    }
                    else
                    {
                        // Skybox / far-plane pixel: the ray extends to infinity, so the closest approach is
                        // the unclamped projection, bounded only at the camera itself (t = 0).
                        float3 ray_vs = dr.view_ray_direction_vs();
                        float3 ray_ws = normalize(mul((float3x3) unity_MatrixInvV, ray_vs));

                        float t_closest = max(0.0, dot(cam_to_sphere, ray_ws));
                        float3 closest_point = eye_camera_ws + t_closest * ray_ws;
                        closest_dist = distance(closest_point, sphere_ws);
                    }
                }

                float strength = 1.0 - smoothstep(aoe_min, aoe_max, closest_dist);

                // Core emphasis: rays passing through the core get an extra dim/brighten applied AFTER
                // grading, as a plain multiply, which is perceptually uniform whatever the gamma. A 1 cm
                // feather (at unit scale) gives the silhouette a clean anti-aliased edge.
                float core_feather_inner = max(core_radius - 0.01 * input.aoe_scale, 0.0);
                float core = 1.0 - smoothstep(core_feather_inner, core_radius, closest_dist);

                half3 current_rgb = scene_color.rgb;

                #ifdef _EXPOSURE_ENABLED
                    // 1 EV = 2x light.
                    float exposure_multiplier = exp2(_Exposure_Value);
                    float exposure_lerp = lerp(1.0, exposure_multiplier, strength);
                    current_rgb *= exposure_lerp;
                #endif

                float gamma = lerp(1.0, exp(_Gamma_Adjust_Value), strength);
                half3 clamped = saturate(current_rgb);
                half3 emission = _Transmit_Emission > 0.5
                    ? (half3)(current_rgb - clamped)
                    : half3(0, 0, 0);

                half3 final_rgb = pow(clamped, (half)gamma) + emission;

                #ifdef _SCOTOPIC_ENABLED
                    // Luma weights (Rec. 601)
                    half luma = dot(final_rgb, half3(0.299, 0.587, 0.114));
                    half3 scotopic_rgb = luma * _Scotopic_Tint.rgb;
                    half blend_factor = strength * saturate(_Scotopic_Strength);
                    final_rgb = lerp(final_rgb, scotopic_rgb, blend_factor);
                #endif

                // Push the core the same direction as the overall effect: darkening dims it, brightening
                // brightens it, neutral leaves it invisible.
                float effect_dir = _Gamma_Adjust_Value;
                #ifdef _EXPOSURE_ENABLED
                    effect_dir += -_Exposure_Value;
                #endif
                float core_amount = core * _Core_Intensity * saturate(abs(effect_dir));
                float core_factor = 1.0 - sign(effect_dir) * core_amount;
                final_rgb *= core_factor;

                return half4(final_rgb, 1);
            }
            ENDCG
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 2: CRYSTAL_SHELL
        //
        // The shared shell, then the same scene grading applied back onto it at reduced strength. Unlike
        // its siblings this pass post-processes shell_rgb() rather than returning it: the shell is a
        // self-luminous surface that should dim SOMEWHAT with the scene it sits in (so it does not read as
        // a compositing artifact in deep dark) but never crush to black (so the bubble stays locatable).
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
            #pragma shader_feature_local _EXPOSURE_ENABLED
            #pragma shader_feature_local _SCOTOPIC_ENABLED

            #include "crystal_shell.hlsl"

            uniform float _Gamma_Adjust_Value;
            uniform float _Shell_Grading_Resist;
            #ifdef _EXPOSURE_ENABLED
                uniform float _Exposure_Value;
            #endif
            #ifdef _SCOTOPIC_ENABLED
                uniform float _Scotopic_Strength;
                uniform half4 _Scotopic_Tint;
            #endif

            half4 shell_fragment_stage(ShellFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

            #if !defined(_SHELL_ON)
                return half4(0, 0, 0, 0);
            #else
                half3 shell = shell_rgb(input.normal_ws, input.position_ws);

                // resist 1 -> shell ignores all grading; 0 -> obeys it fully and disappears in the dark;
                // 0.5 -> takes half the darkening, legible but not jarring. Mechanically: lerp each grading
                // exponent/multiplier back toward identity by the resist fraction before applying it.
                float resist = saturate(_Shell_Grading_Resist);

                #ifdef _EXPOSURE_ENABLED
                {
                    float full_mult = exp2(_Exposure_Value);
                    shell *= lerp(full_mult, 1.0, resist);
                }
                #endif

                {
                    float full_gamma = exp(_Gamma_Adjust_Value);
                    float shell_gamma = lerp(full_gamma, 1.0, resist);
                    half3 clamped = saturate(shell);
                    half3 emission = max(0, shell - clamped);
                    shell = pow(clamped, (half)shell_gamma) + emission;
                }

                #ifdef _SCOTOPIC_ENABLED
                {
                    // A hue/chroma shift rather than a brightness crush, so it applies at full strength and
                    // the shell's colours match the scene tint.
                    half luma = dot(shell, half3(0.299, 0.587, 0.114));
                    shell = lerp(shell, luma * _Scotopic_Tint.rgb, saturate(_Scotopic_Strength));
                }
                #endif

                // Pure additive: alpha 0 keeps this identical to the rest of the family.
                return half4(shell, 0);
            #endif
            }
            ENDCG
        }
    }

    CustomEditor "Ryan6Vrc.AvatarTools.Editor.GammaCrystalShaderGUI"
}
