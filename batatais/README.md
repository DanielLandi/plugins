# Batatais — a scripted Blender reconstruction recipe

A public workflow for reconstructing the Igreja Matriz de Batatais, its gardens
and nearby streets from maps and photographic evidence. See the
[Fable and Astra examples](https://haik.world/models/batatais/about/).

This plugin contains instructions, not the private Blender repository, model
assets or finished generators. Your agent writes a new reconstruction. Blender
and an agent with file/command access are needed to build; Blender MCP is optional.
Installation does not install Blender or any addon, or start a render.

## Claude Code

Install directly from the marketplace URL in your terminal:

```sh
claude plugin install batatais --marketplace https://github.com/DanielLandi/plugins
```

Or, inside Claude Code:

```text
/plugin marketplace add DanielLandi/plugins
/plugin install batatais@daniellandi
```

Then ask: “Use the recreate-batatais-scene skill to build a new Batatais scene.”

## Codex CLI

```sh
codex plugin marketplace add https://github.com/DanielLandi/plugins
codex plugin add batatais@daniellandi
```

Use a current CLI with plugin support. Codex recognizes this repository's Claude
marketplace catalog; the plugin also supplies a portable `plugin.json` manifest.
Restart the agent session if newly installed skills are not yet listed.

## Give another agent the URL

Paste this into an agent with access to public GitHub and local skill installation:

```text
Install the Batatais plugin from https://github.com/DanielLandi/plugins/tree/main/batatais for this CLI. Read its README and SKILL.md, use this CLI's supported plugin or skill installation mechanism, and do not start building the scene yet.
```

This is an agent prompt, not a universal native install command. Agents without a
plugin system can use the self-contained
[SKILL.md](skills/recreate-batatais-scene/SKILL.md) through their supported skill loader.

## Package

- `skills/recreate-batatais-scene/SKILL.md`: self-contained reconstruction workflow.
- `.claude-plugin/plugin.json`: Claude Code manifest.
- `plugin.json`: portable agent-plugin manifest.

Instructions are MIT licensed. Third-party reference imagery and model/rendered
assets are not included and retain their own licenses.
