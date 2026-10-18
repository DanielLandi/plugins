# slide2video.com has moved to the slide2video plugin

slide2video.com now works with a different plugin, `slide2video`, and no longer accepts `lesson-videos` (this
plugin). To keep using the website, install the new plugin in Claude Code:

```
/plugin marketplace add slide2video/slide2video-plugin
/plugin install slide2video@slide2video
```

Then close and reopen Claude Code and run `/slide2video:setup`. It sets up the computer that makes the videos; after
that, `/slide2video:serve` starts it.

## Making videos without the website

Making videos on your own computer with `lesson-videos` keeps working: follow [Install with Claude Code](claude-code.md)
or [Cowork](cowork.md), then run `/lesson-videos:make` in the folder that holds your slide deck.

The commands `pair` and `worker`, and the skill `/lesson-videos:serve`, no longer connect to the website: they only
print how to switch.
