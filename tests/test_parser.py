import pytest

from skillbridge.parser import (
    SkillParseError,
    detect_human_only_fields,
    parse_skill_folder,
)


def test_parse_valid_skill(fixture_skill):
    skill = parse_skill_folder(fixture_skill("pkm-processor"))
    assert skill.name == "pkm-processor"
    assert "Classify and file inbox notes" in skill.description
    assert "## Method" in skill.body
    assert skill.human_only_fields == ["IMPLICATION FOR PORTFOLIO"]


def test_parse_lists_scripts_without_executing(fixture_skill):
    skill = parse_skill_folder(fixture_skill("deck-studio"))
    assert skill.subfolders["scripts"] == ["build_deck.py"]


def test_missing_skill_md(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(SkillParseError, match="No SKILL.md"):
        parse_skill_folder(tmp_path / "empty")


def test_missing_frontmatter(tmp_path):
    d = tmp_path / "nofm"
    d.mkdir()
    (d / "SKILL.md").write_text("# Just a heading, no frontmatter\n")
    with pytest.raises(SkillParseError, match="header block"):
        parse_skill_folder(d)


def test_malformed_frontmatter(tmp_path):
    d = tmp_path / "badfm"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: [unclosed\n---\nbody\n")
    with pytest.raises(SkillParseError, match="malformed"):
        parse_skill_folder(d)


def test_frontmatter_without_name(tmp_path):
    d = tmp_path / "noname"
    d.mkdir()
    (d / "SKILL.md").write_text("---\ndescription: nameless\n---\nbody\n")
    with pytest.raises(SkillParseError, match="name"):
        parse_skill_folder(d)


def test_skill_md_one_level_down(tmp_path, fixture_skill):
    # A zip of a folder often extracts to <root>/<skillname>/SKILL.md
    src = fixture_skill("pkm-processor")
    skill = parse_skill_folder(src.parent)
    assert skill.name == "pkm-processor"


def test_detect_human_only_fields():
    assert detect_human_only_fields("...IMPLICATION FOR PORTFOLIO: ...") == [
        "IMPLICATION FOR PORTFOLIO"
    ]
    assert detect_human_only_fields("an Operator Decision is needed") == ["Operator Decision"]
    assert detect_human_only_fields("nothing here") == []
