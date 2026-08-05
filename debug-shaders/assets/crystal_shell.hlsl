#ifndef CRYSTAL_SHELL_INCLUDED
#define CRYSTAL_SHELL_INCLUDED

// The crystal shell: an additive cubemap reflection plus a fresnel rim, shared by every shader in the
// debug-shaders entry. One home for the property block, the vertex stage, and the shading itself -- each
// shader's shell pass is then pragmas, this include, and a fragment that decides what to do with the
// returned colour. The stereo-correct camera positions it reads are stereo_camera.hlsl's.
//
// The three consumers agree on everything up to that colour and disagree only after it: DebugDisplay and
// DebugOverlay return it, GammaCrystal puts it through the same scene grading it applies to the world.
// That is the whole reason this is a function returning half3 rather than a fragment stage.
//
// Provenance: the shell/rim code is ours, written for a private project's overlay shaders and generalized
// here. It is not upstream's -- lereldarion/unity-shaders has no equivalent pass. See the entry README.

#include "UnityCG.cginc"
#include "stereo_camera.hlsl"

// ── Properties ──────────────────────────────────────────────────────────────────────────────────────
//
// Declared once here rather than in each pass. Every shader in the entry declares the same names in its
// own Properties block -- ShaderLab has no way to share that half -- so the pair is a managed echo, and
// the Properties block is where the ranges and defaults live.

uniform half4 _Shell_Reflection_Color;
uniform samplerCUBE _Shell_ReflectionCube;
uniform float _Shell_Reflection_Strength;
uniform float _Shell_Reflection_Smoothness;
uniform float _Shell_Reflection_BlurMaxMip;

uniform half4 _Shell_Rim_Color;
uniform float _Shell_Rim_Strength;
uniform float _Shell_Rim_Border;
uniform float _Shell_Rim_Blur;
uniform float _Shell_Rim_FresnelPower;
uniform float _Shell_Rim_VRParallaxStrength;

// ── Vertex stage ────────────────────────────────────────────────────────────────────────────────────

struct ShellVertexInput
{
    float4 position_os : POSITION;
    float3 normal_os : NORMAL;
    UNITY_VERTEX_INPUT_INSTANCE_ID
};

struct ShellFragmentInput
{
    float4 position : SV_POSITION;
    float3 position_ws : TEXCOORD0;
    float3 normal_ws : TEXCOORD1;
    UNITY_VERTEX_OUTPUT_STEREO
};

void shell_vertex_stage(ShellVertexInput input, out ShellFragmentInput output)
{
    UNITY_SETUP_INSTANCE_ID(input);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

    output.position = UnityObjectToClipPos(input.position_os);
    output.position_ws = mul(unity_ObjectToWorld, input.position_os).xyz;
    output.normal_ws = UnityObjectToWorldNormal(input.normal_os);
}

// ── Shading ─────────────────────────────────────────────────────────────────────────────────────────

/// The shell's colour at one fragment. Additive by construction: the caller blends One One and passes
/// alpha 0, so nothing here needs to know about the surface behind it.
half3 shell_rgb(float3 normal_ws, float3 position_ws)
{
    float3 N = normalize(normal_ws);

    // Reflections use the per-eye camera, so the reflection parallaxes correctly in VR.
    float3 cam_eye_ws = dbg_camera_eye_ws();
    float3 V_reflect = normalize(cam_eye_ws - position_ws);
    float3 R = normalize(reflect(-V_reflect, N));

    // Perceptual-roughness -> mip through Unity's own remap for a convolved specular cube
    // (perceptualRoughness * (1.7 - 0.7 * perceptualRoughness), UnityImageBasedLighting.cginc), scaled by
    // the slider where both vendors hardcode UNITY_SPECCUBE_LOD_STEPS = 6. lilToon inlines the identical
    // curve pre-multiplied: perceptualRoughness * (10.2 - 4.2 * pR). The bare linear ramp this replaced
    // was NOT equivalent: it under-blurs the mid range and, against a chain that is already near-flat by
    // mip 6, spent the slider's top third on dead travel. The cubemap must be imported with
    // cubemapConvolution = 1 or the whole curve is inert -- see the entry README's import-settings table.
    float perceptual_roughness = 1.0 - saturate(_Shell_Reflection_Smoothness);
    float reflection_mip = perceptual_roughness * (1.7 - 0.7 * perceptual_roughness)
                         * _Shell_Reflection_BlurMaxMip;
    half3 reflection_sample = texCUBElod(_Shell_ReflectionCube, float4(R, reflection_mip)).rgb;
    half3 reflection_rgb = reflection_sample
                         * _Shell_Reflection_Color.rgb
                         * (_Shell_Reflection_Color.a * _Shell_Reflection_Strength);

    // The rim's viewpoint lerps between stereo centre and per-eye: at 0 both eyes see the same rim (flat
    // but stable), at 1 it parallaxes properly.
    float3 cam_rim_ws = lerp(dbg_camera_center_ws(), cam_eye_ws,
                             saturate(_Shell_Rim_VRParallaxStrength));
    float3 V_rim = normalize(cam_rim_ws - position_ws);

    float ndv = saturate(dot(N, V_rim));
    float rim_base = pow(saturate(1.0 - ndv), max(_Shell_Rim_FresnelPower, 0.0001));

    float rim_min = saturate(_Shell_Rim_Border - _Shell_Rim_Blur * 0.5);
    float rim_max = saturate(_Shell_Rim_Border + _Shell_Rim_Blur * 0.5);
    rim_max = max(rim_max, rim_min + 0.0001);

    float rim_mask = smoothstep(rim_min, rim_max, rim_base);
    half3 rim_rgb = _Shell_Rim_Color.rgb * (_Shell_Rim_Color.a * _Shell_Rim_Strength) * rim_mask;

    return reflection_rgb + rim_rgb;
}

#endif // CRYSTAL_SHELL_INCLUDED
