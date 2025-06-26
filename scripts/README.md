# Utility Scripts

This directory contains utility scripts for the MCP Tools project.

## `git-amend-author-and-sign.sh`

A utility script to help amend the author of a series of commits on a branch and prepare them for GPG signing. This is useful for ensuring commits adhere to specific authorship requirements and are properly signed, especially when changes might have been initially made by an AI agent or under a different Git configuration.

### Purpose

1.  **Standardize Commit Author:** Change the author of specified commits to a designated name and email (hardcoded in the script as "Tyler Zervas <tz-dev@vectorwieght.com>").
2.  **Facilitate GPG Signing:** Guide the user through an interactive rebase to sign each amended commit individually with their GPG key.

### Prerequisites

*   `git` installed and configured.
*   A GPG key configured with Git for signing commits. See [GitHub's guide on signing commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).
*   The script should be run from the root of the repository.

### Usage

```bash
./scripts/git-amend-author-and-sign.sh <branch-name> <base-branch>
```

*   `<branch-name>`: The local feature branch whose commits you want to amend and sign.
*   `<base-branch>`: The base branch (e.g., `main`, `develop`) against which to find the commits to process. The script will identify commits on `<branch-name>` that are not on `<base-branch>`.

**Example:**
If you have a branch named `feature/new-tool` that was based off `main`:
```bash
chmod +x scripts/git-amend-author-and-sign.sh # Make it executable first
./scripts/git-amend-author-and-sign.sh feature/new-tool main
```

### Workflow

1.  **Validation:** The script checks if the specified branches exist locally and if the working directory is clean. It also ensures you are on the target `<branch-name>`.
2.  **Confirmation:** It asks for user confirmation before starting the interactive rebase.
3.  **Interactive Rebase Setup:**
    *   The script initiates an interactive rebase (`git rebase -i <base-branch>`).
    *   It automatically sets the `GIT_SEQUENCE_EDITOR` environment variable to a `sed` command. This command modifies the rebase instruction sheet to change all `pick` operations to `edit` (or `e`) for the commits in the rebase range. This ensures the rebase will stop at each commit.
4.  **User Actions During Rebase (Guided by Script Output):**
    *   When Git stops at each commit marked for `edit`, the script (before starting the rebase) will have printed instructions. You need to follow these manually for each commit:
        *   **Amend Author:** Run the command `git commit --amend --author="Tyler Zervas <tz-dev@vectorwieght.com>" --no-edit`. The script will display the exact author string to use.
        *   **Sign Commit:** After amending the author (or if you only want to sign without re-amending author), run `git commit --amend -S`. This will use your configured GPG key and may prompt for a passphrase.
            *   To combine author amendment and signing: `git commit --amend --author="Tyler Zervas <tz-dev@vectorwieght.com>" -S --no-edit`.
        *   **Continue Rebase:** After you are done with a commit, run `git rebase --continue` to proceed to the next one.
    *   Repeat these steps for every commit in the rebase.
5.  **Completion:**
    *   Once the rebase is successfully completed, all processed commits on `<branch-name>` will have the new author and will be GPG-signed.
    *   The script reminds the user that a force-push (preferably `--force-with-lease`) will be necessary to update the remote branch: `git push --force-with-lease origin <branch-name>`.
    *   **Important:** Always verify your local changes thoroughly (`git log`, `git show <commit-sha>`) before force-pushing.

### Important Notes

*   **Conflicts:** If any merge conflicts occur during the rebase, you will need to resolve them manually, then use `git add <resolved-files>` and `git rebase --continue`.
*   **Aborting:** To abort the entire rebase process at any time, use `git rebase --abort`. This will try to return your branch to its state before the rebase began.
*   **Hardcoded Author:** The target author name and email are currently hardcoded within the script. You can modify these variables at the top of the script if needed.
*   **`--autostash`:** The rebase command uses `--autostash` to automatically stash any local uncommitted changes before starting and reapply them after.
*   **`GIT_SEQUENCE_EDITOR`:** This script temporarily exports `GIT_SEQUENCE_EDITOR`. This environment variable tells Git what editor to use for editing sequences like the rebase todo list. By setting it to a `sed` command, it automates the `pick` to `edit` change.
```
