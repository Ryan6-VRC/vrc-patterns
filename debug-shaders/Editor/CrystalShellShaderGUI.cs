using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Ryan6Vrc.Patterns.DebugShaders.Editor
{
    /// <summary>
    /// Shared material inspector for the <c>vrc-patterns/debug-shaders</c> family — every shader that
    /// carries the crystal shell pass. Owns the section chrome, the property-drift checks in both
    /// directions, the shell/rim controls, and the toolbar+keyword handling a <c>[KeywordEnum]</c> mode
    /// property needs. Each shader's own controls live in its subclass.
    ///
    /// <para><b>Building blocks, not a template method.</b> Subclasses write their own <c>OnGUI</c> and call
    /// the pieces they need, because the three shaders genuinely disagree on order: the display puts a
    /// diagnostic summary above everything and its twelve entries between the shell and the advanced fold,
    /// while the other two are a flat stack. A base <c>OnGUI</c> with enough hooks to express that would be
    /// harder to read than three explicit ones.</para>
    ///
    /// <para><b>Layout borrows lilToon's shape, not its code.</b> The header bar, the boxed body, and a
    /// collapsed row that still shows its own key control are patterns from <c>lilEditorGUI.Foldout</c> /
    /// <c>DrawSimpleFoldout</c>, reimplemented here against built-in styles: referencing
    /// <c>jp.lilxyzw.liltoon</c> to draw a foldout would put a shader package in the dependency graph of
    /// entries whose only dependency is an MA <c>BoneProxy</c>.</para>
    /// </summary>
    public abstract class CrystalShellShaderGUI : ShaderGUI
    {
        // ── The shared property surface ──────────────────────────────────────────────────────────────

        /// <summary>
        /// The two screenspace-overlay toggles. The fullscreen path keys off <c>SV_VertexID</c> 0-3, so it
        /// needs a mesh whose first two triangles are drawn from those four vertices — a cube or a quad.
        /// The reorder toggle permutes which corner each id lands on; on a mesh that never draws a second
        /// triangle from ids 0-3 it can only move the covered half, not complete it, which is why the
        /// subclass warns rather than offering it as a repair.
        /// </summary>
        protected static readonly string[] OverlayProps =
            { "_Overlay_Fullscreen", "_Overlay_Screenspace_Vertex_Reorder" };

        protected static readonly string[] ShellToggleProps = { "_Shell_Enabled" };

        protected static readonly string[] ShellProps =
            { "_Shell_ReflectionCube", "_Shell_Reflection_Color", "_Shell_Reflection_Strength",
              "_Shell_Reflection_Smoothness", "_Shell_Reflection_BlurMaxMip" };

        protected static readonly string[] RimProps =
            { "_Shell_Rim_Color", "_Shell_Rim_Strength", "_Shell_Rim_Border", "_Shell_Rim_Blur",
              "_Shell_Rim_FresnelPower", "_Shell_Rim_VRParallaxStrength" };

        // Fold state is static, not per-instance: Unity builds a fresh ShaderGUI on every selection change,
        // so instance fields collapse every section each time you click away and back. Static survives
        // everything short of a domain reload, which is enough for a view preference — and sharing it across
        // the family is the behaviour an operator wants when comparing two of these materials.
        protected static bool _showShell;
        protected static bool _showRendering;

        static GUIStyle _headerStyle;

        // ── Mode property (a [KeywordEnum] drawn as a toolbar) ───────────────────────────────────────

        /// <summary>
        /// The shader's <c>[KeywordEnum]</c> mode property, or <c>null</c> where it has none. A shader that
        /// declares one must also declare <see cref="ModeNames"/> and <see cref="ModeKeywords"/> in the
        /// order the enum does — the float value <i>is</i> the index, so that order is a wire contract
        /// written into authored materials, not a presentation choice.
        /// </summary>
        protected virtual string ModeProperty { get { return null; } }
        protected virtual string ModeLabel { get { return "Mode"; } }
        protected virtual string[] ModeNames { get { return null; } }
        protected virtual string[] ModeKeywords { get { return null; } }

        /// <summary>
        /// The mode as a button bar at the top of the inspector, where lilToon puts its editor-mode row.
        /// A handful of mutually exclusive modes read as buttons; as a popup they read as a list to open.
        /// No-op on a shader with no mode property.
        /// </summary>
        protected void DrawModeBar(Material mat)
        {
            string prop = ModeProperty;
            if (prop == null) return;

            EditorGUILayout.LabelField(ModeLabel, EditorStyles.boldLabel);

            // Guarded like every hand-drawn control here: skipping DrawNamed means skipping its
            // shader-lacks-this-property error box, so each one raises its own.
            if (!mat.HasProperty(prop))
            {
                EditorGUILayout.HelpBox("shader has no property '" + prop + "' — inspector and shader " +
                                        "have drifted", MessageType.Error);
                return;
            }

            int cur = Mathf.Clamp(Mathf.RoundToInt(GetFloat(mat, prop, 0f)), 0, ModeNames.Length - 1);
            DrawModeKeywordMismatch(mat, cur);

            EditorGUI.BeginChangeCheck();
            int next = GUILayout.Toolbar(cur, ModeNames, GUILayout.Height(22f));
            // Written even when next == cur: re-picking the shown mode is how an operator repairs a
            // mismatch without reaching for the Fix button, and a no-op guard would make that click do
            // nothing on exactly the material that needs it.
            if (EditorGUI.EndChangeCheck()) WriteMode(mat, next);
            EditorGUILayout.Space();
        }

        /// <summary>
        /// Reports a material whose mode float and mode keyword disagree, and offers to repair it. The float
        /// is what the bar reads, the keyword is what the shader branches on, so a mismatch renders one mode
        /// while the bar shows another — the exact silent wrongness this inspector exists to refuse.
        ///
        /// <para>The bar's own write keeps the two in step, so this is about materials that arrive already
        /// split: <c>new Material(shader)</c> enables no keyword at all, so a scripted
        /// <c>SetFloat(mode, 2)</c> leaves the first variant in force while the float says otherwise.
        /// Pasted material properties and applied presets can do the same. Detected, never repaired behind
        /// the operator's back: a write during <c>OnGUI</c> would dirty a material just for being looked
        /// at.</para>
        /// </summary>
        void DrawModeKeywordMismatch(Material mat, int cur)
        {
            var keywords = ModeKeywords;
            var names = ModeNames;

            int enabled = -1, enabledCount = 0;
            for (int k = 0; k < keywords.Length; k++)
                if (mat.IsKeywordEnabled(keywords[k])) { enabled = k; enabledCount++; }

            // Exactly one keyword, matching the float, is the only correct state.
            if (enabledCount == 1 && enabled == cur) return;

            string keywordSays = enabledCount == 0
                ? "no mode keyword is enabled, so the shader falls back to " + names[0]
                : enabledCount > 1
                    ? enabledCount + " mode keywords are enabled at once"
                    : "the keyword says " + names[enabled];

            EditorGUILayout.HelpBox(
                ModeLabel + " is inconsistent: the float says " + names[cur] + " but " + keywordSays +
                ". The shader branches on the keyword, so what renders is not what this bar shows. " +
                "Re-pick the mode below, or press Fix.", MessageType.Error);

            if (GUILayout.Button("Fix — set the keyword to " + names[cur]))
                WriteMode(mat, cur);
        }

        /// <summary>
        /// The float and the keywords, written together. <c>[KeywordEnum]</c> is what normally keeps them in
        /// step and only <see cref="MaterialEditor.ShaderProperty"/> honours it, so every hand-drawn path
        /// has to come through here.
        /// </summary>
        protected void WriteMode(Material mat, int mode)
        {
            var keywords = ModeKeywords;
            Undo.RecordObject(mat, "Change " + ModeLabel.ToLowerInvariant());
            mat.SetFloat(ModeProperty, mode);
            for (int k = 0; k < keywords.Length; k++)
            {
                if (k == mode) mat.EnableKeyword(keywords[k]);
                else mat.DisableKeyword(keywords[k]);
            }
            EditorUtility.SetDirty(mat);
        }

        /// <summary>
        /// Refuses a multi-material selection, the way the display inspector already does. Everything below
        /// reads and writes a single <c>Material</c>: <see cref="DrawModeBar"/> writes the float and keywords
        /// to one target while <see cref="MaterialEditor.ShaderProperty"/> still writes every selected
        /// material, so picking a mode across a selection leaves the others on the old keyword — and
        /// <see cref="DrawModeKeywordMismatch"/> only ever inspects the first, so it cannot report the split
        /// it exists to catch. The section gates (<c>_Shell_Enabled</c>, the effect toggles) read the first
        /// material too, hiding rows the rest still need.
        ///
        /// <para>Returns true when the caller should fall back to <c>base.OnGUI</c>.</para>
        /// </summary>
        protected static bool RefuseMultiSelect(MaterialEditor editor, string hidden)
        {
            if (editor.targets == null || editor.targets.Length <= 1) return false;
            EditorGUILayout.HelpBox(
                "Editing " + editor.targets.Length + " materials at once. " + hidden + " is hidden because " +
                "the mode bar writes its keyword to one material at a time, which would leave the rest " +
                "showing a mode they are not rendering. Edit them one at a time.", MessageType.Info);
            return true;
        }

        // ── Shared sections ─────────────────────────────────────────────────────────────────────────

        /// <summary>
        /// The screenspace-overlay toggles, drawn only where the shader declares them — unlike
        /// <see cref="DrawNamed"/>, absence here is legitimate rather than drift, since the shell family
        /// does not all carry a fullscreen path.
        /// </summary>
        protected void DrawOverlaySection(MaterialEditor editor, MaterialProperty[] properties, Material mat)
        {
            if (!mat.HasProperty(OverlayProps[0])) return;
            DrawNamed(editor, properties, OverlayProps);
        }

        /// <summary>
        /// The shell and the rim light. The rim lives in the same pass behind the same <c>_SHELL_ON</c>
        /// keyword, so with the shell off neither group does anything: nesting says that, where two sibling
        /// sections implied the rim was independently live.
        /// </summary>
        protected void DrawShellSection(MaterialEditor editor, MaterialProperty[] properties, Material mat)
        {
            if (Section("Crystal shell", "The reflective outer pass, and the rim light inside it",
                        ref _showShell))
                using (Body())
                {
                    DrawNamed(editor, properties, ShellToggleProps);
                    if (GetFloat(mat, "_Shell_Enabled", 1f) != 0f)
                    {
                        DrawNamed(editor, properties, ShellProps);
                        Line();
                        EditorGUILayout.LabelField("Rim light", EditorStyles.boldLabel);
                        DrawNamed(editor, properties, RimProps);
                    }
                }
        }

        protected void DrawRenderingSection(MaterialEditor editor)
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Advanced", EditorStyles.boldLabel);
            if (Section("Rendering", "Unity's own per-material render settings", ref _showRendering))
                using (Body())
                {
                    editor.RenderQueueField();
                    editor.DoubleSidedGIField();
                    editor.EnableInstancingField();
                }
        }

        // ── Drift checks, both directions ────────────────────────────────────────────────────────────

        /// <summary>
        /// Draws the named properties in the order given. A name the shader lacks gets an explicit error box
        /// rather than being silently omitted, so shader/GUI drift is loud — one forgotten control is an
        /// invisible control.
        /// </summary>
        protected void DrawNamed(MaterialEditor editor, MaterialProperty[] properties, string[] names,
                                 string[] labels = null)
        {
            for (int n = 0; n < names.Length; n++)
            {
                var name = names[n];
                var prop = properties.FirstOrDefault(p => p.name == name);
                if (prop == null)
                {
                    EditorGUILayout.HelpBox("shader has no property '" + name +
                                            "' — inspector and shader have drifted", MessageType.Error);
                    continue;
                }
                editor.ShaderProperty(prop, labels != null ? labels[n] : prop.displayName);
            }
        }

        /// <summary>
        /// Every property this inspector is responsible for drawing, declared rather than observed.
        /// Checked against the shader by <see cref="DrawUnclaimed"/>: a collapsed section draws nothing, so
        /// a coverage check keyed on what actually got drawn would call all of its properties orphans.
        /// A subclass unions its own onto this.
        /// </summary>
        protected virtual IEnumerable<string> ClaimedProperties
        {
            get
            {
                var claimed = OverlayProps.Concat(ShellToggleProps).Concat(ShellProps).Concat(RimProps);
                return ModeProperty != null ? claimed.Concat(new[] { ModeProperty }) : claimed;
            }
        }

        /// <summary>
        /// A property the shader declares that no section claims would be silently unreachable through this
        /// GUI — the same failure <see cref="DrawNamed"/>'s error box catches from the other direction.
        /// <c>[HideInInspector]</c> properties are excluded because being undrawn is what that flag asks
        /// for; a subclass extends <paramref name="alsoExempt"/> for properties it edits through some other
        /// representation.
        /// </summary>
        protected void DrawUnclaimed(MaterialProperty[] properties,
                                     System.Func<string, bool> alsoExempt = null)
        {
            var claimed = new HashSet<string>(ClaimedProperties);
            var orphans = properties
                .Where(p => (p.flags & MaterialProperty.PropFlags.HideInInspector) == 0)
                .Where(p => !claimed.Contains(p.name))
                .Where(p => alsoExempt == null || !alsoExempt(p.name))
                .Select(p => p.name)
                .ToArray();

            if (orphans.Length > 0)
                EditorGUILayout.HelpBox(
                    "The shader declares " + orphans.Length + " property(s) no section of this " +
                    "inspector draws, so they are unreachable here: " + string.Join(", ", orphans) +
                    ". Add them to a section in " + GetType().Name + ".", MessageType.Error);
        }

        // ── Section chrome (our own, shaped after lilEditorGUI) ──────────────────────────────────────

        protected static void EnsureStyles()
        {
            // Built during OnGUI, never in a field initializer: a GUIStyle derived from a named built-in
            // style needs GUI.skin, which does not exist at static-init time.
            if (_headerStyle != null) return;
            _headerStyle = new GUIStyle("ShurikenModuleTitle")
            {
                font = EditorStyles.label.font,
                fontSize = EditorStyles.label.fontSize,
                fontStyle = FontStyle.Bold,
                border = new RectOffset(15, 7, 4, 4),
                contentOffset = new Vector2(20f, -2f),
                fixedHeight = 22
            };
        }

        /// <summary>A full-width header bar whose whole surface toggles the section, as lilToon's is.</summary>
        protected static bool Section(string title, string tooltip, ref bool display)
        {
            var rect = GUILayoutUtility.GetRect(16f, 22f, _headerStyle);
            rect.width += 8f;
            rect.x -= 8f;
            GUI.Box(rect, new GUIContent(title, tooltip), _headerStyle);

            var e = Event.current;
            if (e.type == EventType.Repaint)
                EditorStyles.foldout.Draw(new Rect(rect.x + 4f, rect.y + 3f, 13f, 13f),
                                          false, false, display, false);
            // Left button only. The bar is deliberately 8px wider than the content rect, so swallowing
            // every button would suppress the context menu over a band beyond the section itself.
            if (e.type == EventType.MouseDown && e.button == 0 && rect.Contains(e.mousePosition))
            {
                display = !display;
                e.Use();
            }
            return display;
        }

        protected static EditorGUILayout.VerticalScope Body()
            => new EditorGUILayout.VerticalScope(EditorStyles.helpBox);

        protected static void Line()
            => EditorGUI.DrawRect(EditorGUI.IndentedRect(EditorGUILayout.GetControlRect(false, 1)),
                                  new Color(0.5f, 0.5f, 0.5f, 0.4f));

        protected static float GetFloat(Material mat, string name, float fallback)
            => mat.HasProperty(name) ? mat.GetFloat(name) : fallback;
    }
}
