---
name: serve
description: Use when the teacher asks about slide2video.com, wants this computer to make the videos for lessons they upload there ("start making videos", "serve", "connect to the website"), or asks whether it's working. slide2video.com has moved to the slide2video plugin; this tells them how to switch.
---

# lesson-videos: slide2video.com has moved

You are helping a teacher who may never have used a terminal. Explain in plain words; do not run `LV pair` or
`LV worker` (they only print the message below and stop).

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

If that path doesn't exist (in some claude.ai sessions `${CLAUDE_SKILL_DIR}` comes through empty), the plugin is
under `/root/.claude/plugins/synced/`.

slide2video.com now works with a different plugin, `slide2video`, and no longer accepts lesson-videos. Tell the
teacher, and give them these lines to type in Claude Code:

```
/plugin marketplace add slide2video/slide2video-plugin
/plugin install slide2video@slide2video
```

Then they close and reopen Claude Code and run `/slide2video:setup`. After that, `/slide2video:serve` makes this
computer work on the website's video projects.

Making videos on this computer with lesson-videos keeps working: if they want that, run `/lesson-videos:make` in the
folder that holds their slide deck.
