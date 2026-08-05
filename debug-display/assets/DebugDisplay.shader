// Ryan6VRC/Overlay/DebugDisplay -- a generalized in-world numeric readout for avatar debugging.
//
// Derived from lereldarion/unity-shaders (MIT, (c) 2025 Lereldarion), ancestor Shaders/Overlay_HUD.shader.
// Upstream's are the Font metric ratios, median(), the screenspace-scale and SDF-blend helpers, and the
// fragment-stage ray-traced billboard plane. Ours are the 6-bit charset and its regenerated atlas, the
// entry grid with per-entry decimals/rpad/palette, the per-entry value sources, the three display modes,
// the crystal shell pass, and the string->float label packing. Full split in the entry README.
//
// Namespaced under Ryan6VRC/ rather than plain Overlay/ because upstream ships an Overlay/* family in a
// VPM package a consumer could install alongside this one, and a name collision resolves arbitrarily.
//
// Bundled Geist Mono glyphs: SIL Open Font License 1.1, see GeistMono-OFL.txt beside this file.

Shader "Ryan6VRC/Overlay/DebugDisplay"
{
    Properties
    {
        [Header(Layout)]
        [KeywordEnum(Billboard, Object, UV)] _Display_Mode("Display mode", Float) = 0
        _Font_Size("Font size (m per ascender)", Range(0.001, 0.25)) = 0.0225
        // Billboard and object modes trace against a plane built from NORMALIZED basis vectors, which
        // protects the monospace grid from a stretched mesh but also discards object scale -- leaving
        // _Font_Size an absolute physical size. With Cull Back making the mesh a window, text that
        // outgrows its mesh is not clipped at the edge, it is ABSENT: shrink the avatar and the readout
        // vanishes rather than degrading. On makes _Font_Size relative to object scale so the text
        // always fits its mesh, and makes all three modes agree (UV mode is already scale-relative,
        // since _Font_Size cancels out of it). Off reproduces the ancestor's world-fixed behaviour.
        [ToggleUI] _Font_Scale_Relative("Scale text with object", Float) = 1
        // In GLYPH ADVANCES, not metres. With _Font_Size in metres-per-ascender one advance is a derived
        // length, so a metre-valued width would silently rescale the layout every time the font size
        // moved. In advances the two knobs are independent and the GUI's preview is computable from
        // neither. A cell needs 12 (label) + 10 (value) = 22 advances to avoid clipping.
        _Total_Width("Total width (glyph advances)", Range(10, 200)) = 24
        [IntRange] _Grid_Columns("Grid columns", Range(1, 6)) = 1
        [IntRange] _Grid_Rows("Grid rows", Range(1, 6)) = 3
        _Text_Depth_Offset("Depth offset", Range(-0.5, 0.5)) = 0.0
        [NoScaleOffset] _MSDF_Glyph_Atlas("MSDF glyph atlas", 2D) = "" {}

        [Header(Text palette)]
        [HDR] _Palette_0("Palette 0", Color) = (1, 0.2, 0.2, 1)
        [HDR] _Palette_1("Palette 1", Color) = (0.2, 1, 0.2, 1)
        [HDR] _Palette_2("Palette 2", Color) = (0.2, 0.5, 1, 1)
        [HDR] _Palette_3("Palette 3", Color) = (1, 1, 1, 1)

        // Entries. Three properties each: a packed label vector, a hidden packed format bitfield, and the
        // visible float that IS the animation target -- a consumer's clip binds material._E0_Value.
        //
        // Labels are NOT [HideInInspector]: with avatar-tools absent the material falls back to Unity's
        // default ShaderGUI, and a hidden property would make the entry unconfigurable rather than merely
        // awkward. The default is all-space (262143 per component); a zeroed vector would decode as glyph
        // 0 twelve times and print "++++++++++++" on a fresh material.
        //
        // Twelve is a shader constant, not a preference: the fragment stage selects an entry with a switch
        // over this many cases, and ShaderLab cannot declare a property array (SetVectorArray does not
        // survive a material save -- Material serializes only m_TexEnvs/m_Ints/m_Floats/m_Colors).
        [Header(Entries)]
        _E0_Label("E0 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E0_Format("E0 format (packed)", Float) = 0
        _E0_Value("E0 value", Float) = 0
        _E1_Label("E1 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E1_Format("E1 format (packed)", Float) = 0
        _E1_Value("E1 value", Float) = 0
        _E2_Label("E2 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E2_Format("E2 format (packed)", Float) = 0
        _E2_Value("E2 value", Float) = 0
        _E3_Label("E3 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E3_Format("E3 format (packed)", Float) = 0
        _E3_Value("E3 value", Float) = 0
        _E4_Label("E4 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E4_Format("E4 format (packed)", Float) = 0
        _E4_Value("E4 value", Float) = 0
        _E5_Label("E5 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E5_Format("E5 format (packed)", Float) = 0
        _E5_Value("E5 value", Float) = 0
        _E6_Label("E6 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E6_Format("E6 format (packed)", Float) = 0
        _E6_Value("E6 value", Float) = 0
        _E7_Label("E7 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E7_Format("E7 format (packed)", Float) = 0
        _E7_Value("E7 value", Float) = 0
        _E8_Label("E8 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E8_Format("E8 format (packed)", Float) = 0
        _E8_Value("E8 value", Float) = 0
        _E9_Label("E9 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E9_Format("E9 format (packed)", Float) = 0
        _E9_Value("E9 value", Float) = 0
        _E10_Label("E10 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E10_Format("E10 format (packed)", Float) = 0
        _E10_Value("E10 value", Float) = 0
        _E11_Label("E11 label (packed)", Vector) = (262143, 262143, 262143, 262143)
        [HideInInspector] _E11_Format("E11 format (packed)", Float) = 0
        _E11_Value("E11 value", Float) = 0

        [Header(Crystal shell)]
        [Toggle(_SHELL_ON)] _Shell_Enabled("Shell enabled", Float) = 1
        [HDR] _Shell_Reflection_Color("Color / Mask", Color) = (1,1,1,1)
        [NoScaleOffset] _Shell_ReflectionCube("Reflection cubemap", Cube) = "" {}
        _Shell_Reflection_Strength("Reflectance", Range(0, 4)) = 1
        _Shell_Reflection_Smoothness("Smoothness", Range(0, 1)) = 0.7
        // The LOD the perceptual-roughness curve reaches at roughness 1, i.e. what both vendors hardcode
        // as UNITY_SPECCUBE_LOD_STEPS. Ranged to 6 rather than 10 because a Specular-convolved chain is
        // already near-flat there, so the default IS lilToon's remap and the slider only trims blur.
        _Shell_Reflection_BlurMaxMip("Blur max mip (LOD steps)", Range(0, 6)) = 6

        [Header(Rim light)]
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
            // RESTORED from upstream, which the local copy had dropped while still reading the object
            // matrix. Dynamic batching bakes vertices to world space and leaves unity_ObjectToWorld
            // identity, so a batched display prints the BATCH ROOT's coordinates rather than its own.
            // It costs nothing (each display needs its own material anyway, so these never batch), and it
            // becomes live exactly here: a UV-mode quad is 4 vertices, well inside the eligible case,
            // and in-game the governing batching settings are the VRChat client's build, not ours.
            "DisableBatching" = "True"
        }

        // ────────────────────────────────────────────────────────────────────────────────────────────
        // PASS 1: the readout
        // ────────────────────────────────────────────────────────────────────────────────────────────
        Pass
        {
            Name "DEBUG_DISPLAY_TEXT"

            Cull Back
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            // ZTest Less here vs LEqual on the shell below. The asymmetry is upstream's and unexplained;
            // carried rather than "tidied", because equalising it would change what occludes what and the
            // ancestor's look is the equivalence target.
            ZTest Less

            CGPROGRAM
            #pragma warning (error : 3205)
            #pragma warning (error : 3206)

            #pragma target 5.0
            #pragma multi_compile_instancing
            #pragma multi_compile_local _DISPLAY_MODE_BILLBOARD _DISPLAY_MODE_OBJECT _DISPLAY_MODE_UV
            #pragma vertex vertex_stage
            #pragma fragment fragment_stage

            #include "debug_display_common.hlsl"

            uniform float _Font_Size;
            uniform float _Font_Scale_Relative;
            uniform float _Total_Width;
            uniform float _Grid_Columns;
            uniform float _Grid_Rows;
            uniform float _Text_Depth_Offset;

            uniform half4 _Palette_0, _Palette_1, _Palette_2, _Palette_3;

            uniform float4 _E0_Label, _E1_Label, _E2_Label, _E3_Label, _E4_Label, _E5_Label;
            uniform float4 _E6_Label, _E7_Label, _E8_Label, _E9_Label, _E10_Label, _E11_Label;
            uniform float _E0_Format, _E1_Format, _E2_Format, _E3_Format, _E4_Format, _E5_Format;
            uniform float _E6_Format, _E7_Format, _E8_Format, _E9_Format, _E10_Format, _E11_Format;
            uniform float _E0_Value, _E1_Value, _E2_Value, _E3_Value, _E4_Value, _E5_Value;
            uniform float _E6_Value, _E7_Value, _E8_Value, _E9_Value, _E10_Value, _E11_Value;

            struct VertexInput
            {
                float4 position_os : POSITION;
                float2 uv0 : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct FragmentInput
            {
                float4 position : SV_POSITION;
                nointerpolation float4 obj_a : OBJ_A;   // world xyz + azimuth
                nointerpolation float4 obj_b : OBJ_B;   // scale xyz + elevation
            #if defined(_DISPLAY_MODE_UV)
                float2 uv0 : UV0;
            #else
                float3 ray_ws : RAY_WS;
                nointerpolation float3 plane_origin_ws : PLANE_O;
                nointerpolation float3 plane_right_ws : PLANE_R;
                nointerpolation float3 plane_up_ws : PLANE_U;
                nointerpolation float3 plane_normal_ws : PLANE_N;
            #endif
                UNITY_VERTEX_OUTPUT_STEREO
            };

            void vertex_stage(VertexInput input, out FragmentInput output)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                output.position = UnityObjectToClipPos(input.position_os);

                // Object-matrix sources must be read HERE -- see dd_resolve_value's note on
                // unity_InstanceID.
                dd_object_sources(output.obj_a, output.obj_b);

            #if defined(_DISPLAY_MODE_UV)
                output.uv0 = input.uv0;
            #else
                float3 pos_ws = mul(unity_ObjectToWorld, float4(input.position_os.xyz, 1)).xyz;
                output.ray_ws = pos_ws - dd_camera_eye_ws();

                float3 origin_ws = output.obj_a.xyz;
                float3 right, up, normal;
                #if defined(_DISPLAY_MODE_OBJECT)
                    // Axes fixed to the object: a display floating inside whatever mesh carries it.
                    // Normalised so a NON-UNIFORMLY scaled object cannot stretch the monospace grid.
                    // That drops uniform scale too, which _Font_Scale_Relative puts back as a single
                    // scalar in the fragment stage -- consistently with billboard mode.
                    right = normalize(float3(unity_ObjectToWorld._m00, unity_ObjectToWorld._m10, unity_ObjectToWorld._m20));
                    up = normalize(float3(unity_ObjectToWorld._m01, unity_ObjectToWorld._m11, unity_ObjectToWorld._m21));
                    normal = normalize(float3(unity_ObjectToWorld._m02, unity_ObjectToWorld._m12, unity_ObjectToWorld._m22));
                #else
                    // Billboard: plane faces the STEREO-CENTRE camera, so both eyes ray-trace against one
                    // plane and the disparity is coherent. dd_camera_center_ws fixes the ancestor's
                    // dead-guard bug here.
                    normal = normalize(dd_camera_center_ws() - origin_ws);
                    up = float3(0, 1, 0);
                    right = cross(normal, up);
                    if (length(right) < 0.001) right = float3(1, 0, 0);   // camera directly overhead
                    else right = normalize(right);
                    up = cross(right, normal);
                #endif

                output.plane_right_ws = right;
                output.plane_up_ws = up;
                output.plane_normal_ws = normal;
                // Offsets the virtual PLANE, not geometry -- which is why it relocates to the vertex
                // stage untouched.
                output.plane_origin_ws = origin_ws - normal * _Text_Depth_Offset;
            #endif
            }

            half4 fragment_stage(FragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                // ── One mode branch, producing frame_uv in metres. Everything after is mode-agnostic.
                //
                // A SINGLE scalar -- the mean of the three axes, never per-axis. Per-axis would stretch
                // the glyphs, which is the exact thing normalizing the plane basis was protecting. Only
                // the font size moves: cell_h_px and grid_px are pure px and untouched, p_px picks it up
                // through font.scale and sdf() through font.inverse_scale, and it cancels out of UV mode
                // the same way _Font_Size itself does.
                float mean_scale = dot(input.obj_b.xyz, float3(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0));
                float scale_factor = lerp(1.0, mean_scale, _Font_Scale_Relative);
                Font font = Font::init(_Font_Size * scale_factor);
                float cell_w_px = (_Total_Width / max(_Grid_Columns, 1.0)) * Font::advance_px;
                float cell_h_px = Font::layout_bbox_px.y;
                float2 grid_px = float2(cell_w_px * _Grid_Columns, cell_h_px * _Grid_Rows);

                float2 frame_uv;
            #if defined(_DISPLAY_MODE_UV)
                // The mesh's 0-1 TEXCOORD0 span maps exactly onto the grid. _Font_Size cancels out of
                // this mode (it scales grid_px and frame_uv alike, via font.inverse_scale here and
                // font.scale below), and so does _Font_Scale_Relative with it: UV mode is inherently
                // scale-relative, because the quad's world size sets the apparent text size.
                frame_uv = (input.uv0 - 0.5) * (grid_px * font.inverse_scale);
            #else
                float3 camera_ws = dd_camera_eye_ws();
                float3 ray_dir = normalize(input.ray_ws);
                float denom = dot(ray_dir, input.plane_normal_ws);
                if (abs(denom) < 0.0001) discard;                        // ray parallel to the plane
                float t = dot(input.plane_origin_ws - camera_ws, input.plane_normal_ws) / denom;
                if (t < 0) discard;                                      // plane behind the camera
                float3 offset_ws = (camera_ws + t * ray_dir) - input.plane_origin_ws;
                frame_uv = float2(dot(offset_ws, input.plane_right_ws), dot(offset_ws, input.plane_up_ws));
            #endif

                // Derivatives BEFORE any cell-level discard. Derivatives after a discard in a divergent
                // quad are unreliable, and cell-boundary and grid-edge discards are exactly the quads
                // whose neighbours are text. The ancestor's own discards above are geometrically
                // coherent, so they are safe where these would not be.
                float screen_scale = dd_screenspace_scale_of_uv(frame_uv);

            #if defined(_DISPLAY_MODE_UV)
                // A mesh with no UVs feeds a constant TEXCOORD0, so it has no UV gradient. Detected
                // explicitly rather than left to emerge: with zero derivatives the AA smoothstep
                // degenerates to a HARD THRESHOLD, and inside a glyph that fills the whole mesh with
                // solid palette colour rather than rendering nothing.
                if (screen_scale <= 0.0) discard;
            #endif

                // ── Cell ────────────────────────────────────────────────────────────────────────────
                float2 p_px = frame_uv * font.scale + grid_px * 0.5;
                if (any(p_px < 0.0) || any(p_px > grid_px)) discard;

                uint cols = (uint)_Grid_Columns;
                uint rows = (uint)_Grid_Rows;
                uint col = (uint)floor(p_px.x / cell_w_px);
                uint row = (uint)floor(p_px.y / cell_h_px);
                // NOT redundant with the idx bound below. The p_px test is strict, so p_px == grid_px
                // yields col == cols, and float rounding in the division can produce it below the
                // boundary too; a 3x2 grid would then draw entry 3 outside its cell. And computing idx in
                // float would be worse -- _Grid_Rows is a ShaderLab Range hence float, so a row overflow
                // gives a negative that ftou CLAMPS to zero, silently drawing entry 0 in a phantom cell.
                if (col >= cols || row >= rows) discard;

                uint idx = (rows - 1u - row) * cols + col;               // row-major from the top-left
                if (idx >= (uint)DD_MAX_ENTRIES) discard;

                float2 cell_px = p_px - float2(col * cell_w_px, row * cell_h_px);

                float y_offset = dd_glyph_band_offset();
                if (cell_px.y < y_offset || cell_px.y > cell_h_px - y_offset) discard;

                // ── Entry ───────────────────────────────────────────────────────────────────────────
                // A switch, not a gathered local array. Compiled, a 12-float4 local array indexed by a
                // runtime value emits two dcl_indexableTemp plus 24 movs that run on EVERY fragment
                // reaching here; the switch emits none and executes ~6 instructions per lane. idx is
                // constant across a whole cell, so divergence is confined to cell borders.
                float4 label = _E0_Label;
                float fmt = _E0_Format;
                float entry_value = _E0_Value;
                [branch] switch (idx)
                {
                    case  1u: label = _E1_Label;  fmt = _E1_Format;  entry_value = _E1_Value;  break;
                    case  2u: label = _E2_Label;  fmt = _E2_Format;  entry_value = _E2_Value;  break;
                    case  3u: label = _E3_Label;  fmt = _E3_Format;  entry_value = _E3_Value;  break;
                    case  4u: label = _E4_Label;  fmt = _E4_Format;  entry_value = _E4_Value;  break;
                    case  5u: label = _E5_Label;  fmt = _E5_Format;  entry_value = _E5_Value;  break;
                    case  6u: label = _E6_Label;  fmt = _E6_Format;  entry_value = _E6_Value;  break;
                    case  7u: label = _E7_Label;  fmt = _E7_Format;  entry_value = _E7_Value;  break;
                    case  8u: label = _E8_Label;  fmt = _E8_Format;  entry_value = _E8_Value;  break;
                    case  9u: label = _E9_Label;  fmt = _E9_Format;  entry_value = _E9_Value;  break;
                    case 10u: label = _E10_Label; fmt = _E10_Format; entry_value = _E10_Value; break;
                    case 11u: label = _E11_Label; fmt = _E11_Format; entry_value = _E11_Value; break;
                    default: break;
                }

                uint decimals, palette, rpad, source;
                dd_unpack_format(fmt, decimals, palette, rpad, source);
                float value = dd_resolve_value(source, entry_value, input.obj_a, input.obj_b);

                // ── Glyph ───────────────────────────────────────────────────────────────────────────
                // The value region wins and a SPACE in it falls through to the label. That ordering picks
                // the better failure mode: a short label's trailing spaces overlap the value harmlessly,
                // while a genuine collision (long label + wide value) overdraws the label's tail into
                // visibly garbled text -- which is a diagnostic. Label-first would instead BLANK the
                // value's leading digits, and a truncated number reads as a plausible smaller one.
                float value_right_px = cell_w_px - (float)rpad * Font::advance_px;
                float value_left_px = value_right_px - (float)DD_VALUE_GLYPHS * Font::advance_px;

                uint glyph = Font::space;
                float x_in_advance = 0.0;

                if (cell_px.x >= value_left_px && cell_px.x < value_right_px)
                {
                    int n = (int)floor((value_right_px - cell_px.x) / Font::advance_px);   // 0 = rightmost
                    // The left bound is inclusive, so exactly on it the division yields n ==
                    // DD_VALUE_GLYPHS -- one column past the field, which is the column the minus sign
                    // wants. Bound n rather than widening the region: the same strict-vs-inclusive care
                    // the col/row guard above takes, applied here too.
                    if (n >= 0 && n < DD_VALUE_GLYPHS)
                    {
                        glyph = dd_value_glyph_at(value, decimals, n);
                        x_in_advance = cell_px.x - (value_right_px - (float)(n + 1) * Font::advance_px);
                    }
                }
                if (glyph == Font::space && cell_px.x < (float)DD_MAX_LABEL_CHARS * Font::advance_px)
                {
                    uint n = (uint)floor(cell_px.x / Font::advance_px);
                    glyph = dd_label_glyph_at(label, n);
                    x_in_advance = cell_px.x - (float)n * Font::advance_px;
                }
                if (glyph == Font::space) discard;

                font.sampling_atlas_id = glyph;
                font.sampling_offset_px = float2(x_in_advance, cell_px.y - y_offset);

                float alpha = dd_sdf_blend_with_aa(font.sdf(), screen_scale);
                if (alpha < 0.001) discard;

                half3 color = _Palette_0.rgb;
                if (palette == 1u) color = _Palette_1.rgb;
                else if (palette == 2u) color = _Palette_2.rgb;
                else if (palette == 3u) color = _Palette_3.rgb;

                // 0.95 is upstream's peak opacity, carried deliberately: under
                // Blend SrcAlpha OneMinusSrcAlpha the difference from 1.0 is visible, so changing it
                // would fail the equivalence check against the ancestor for a reason nobody would find.
                return half4(color, alpha * 0.95);
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

            #include "debug_display_common.hlsl"

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

            half4 shell_fragment_stage(ShellFragmentInput input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

            #if !defined(_SHELL_ON)
                return half4(0, 0, 0, 0);
            #else
                float3 N = normalize(input.normal_ws);

                float3 cam_eye_ws = dd_camera_eye_ws();
                float3 V_reflect = normalize(cam_eye_ws - input.position_ws);
                float3 R = normalize(reflect(-V_reflect, N));

                // Perceptual-roughness -> mip through Unity's own remap for a convolved specular cube
                // (perceptualRoughness * (1.7 - 0.7 * perceptualRoughness), UnityImageBasedLighting.cginc),
                // scaled by the slider where both vendors hardcode UNITY_SPECCUBE_LOD_STEPS = 6. lilToon
                // inlines the identical curve pre-multiplied: perceptualRoughness * (10.2 - 4.2 * pR).
                // The prior bare linear ramp was NOT equivalent: it under-blurs the mid range and, against
                // a chain that is already near-flat by mip 6, spent the slider's top third on dead travel.
                float perceptual_roughness = 1.0 - saturate(_Shell_Reflection_Smoothness);
                float reflection_mip = perceptual_roughness * (1.7 - 0.7 * perceptual_roughness)
                                     * _Shell_Reflection_BlurMaxMip;
                half3 reflection_sample = texCUBElod(_Shell_ReflectionCube, float4(R, reflection_mip)).rgb;
                half3 reflection_rgb = reflection_sample
                                     * _Shell_Reflection_Color.rgb
                                     * (_Shell_Reflection_Color.a * _Shell_Reflection_Strength);

                // The rim's viewpoint lerps between stereo centre and per-eye: at 0 both eyes see the
                // same rim (flat but stable), at 1 it parallaxes properly.
                float3 cam_rim_ws = lerp(dd_camera_center_ws(), cam_eye_ws, saturate(_Shell_Rim_VRParallaxStrength));
                float3 V_rim = normalize(cam_rim_ws - input.position_ws);

                float ndv = saturate(dot(N, V_rim));
                float rim_base = pow(saturate(1.0 - ndv), max(_Shell_Rim_FresnelPower, 0.0001));

                float rim_min = saturate(_Shell_Rim_Border - _Shell_Rim_Blur * 0.5);
                float rim_max = saturate(_Shell_Rim_Border + _Shell_Rim_Blur * 0.5);
                rim_max = max(rim_max, rim_min + 0.0001);

                float rim_mask = smoothstep(rim_min, rim_max, rim_base);
                half3 rim_rgb = _Shell_Rim_Color.rgb * (_Shell_Rim_Color.a * _Shell_Rim_Strength) * rim_mask;

                return half4(reflection_rgb + rim_rgb, 0);
            #endif
            }
            ENDCG
        }
    }

    CustomEditor "Ryan6Vrc.AvatarTools.Editor.DebugDisplayShaderGUI"
}
