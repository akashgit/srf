---
name: workflow-mini-swebench
description: "Run the mini-swebench workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Mini Swebench Workflow

The user wants: **$ARGUMENTS**

## Step: Read Task

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cat /tmp/task-instruction.md > $PROJECT_PATH/.factory/reviews/task.md 2>/dev/null || echo 'No task instruction found' > $PROJECT_PATH/.factory/reviews/task.md
```

## Phase 1: Solver (LLM API)

**Model:** opus | **Provider:** vertex | **Tools:** bash | **Max turns:** 100 | **Timeout:** 7200s

**System prompt:**
You are a helpful assistant that can interact with a computer shell to solve programming tasks.

**Instance prompt:**
<pr_description>
Consider the following PR description:

{instance_context}
</pr_description>

<instructions>
# Task Instructions

## Overview

You're a software engineer interacting continuously with a computer by submitting commands.
You'll be helping implement necessary changes to meet requirements in the PR description.
Your task is specifically to make changes to non-test files in the current directory in order to fix the issue described in the PR description in a way that is general and consistent with the codebase.
<IMPORTANT>This is an interactive process where you will think and issue AT LEAST ONE command, see the result, then think and issue your next command(s).</IMPORTANT>

For each response:

1. Include a THOUGHT section explaining your reasoning and what you're trying to accomplish
2. Provide one or more bash tool calls to execute

## Important Boundaries

- MODIFY: Regular source code files in /testbed (this is the working directory for all your subsequent commands)
- DO NOT MODIFY: Tests, configuration files (pyproject.toml, setup.cfg, etc.)

## Recommended Workflow

1. Analyze the codebase by finding and reading relevant files
2. Create a script to reproduce the issue
3. Edit the source code to resolve the issue
4. Verify your fix works by running your script again
5. Test edge cases to ensure your fix is robust

## Command Execution Rules

You are operating in an environment where

1. You issue at least one command
2. The system executes the command(s) in a subshell
3. You see the result(s)
4. You write your next command(s)

Each response should include:

1. **Reasoning text** where you explain your analysis and plan
2. At least one tool call with your command

**CRITICAL REQUIREMENTS:**

- Your response SHOULD include reasoning text explaining what you're doing
- Your response MUST include AT LEAST ONE bash tool call. You can make MULTIPLE tool calls in a single response when the commands are independent (e.g., searching multiple files, reading different parts of the codebase).
- Directory or environment variable changes are not persistent. Every action is executed in a new subshell.
- However, you can prefix any action with `MY_ENV_VAR=MY_VALUE cd /path/to/working/dir && ...` or write/load environment variables from files

Example of a CORRECT response:
<example_response>
I need to understand the Builder-related code. Let me find relevant files and check the project structure.

[Makes multiple bash tool calls: {"command": "ls -la"}, {"command": "find src -name '*.java' | grep -i builder"}, {"command": "cat README.md | head -50"}]
</example_response>

## Environment Details

- You have a full Linux shell environment
- Always use non-interactive flags (-y, -f) for commands
- Avoid interactive tools like vi, nano, or any that require user input
- You can use bash commands or invoke any tool that is available in the environment
- You can also create new tools or scripts to help you with the task
- If a tool isn't available, you can also install it

## Submission

When you've completed your work, commit your changes directly on the current branch.
Follow these steps IN ORDER, with SEPARATE commands:

Step 1: Stage only the source files you modified
Run `git add path/to/file1 path/to/file2` listing only the source files you modified.

<IMPORTANT>
Only stage the specific source files you modified to fix the issue.
Do not stage any of the following files:

- test and reproduction files
- helper scripts, tests, or tools that you created
- installation, build, packaging, configuration, or setup scripts unless they are directly part of the issue you were fixing
- binary or compiled files
</IMPORTANT>

Step 2: Verify your staged changes
Run `git diff --cached` to confirm only your intended changes are staged.

Step 3: Commit with a descriptive message
Run `git commit -m "Fix: <brief description of the fix>"`.

<CRITICAL>
- Do NOT create branches or PRs — commit directly on the current branch.
- Clean up any temporary test or reproduction scripts before committing — do NOT leave them in the repo.
- You CANNOT continue working after committing.
</CRITICAL>
</instructions>

**Reads:** .factory/reviews/task.md
**Writes:** .factory/reviews/builder-latest.md

### Gate — Verify (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
cd $PROJECT_PATH && CHANGES=$(git diff HEAD~1 --stat 2>/dev/null || echo 'NO_COMMITS') && if [ "$CHANGES" = 'NO_COMMITS' ] || [ -z "$CHANGES" ]; then echo 'fail: solver did not commit any changes'; exit 0; fi && BUILDER_OUTPUT=$(cat .factory/reviews/builder-latest.md 2>/dev/null || echo '') && if echo "$BUILDER_OUTPUT" | grep -qiE 'tests?.*(pass|succeed|ok|PASSED)'; then echo 'pass: solver reports tests passing'; elif echo "$BUILDER_OUTPUT" | grep -qiE 'tests?.*(fail|error|FAILED)'; then echo 'reloop: solver needs to retry — tests did not pass'; else echo 'pass: changes committed, no issues detected'; fi
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `auto_merge`
- **RELOOP** (exit non-zero / FAIL in output) → return to `solver` for the next iteration.

*On RELOOP: return to `solver` (max 3 iterations)*

## Step: Auto Merge

```bash
cd $PROJECT_PATH && CURRENT=$(git rev-parse --abbrev-ref HEAD) && COMMON=$(git rev-parse --git-common-dir) && BASE=$(git --git-dir="$COMMON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main) && if [ "$CURRENT" = "$BASE" ]; then echo "Already on $BASE — no merge needed"; exit 0; fi && git update-ref refs/heads/"$BASE" HEAD && PARENT_WT=$(cd "$COMMON/.." && pwd) && git diff-tree --no-commit-id --name-only -r HEAD HEAD~1 | while read file; do if [ -f "$file" ]; then mkdir -p "$PARENT_WT/$(dirname $file)" && cp "$file" "$PARENT_WT/$file"; fi; done && echo "Updated $BASE to $(git rev-parse --short HEAD)"
```
