using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Ryan6Vrc.Patterns.DebugShaders.Editor
{
    /// <summary>
    /// Material inspector for <c>Ryan6VRC/Overlay/TransClip</c> — a depth wall with a front-face shell. The
    /// shell half is the family's, so this class exists for two things the shared base cannot supply: the
    /// base-alpha control (an unclaimed property raises <see cref="CrystalShellShaderGUI.DrawUnclaimed"/>'s
    /// error box, and <see cref="CrystalShellShaderGUI"/> is abstract besides), and the render queue.
    ///
    /// <para><b>The queue is this shader's main knob and it is not a shader property.</b> What gets clipped
    /// is decided entirely by where the material sorts, so the Rendering fold's Render Queue field is the
    /// control an operator actually reaches for — and it is buried under an "Advanced" header on every other
    /// member of the family. The summary block below states the current setting in the vocabulary of the
    /// effect rather than as a number, because 2440 and 2451 look like the same value and behave
    /// differently.</para>
    /// </summary>
    public class TransClipShaderGUI : CrystalShellShaderGUI
    {
        static readonly string[] AlphaProps = { "_Shell_Alpha" };

        protected override IEnumerable<string> ClaimedProperties
        {
            get { return base.ClaimedProperties.Concat(AlphaProps); }
        }

        public override void OnGUI(MaterialEditor materialEditor, MaterialProperty[] properties)
        {
            var mat = materialEditor.target as Material;
            if (mat == null) { base.OnGUI(materialEditor, properties); return; }
            if (RefuseMultiSelect(materialEditor, "The queue summary and shell controls"))
            {
                base.OnGUI(materialEditor, properties);
                return;
            }

            EnsureStyles();
            DrawSummary(mat);

            DrawShellSection(materialEditor, properties, mat);

            // Outside the shell fold on purpose: with the shell disabled this material is a pure depth wall,
            // and the alpha is then the one number explaining why nothing is visible. A control that
            // disappears with the section is a control an operator looks for and cannot find.
            using (Body())
            {
                EditorGUILayout.LabelField("Shell coverage", EditorStyles.boldLabel);
                DrawNamed(materialEditor, properties, AlphaProps);
            }

            DrawRenderingSection(materialEditor);
            DrawUnclaimed(properties);
        }

        /// <summary>
        /// Never inside a fold, same role as the sibling inspectors': what this material is currently
        /// clipping, read off the effective queue, plus the two states that render as "nothing happened".
        /// </summary>
        static void DrawSummary(Material mat)
        {
            // -1 means "take the shader's own queue tag", which is what an untouched material carries; the
            // material's serialized override is the value otherwise. Material.renderQueue resolves the pair,
            // but returns -1 before the shader is loaded, so fall back to the shader's.
            int queue = mat.renderQueue;
            if (queue < 0 && mat.shader != null) queue = mat.shader.renderQueue;

            string clips =
                queue < 2450 ? "cutout materials and transparents alike — the default"
              : queue == 2450 ? "transparents, and cutout materials only by per-object sort order: 2450 is " +
                "the cutout queue itself, so which of the two draws first is not decided by the queue — use " +
                "2449 or 2451 for a definite answer"
              : queue < 3000 ? "transparents only; cutout materials draw through it"
              : "nothing useful: the wall sorts with the transparents it is meant to clip, so what it hides " +
                "depends on per-object sort order";

            EditorGUILayout.HelpBox(
                "Render queue " + queue + ": the depth wall clips " + clips + ". The queue is what decides " +
                "this — set it in Advanced > Rendering below, not on the shader.", MessageType.Info);

            var warnings = new List<string>();

            if (GetFloat(mat, "_Shell_Enabled", 1f) == 0f)
                warnings.Add("The shell is off, so this material draws no colour at all and the object is " +
                             "invisible from every angle. That is a legitimate setting — it is also " +
                             "indistinguishable from a broken install, so expect to verify it by what " +
                             "disappears behind the object rather than by looking at the object.");
            else if (GetFloat(mat, "_Shell_Alpha", 0.015f) <= 0f)
            {
                // Read as a Color: GetFloat on a colour property is not a type Unity coerces.
                float rimAlpha = mat.HasProperty("_Shell_Rim_Color")
                    ? mat.GetColor("_Shell_Rim_Color").a * GetFloat(mat, "_Shell_Rim_Strength", 1f)
                    : 0f;
                if (rimAlpha <= 0f)
                    warnings.Add("Base alpha and rim alpha are both 0, so the shell pass writes nothing " +
                                 "and only the depth wall remains. Raise one, or turn the shell off and " +
                                 "mean it.");
            }

            if (warnings.Count > 0)
                EditorGUILayout.HelpBox(string.Join("\n\n", warnings), MessageType.Warning);
        }
    }
}
