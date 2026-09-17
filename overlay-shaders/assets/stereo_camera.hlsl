#ifndef STEREO_CAMERA_INCLUDED
#define STEREO_CAMERA_INCLUDED

// Stereo-correct camera positions, shared by every shader in the entry. Its own file rather than a corner
// of crystal_shell.hlsl because the display shader's TEXT pass needs it while wanting none of the shell's
// uniforms, and one fact belongs in one place regardless of who else is nearby.
//
// THE ANCESTORS' GUARD IS DEAD CODE IN VRCHAT AND WE FIX IT HERE. Every shader this entry is built from
// tests `#ifdef UNITY_SINGLE_PASS_STEREO`, which is the deprecated double-wide path. VRChat PC runs
// single-pass INSTANCED: HLSLSupport.cginc:26-27 defines UNITY_STEREO_INSTANCING_ENABLED from
// STEREO_INSTANCING_ON, and UnityShaderVariables.cginc:10-12 folds that into USING_STEREO_MATRICES --
// under which line 24 has already redefined _WorldSpaceCameraPos to
// unity_StereoWorldSpaceCameraPos[unity_StereoEyeIndex].
//
// So both of the original helpers fall through to a PER-EYE position. The eye one is right by accident;
// the centre one is not, and anything built on it -- a billboard plane's normal, the rim's parallax anchor
// -- then differs between the eyes, giving a stereo disparity that corresponds to no fixed geometry at all.
// Poiyomi gets this right the same way (CGI_PoiHelpers.cginc:68-74).
//
// NOT every UNITY_SINGLE_PASS_STEREO in the ancestors was this bug. depth_reconstruct.hlsl keeps one on
// purpose: there the guarded code is a double-wide-only correction that is CORRECT to leave inert under
// instancing, and converting it would have introduced the very defect this file removes.

#include "UnityCG.cginc"

float3 dbg_camera_eye_ws()
{
    #if defined(USING_STEREO_MATRICES)
        return unity_StereoWorldSpaceCameraPos[unity_StereoEyeIndex];
    #else
        return _WorldSpaceCameraPos.xyz;
    #endif
}

float3 dbg_camera_center_ws()
{
    #if defined(USING_STEREO_MATRICES)
        return 0.5 * (unity_StereoWorldSpaceCameraPos[0] + unity_StereoWorldSpaceCameraPos[1]);
    #else
        return _WorldSpaceCameraPos.xyz;
    #endif
}

#endif // STEREO_CAMERA_INCLUDED
