using NUnit.Framework;
using Ryan6Vrc.Patterns.DebugShaders.Editor;
using UnityEngine;

// The whole test surface for debug-shaders, deliberately.
//
// Only two things here can break silently: a label or a format that packs one way and unpacks another
// reads as a plausible wrong value in-world rather than as an error, and the shader's HLSL mirrors this
// arithmetic, so a change on one side that is not made on the other is invisible until someone looks at
// a display. Everything else about these shaders fails loudly or is visible on screen, and is not worth
// a fixture.
public class DisplayGlyphsTests
{
    [Test]
    public void Label_Round_Trips_Through_The_Packed_Vector()
    {
        Assert.IsTrue(DisplayGlyphs.TryEncodeLabel("POS X:", out var packed, out var error, out _), error);
        Assert.AreEqual("POS X:", DisplayGlyphs.DecodeLabel(packed));
    }

    [Test]
    public void Label_Fills_Every_Slot_Without_Losing_A_Char()
    {
        // 12 chars is the ceiling, and the last component is the one a too-small type would drop.
        var full = "ABCDEFGHIJKL";
        Assert.IsTrue(DisplayGlyphs.TryEncodeLabel(full, out var packed, out var error, out _), error);
        Assert.AreEqual(full, DisplayGlyphs.DecodeLabel(packed));
    }

    [Test]
    public void Packed_Component_Stays_Inside_The_G7_Safe_Ceiling()
    {
        // Material properties survive the toolchain as float.ToString() "G7" text, so a component above
        // 7 significant digits re-parses to a different number and every char packed in it changes.
        Assert.IsTrue(DisplayGlyphs.TryEncodeLabel("ABCDEFGHIJKL", out var packed, out _, out _));
        foreach (var c in new[] { packed.x, packed.y, packed.z, packed.w })
            Assert.LessOrEqual(c, DisplayGlyphs.MaxComponent, "component exceeds the G7-safe ceiling");
    }

    [Test]
    public void Label_Outside_The_Charset_Is_Refused_By_Name()
    {
        // Lowercase is uppercased BEFORE the charset check (the charset is uppercase-only), so the
        // refusal names the uppercased form: é goes in, É comes back. Asserting the lowercase form
        // is the mistake to avoid here.
        Assert.IsFalse(DisplayGlyphs.TryEncodeLabel("héllo", out _, out var error, out _));
        StringAssert.Contains("É", error, "the refusal names the offending character");
        StringAssert.Contains("index 1", error, "and where it is");
    }

    [Test]
    public void Format_Round_Trips_Through_The_Bitfield()
    {
        Assert.IsTrue(DisplayGlyphs.TryPackFormat(3, 2, 7, DisplayGlyphs.ValueSource.WorldY,
                                                  out var packed, out var error), error);
        DisplayGlyphs.UnpackFormat(packed, out var decimals, out var palette,
                                   out var rpad, out var source);
        Assert.AreEqual(3, decimals);
        Assert.AreEqual(2, palette);
        Assert.AreEqual(7, rpad);
        Assert.AreEqual(DisplayGlyphs.ValueSource.WorldY, source);
    }

    [Test]
    public void Charset_Slots_The_Shader_Indexes_By_Name_Are_Where_It_Expects()
    {
        // The HLSL reaches these by ordinal, so a reordered charset silently redraws every glyph.
        Assert.AreEqual('+', DisplayGlyphs.Charset[DisplayGlyphs.Plus]);
        Assert.AreEqual('-', DisplayGlyphs.Charset[DisplayGlyphs.Minus]);
        Assert.AreEqual('.', DisplayGlyphs.Charset[DisplayGlyphs.Dot]);
        Assert.AreEqual('0', DisplayGlyphs.Charset[DisplayGlyphs.Zero]);
        Assert.AreEqual(':', DisplayGlyphs.Charset[DisplayGlyphs.Colon]);
        Assert.AreEqual('A', DisplayGlyphs.Charset[DisplayGlyphs.LetterA]);
    }
}
