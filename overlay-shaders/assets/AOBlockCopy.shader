// Ryan6VRC/Overlay/AOBlockCopy -- the copy half of the AO block pair. It draws nothing: its GrabPass saves
// the frame at the last opaque queue, which is before the world's post-processing multiplies ambient
// occlusion in (PostProcessing v2 composites forward AO at CameraEvent.BeforeImageEffectsOpaque, after the
// opaque queues and the skybox and before queue 2501). AOBlock, queued at 2501, pastes that copy back inside
// its sphere.
//
// Two shaders because a material has one queue and the copy and the paste sit either side of the AO
// composite. Host both on renderers that share a mesh and a transform so they are frustum-culled together:
// a paste whose copy was culled reads the previous camera's image.
//
// The technique (copy before AO, paste after) is the one NochaStore's "AOB - Ambient Occlusion Block" ships;
// no code is shared with it.

Shader "Ryan6VRC/Overlay/AOBlockCopy"
{
    Properties
    {
    }

    SubShader
    {
        Tags
        {
            // LOAD-BEARING. 2500 is the last queue Unity draws before the skybox and the AO composite, so the
            // copy holds every opaque and cutout surface, lit and un-occluded. The sky is not in it yet;
            // AOBlock never pastes a sky pixel.
            "Queue" = "Geometry+500"
            // Not Opaque: an Opaque RenderType would put the host mesh in _CameraDepthNormalsTexture.
            "RenderType" = "Transparent"
            "VRCFallback" = "Hidden"
            "PreviewType" = "Plane"
            "IgnoreProjector" = "True"
        }

        GrabPass { "_AOBlockPreAOTexture" }

        Pass
        {
            Name "COPY_TRIGGER"

            Cull Off
            ZWrite Off
            ZTest Always
            ColorMask 0

            CGPROGRAM
            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma vertex trigger_vertex_stage
            #pragma fragment trigger_fragment_stage

            #include "UnityCG.cginc"

            struct TriggerVertexInput
            {
                float4 position_os : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct TriggerFragmentInput
            {
                float4 position : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            // Every triangle degenerates: the GrabPass above runs because the renderer is drawn, not because
            // a fragment lands.
            void trigger_vertex_stage(TriggerVertexInput input, out TriggerFragmentInput output)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                output.position = float4(0, 0, 0, 0);
            }

            half4 trigger_fragment_stage(TriggerFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                return half4(0, 0, 0, 0);
            }
            ENDCG
        }
    }
}
