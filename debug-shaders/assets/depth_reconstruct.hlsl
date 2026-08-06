#ifndef DEPTH_RECONSTRUCT_INCLUDED
#define DEPTH_RECONSTRUCT_INCLUDED

// Reconstructing a view-space position from the camera depth texture: the clip->view matrix derivation and
// the sampling around it, shared by DebugOverlay (both probe modes) and GammaCrystal (its volumetric
// strength term). One home, because the matrix is four chained corrections whose order is not obvious and
// which two shaders must agree on exactly.
//
// NOTHING ON AN AVATAR POPULATES _CameraDepthTexture. A shader reading it renders a flat fill rather than
// erroring when it is absent, so every consumer of this file needs a depth source in the scene -- the
// entry's sample prefabs ship a shadow-casting directional light for exactly that, and the entry README
// explains its four settings. This is also why the display shader does NOT include this file: it measures
// camera-to-object distance from the object matrix instead, which is always available and always right.

#include "UnityCG.cginc"

UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
uniform float4 _CameraDepthTexture_TexelSize;

struct DepthReconstruction
{
    float2 pixel_position;
    float4x4 cs_to_vs;

    static DepthReconstruction init(float4 fragment_sv_position)
    {
        DepthReconstruction o;
        o.pixel_position = fragment_sv_position.xy;

        float4x4 flipZ = float4x4(
            1, 0,  0, 0,
            0, 1,  0, 0,
            0, 0, -1, 1,
            0, 0,  0, 1
        );

        float4x4 scaleZ = float4x4(
            1, 0, 0,  0,
            0, 1, 0,  0,
            0, 0, 2, -1,
            0, 0, 0,  1
        );

        float4x4 invP = unity_CameraInvProjection;

        float4x4 flipY = float4x4(
            1, 0,                   0, 0,
            0, _ProjectionParams.x, 0, 0,
            0, 0,                   1, 0,
            0, 0,                   0, 1
        );

        o.cs_to_vs = mul(scaleZ, flipZ);
        o.cs_to_vs = mul(invP, o.cs_to_vs);
        o.cs_to_vs = mul(flipY, o.cs_to_vs);
        o.cs_to_vs._24 *= _ProjectionParams.x;
        o.cs_to_vs._42 *= -1;

        return o;
    }

    // DELIBERATELY still guarded on UNITY_SINGLE_PASS_STEREO, unlike the camera helpers in
    // stereo_camera.hlsl. That guard is dead code there and fixing it was the point; here it is dead code
    // that is CORRECT to leave dead. The half-width offset only exists because the deprecated double-wide
    // path packs both eyes into one render target, so clip x must be un-shifted per eye. Single-pass
    // instanced has no such packing, and applying the offset under USING_STEREO_MATRICES would sample the
    // depth texture two clip-space units off in the right eye. Kept rather than deleted so a consumer
    // rendering genuinely double-wide still gets the correction.
    float2 clip_position(float2 sv_position)
    {
        float2 clipPos = ((sv_position / _ScreenParams.xy) * 2 - 1) * float2(1, -1);
        #ifdef UNITY_SINGLE_PASS_STEREO
            clipPos.x -= 2 * unity_StereoEyeIndex;
        #endif
        return clipPos;
    }

    float3 position_vs(float2 pixel_shift)
    {
        float2 shifted = pixel_position + pixel_shift;
        float raw = SAMPLE_DEPTH_TEXTURE_LOD(
            _CameraDepthTexture, float4(shifted * _CameraDepthTexture_TexelSize.xy, 0, 0));

        float4 v = mul(cs_to_vs, float4(clip_position(shifted), raw, 1));
        return v.xyz / v.w;
    }

    float3 position_vs()
    {
        return position_vs(float2(0, 0));
    }

    /// Same reconstruction, plus whether the sample is real geometry.
    /// Returns xyz = view-space position, w = 1 for a valid surface, 0 for sky / far plane.
    float4 position_vs_checked()
    {
        float raw = SAMPLE_DEPTH_TEXTURE_LOD(
            _CameraDepthTexture, float4(pixel_position * _CameraDepthTexture_TexelSize.xy, 0, 0));

        float4 v = mul(cs_to_vs, float4(clip_position(pixel_position), raw, 1));

        // On reversed-Z (DX11): near = 1, far = 0. Valid geometry is strictly between.
        float valid = (raw > 0.0001 && raw < 0.9999) ? 1.0 : 0.0;
        return float4(v.xyz / v.w, valid);
    }

    /// A view-space ray direction for sky / far-plane pixels, where there is no surface to reconstruct.
    float3 view_ray_direction_vs()
    {
        float4 v = mul(cs_to_vs, float4(clip_position(pixel_position), 0.5, 1));
        return normalize(v.xyz / v.w);
    }
};

#endif // DEPTH_RECONSTRUCT_INCLUDED
