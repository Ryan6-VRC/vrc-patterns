using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Ryan6Vrc.Patterns.DebugShaders.Editor
{
    /// <summary>
    /// Material inspector for <c>Ryan6VRC/Overlay/GammaCrystal</c> — a localized grading bubble (gamma,
    /// optional linear exposure, optional scotopic desaturation) applied through a grab pass, with the
    /// shared crystal shell as its visible surface.
    ///
    /// <para>Unlike its siblings this shader has three independently-switchable effects and an area of
    /// effect measured in metres, so the two failure modes worth naming are both "renders something
    /// plausible": every effect neutral (the fragment early-outs and only the shell draws, which looks like a
    /// broken install), and a minimum distance at or past the maximum (the shader has to clamp, turning the
    /// smooth falloff into a hard edge).</para>
    /// </summary>
    public class GammaCrystalShaderGUI : CrystalShellShaderGUI
    {
        static readonly string[] GammaProps = { "_Gamma_Adjust_Value", "_Transmit_Emission" };
        static readonly string[] ExposureToggleProps = { "_Exposure_Enable" };
        static readonly string[] ExposureProps = { "_Exposure_Value" };
        static readonly string[] ScotopicToggleProps = { "_Scotopic_Enable" };
        static readonly string[] ScotopicProps = { "_Scotopic_Strength", "_Scotopic_Tint" };
        static readonly string[] AoEProps =
            { "_AoE_Scale_Relative", "_AoE_MinDistance", "_AoE_MaxDistance", "_Core_Radius",
              "_Core_Intensity" };
        static readonly string[] GradingResistProps = { "_Shell_Grading_Resist" };

        static bool _showGrading = true;
        static bool _showAoE = true;

        protected override IEnumerable<string> ClaimedProperties
        {
            get
            {
                return base.ClaimedProperties
                    .Concat(GammaProps).Concat(ExposureToggleProps).Concat(ExposureProps)
                    .Concat(ScotopicToggleProps).Concat(ScotopicProps)
                    .Concat(AoEProps).Concat(GradingResistProps);
            }
        }

        public override void OnGUI(MaterialEditor materialEditor, MaterialProperty[] properties)
        {
            var mat = materialEditor.target as Material;
            if (mat == null) { base.OnGUI(materialEditor, properties); return; }
            if (RefuseMultiSelect(materialEditor, "The grading and area-of-effect controls"))
            {
                base.OnGUI(materialEditor, properties);
                return;
            }

            EnsureStyles();
            DrawSummary(mat);

            if (Section("Grading", "What the bubble does to the scene inside it", ref _showGrading))
                using (Body())
                {
                    // The three group names live here, not in a shader [Header]: Unity draws a property's
                    // header inside whichever section drew the property, which titles the fold twice.
                    EditorGUILayout.LabelField("Gamma", EditorStyles.boldLabel);
                    DrawNamed(materialEditor, properties, GammaProps);
                    Line();
                    EditorGUILayout.LabelField("Exposure", EditorStyles.boldLabel);
                    DrawNamed(materialEditor, properties, ExposureToggleProps);
                    if (GetFloat(mat, "_Exposure_Enable", 0f) != 0f)
                        DrawNamed(materialEditor, properties, ExposureProps);
                    Line();
                    EditorGUILayout.LabelField("Scotopic desaturation", EditorStyles.boldLabel);
                    DrawNamed(materialEditor, properties, ScotopicToggleProps);
                    if (GetFloat(mat, "_Scotopic_Enable", 0f) != 0f)
                        DrawNamed(materialEditor, properties, ScotopicProps);
                }

            if (Section("Area of effect", "How far the grading reaches, and the dense core inside it",
                        ref _showAoE))
                using (Body())
                    DrawNamed(materialEditor, properties, AoEProps);

            DrawShellSection(materialEditor, properties, mat);
            // Not inside the shell fold: it governs how much of the scene grading the shell receives, so it
            // is a property of the interaction between the two sections rather than of either one. Drawn
            // after both, where an operator has just seen what it mediates.
            using (Body())
            {
                EditorGUILayout.LabelField("Shell scene grading", EditorStyles.boldLabel);
                DrawNamed(materialEditor, properties, GradingResistProps);
            }

            DrawRenderingSection(materialEditor);
            DrawUnclaimed(properties);
        }

        /// <summary>
        /// The block that is never inside a fold, same role as the display inspector's: a fault on a
        /// collapsed section still shows up here.
        /// </summary>
        static void DrawSummary(Material mat)
        {
            var warnings = new List<string>();

            bool hasGamma = Mathf.Abs(GetFloat(mat, "_Gamma_Adjust_Value", 0f)) > 0.001f;
            bool hasExposure = GetFloat(mat, "_Exposure_Enable", 0f) != 0f &&
                               Mathf.Abs(GetFloat(mat, "_Exposure_Value", 0f)) > 0.001f;
            bool hasScotopic = GetFloat(mat, "_Scotopic_Enable", 0f) != 0f &&
                               GetFloat(mat, "_Scotopic_Strength", 0f) > 0.001f;

            if (!hasGamma && !hasExposure && !hasScotopic)
                warnings.Add("Every effect is neutral, so the grading pass returns the scene untouched and " +
                             "only the crystal shell renders. That looks like a broken install rather than " +
                             "a disabled effect — set a gamma value, or enable exposure or scotopic.");

            float min = GetFloat(mat, "_AoE_MinDistance", 1f);
            float max = GetFloat(mat, "_AoE_MaxDistance", 2f);
            if (min >= max)
                warnings.Add("Full-strength distance (" + min.ToString("0.###") + " m) is at or past the " +
                             "zero-strength distance (" + max.ToString("0.###") + " m). The shader clamps " +
                             "the maximum up to keep the falloff finite, so the bubble gets a hard edge " +
                             "instead of a smooth one.");

            if (warnings.Count > 0)
                EditorGUILayout.HelpBox(string.Join("\n\n", warnings), MessageType.Warning);
        }
    }
}
