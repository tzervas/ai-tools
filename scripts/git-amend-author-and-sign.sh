#!/bin/bash

# Script to automate amending commit author and facilitate signing for a series of commits.

set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
NEW_AUTHOR_NAME="Tyler Zervas"
NEW_AUTHOR_EMAIL="tz-dev@vectorwieght.com"
# --- End Configuration ---

# --- Helper Functions ---
print_usage() {
  echo "Usage: $0 <branch-name> <base-branch>"
  echo "  <branch-name>: The local feature branch whose commits you want to amend."
  echo "  <base-branch>: The base branch (e.g., main, develop) against which to find commits."
  echo ""
  echo "This script will start an interactive rebase for the commits on <branch-name>"
  echo "that are not on <base-branch>. For each commit, it will offer to amend the author."
  echo "You will then be prompted to sign the commit if desired."
}

confirm_action() {
  read -r -p "$1 [y/N]: " response
  case "$response" in
    [yY][eE][sS]|[yY])
      return 0 # True
      ;;
    *)
      return 1 # False
      ;;
  esac
}
# --- End Helper Functions ---

# --- Main Script ---
if [ "$#" -ne 2 ]; then
  echo "Error: Incorrect number of arguments."
  print_usage
  exit 1
fi

BRANCH_NAME="$1"
BASE_BRANCH="$2"
FULL_AUTHOR="${NEW_AUTHOR_NAME} <${NEW_AUTHOR_EMAIL}>"

echo "--- Starting Commit Amendment Process ---"
echo "Target Branch: ${BRANCH_NAME}"
echo "Base Branch:   ${BASE_BRANCH}"
echo "New Author:    ${FULL_AUTHOR}"
echo ""

# 1. Validate branches
if ! git rev-parse --verify "$BRANCH_NAME" > /dev/null 2>&1; then
  echo "Error: Branch '${BRANCH_NAME}' does not exist locally."
  exit 1
fi
if ! git rev-parse --verify "$BASE_BRANCH" > /dev/null 2>&1; then
    # Try to fetch if it's a remote branch name
    if git rev-parse --verify "origin/${BASE_BRANCH}" > /dev/null 2>&1; then
        echo "Local branch '${BASE_BRANCH}' not found, but 'origin/${BASE_BRANCH}' exists."
        if confirm_action "Do you want to create local branch '${BASE_BRANCH}' from 'origin/${BASE_BRANCH}'?"; then
            git checkout -b "${BASE_BRANCH}" "origin/${BASE_BRANCH}"
            git checkout "${BRANCH_NAME}" # Switch back
        else
            echo "Aborting. Please ensure '${BASE_BRANCH}' exists locally."
            exit 1
        fi
    else
        echo "Error: Base branch '${BASE_BRANCH}' (and 'origin/${BASE_BRANCH}') does not exist."
        exit 1
    fi
fi


# 2. Ensure the working directory is clean
if ! git diff-index --quiet HEAD --; then
  echo "Error: Your working directory is not clean. Please commit or stash your changes."
  exit 1
fi

# 3. Switch to the target branch (optional, but good for context)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "$BRANCH_NAME" ]; then
  if confirm_action "You are not on branch '${BRANCH_NAME}'. Switch to it now?"; then
    if ! git checkout "$BRANCH_NAME"; then
      echo "Error: Could not switch to branch '${BRANCH_NAME}'."
      exit 1
    fi
  else
    echo "Aborting. Please switch to branch '${BRANCH_NAME}' and rerun the script."
    exit 1
  fi
fi

# 4. Identify commits to rebase
# Use 'git rev-list --reverse <base-branch>..<branch-name>' to get commits in chronological order
COMMIT_RANGE="${BASE_BRANCH}..${BRANCH_NAME}"
COMMIT_COUNT=$(git rev-list --count "$COMMIT_RANGE")

if [ "$COMMIT_COUNT" -eq 0 ]; then
  echo "No commits found on '${BRANCH_NAME}' that are not in '${BASE_BRANCH}'. Nothing to do."
  exit 0
fi

echo "Found ${COMMIT_COUNT} commit(s) on '${BRANCH_NAME}' ahead of '${BASE_BRANCH}' to process."
echo "An interactive rebase will be initiated. For each commit, you should:"
echo "  1. Mark the commit with 'edit' (or 'e')."
echo "  2. When the rebase stops at the commit:"
echo "     a. The script will offer to amend the author automatically."
echo "     b. You will then be prompted to sign the commit (e.g., using 'git commit --amend -S')."
echo "     c. After signing (or if you choose not to), run 'git rebase --continue'."
echo ""
echo "IMPORTANT: If you make a mistake, you can abort with 'git rebase --abort'."
echo "The script will set GIT_SEQUENCE_EDITOR to a helper that marks all commits for 'edit'."
echo ""

if ! confirm_action "Proceed with interactive rebase?"; then
  echo "Aborted by user."
  exit 0
fi

# 5. Perform interactive rebase
# We'll use a temporary script to mark all commits in the rebase for 'edit'
# This is safer than trying to fully automate the rebase loop from outside.
# The user will still need to `git rebase --continue` manually after each step.

export GIT_SEQUENCE_EDITOR="sed -i -e 's/^pick /e /'"
export TARGET_AUTHOR_FOR_AMEND="${FULL_AUTHOR}" # Pass to sub-shell/git environment

# The actual rebase command
# We use `git rebase -i --autostash $BASE_BRANCH`
# The commits are listed oldest first.
if ! git rebase -i --autostash "$BASE_BRANCH"; then
    echo ""
    echo "Error during rebase. The rebase process might have been aborted or failed."
    echo "If the rebase is still in progress (check 'git status'), you might need to resolve conflicts"
    echo "or use 'git rebase --abort' or 'git rebase --continue' manually."
    echo "If aborted, your branch should be in its original state (unless autostash failed to restore)."
    unset GIT_SEQUENCE_EDITOR
    unset TARGET_AUTHOR_FOR_AMEND
    exit 1
fi

unset GIT_SEQUENCE_EDITOR
unset TARGET_AUTHOR_FOR_AMEND

echo ""
echo "--- Interactive Rebase Initiated ---"
echo "The rebase process has started. Please follow the prompts from Git."
echo ""
echo "For each commit marked for 'edit':"
echo "1. Git will stop. Check the current commit details."
echo "2. To amend the author to '${FULL_AUTHOR}', run:"
echo "   git commit --amend --author=\"${FULL_AUTHOR}\" --no-edit"
echo "3. To additionally sign the commit (recommended), run:"
echo "   git commit --amend -S"
echo "   (This will use your configured GPG key. You might be prompted for a passphrase.)"
echo "   Alternatively, if you only changed the author and want to sign that:"
echo "   git commit --amend --author=\"${FULL_AUTHOR}\" -S --no-edit"
echo "4. Once done with amending and/or signing, run:"
echo "   git rebase --continue"
echo ""
echo "If you want to skip amending a specific commit, just run 'git rebase --continue'."
echo "If conflicts occur, resolve them, then 'git add <files>' and 'git rebase --continue'."
echo "To abort the entire rebase: 'git rebase --abort'."
echo ""
echo "--- Script Instructions Complete ---"
echo "The interactive rebase is now under your control."
echo "After the rebase is successfully finished, you will likely need to force-push the branch:"
echo "  git push --force-with-lease origin ${BRANCH_NAME}"
echo ""
echo "Please ensure you verify the changes locally before force-pushing."

exit 0
