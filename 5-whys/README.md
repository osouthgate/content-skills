# 5-whys

A short Five Whys pass: state the problem, follow evidenced causes, and separate
a root cause from a contributing factor.

Five Whys is one root-cause technique, not a full investigation. A safety event,
an accident, or a system with many independent defenses needs a broader
root-cause analysis than this skill performs.

Adapted from [awesome-skills/5-whys-skill](https://github.com/awesome-skills/5-whys-skill)
(MIT). See [NOTICE.md](NOTICE.md).

```text
/5-whys the checkout API started returning 500s at 14:10
```

## Install

### Claude Code

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install 5-whys@content-skills
```

### Cursor / Codex / other hosts

```bash
ln -s /path/to/content-skills/5-whys/skills/5-whys \
  ~/.cursor/skills/5-whys
```
