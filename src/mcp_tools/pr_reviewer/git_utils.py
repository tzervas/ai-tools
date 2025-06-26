import git
from typing import List, Tuple, Optional, Set
import os

class GitRepoError(Exception):
    """Custom exception for Git repository errors."""
    pass

class GitUtils:
    def __init__(self, repo_path: Optional[str] = None):
        """
        Initializes GitUtils.

        Args:
            repo_path: Path to the Git repository. Defaults to the current working directory.

        Raises:
            GitRepoError: If the path is not a valid Git repository.
        """
        try:
            self.repo_path = repo_path or os.getcwd()
            self.repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            raise GitRepoError(f"Not a valid Git repository: {self.repo_path}")
        except Exception as e:
            raise GitRepoError(f"Error initializing Git repository at {self.repo_path}: {e}")

    def get_current_branch_name(self) -> Optional[str]:
        """
        Gets the name of the current active branch.
        Returns None if in a detached HEAD state.
        """
        try:
            return self.repo.active_branch.name
        except TypeError: # Happens in detached HEAD state
            return None
        except Exception as e:
            # Log this or handle more gracefully if needed
            print(f"Warning: Could not determine active branch: {e}")
            return None


    def get_commits_between(self, base_rev: str, head_rev: str) -> List[git.Commit]:
        """
        Gets a list of commits between base_rev and head_rev (exclusive of base_rev, inclusive of head_rev).
        Commits are returned in chronological order (oldest first).

        Args:
            base_rev: The base revision (e.g., 'main', commit SHA).
            head_rev: The head revision (e.g., 'feature/my-branch', commit SHA, 'HEAD').

        Returns:
            A list of git.Commit objects.

        Raises:
            GitRepoError: If revisions are invalid or other Git errors occur.
        """
        try:
            base_commit = self.repo.commit(base_rev)
            head_commit = self.repo.commit(head_rev)

            # Construct the range: base_commit..head_commit
            # rev_list returns in reverse chronological order by default.
            # We use --reverse to get chronological.
            commit_range = f"{base_commit.hexsha}..{head_commit.hexsha}"
            commits = list(self.repo.iter_commits(rev=commit_range, reverse=True))
            return commits
        except git.GitCommandError as e:
            raise GitRepoError(f"Error getting commits between '{base_rev}' and '{head_rev}': {e}")
        except Exception as e: # Catch other potential errors like bad revision names
            raise GitRepoError(f"Invalid revision or error in get_commits_between ('{base_rev}', '{head_rev}'): {e}")

    def get_commit_details(self, commit: git.Commit) -> dict:
        """
        Extracts relevant details from a git.Commit object.
        """
        return {
            "sha": commit.hexsha,
            "message_subject": commit.summary, # First line of message
            "message_body": commit.message.replace(commit.summary, "", 1).lstrip(), # Rest of the message
            "author_name": commit.author.name,
            "author_email": commit.author.email,
            "authored_date": commit.authored_datetime,
            "committer_name": commit.committer.name,
            "committer_email": commit.committer.email,
            "committed_date": commit.committed_datetime,
        }

    def get_changed_files_in_commit(self, commit_sha: str) -> List[str]:
        """
        Gets a list of files changed in a specific commit.
        This includes added, modified, deleted, renamed files.
        """
        try:
            commit = self.repo.commit(commit_sha)
            # Handle initial commit (no parents)
            if not commit.parents:
                return [item.a_path for item in commit.tree.diff(None)]

            # For regular commits, diff against the first parent
            # The diff shows changes from parent to commit.
            # item.a_path is usually the path before change (for delete/rename)
            # item.b_path is usually the path after change (for add/rename/modify)
            # We generally care about the path as it exists in the commit.
            changed_files = []
            for diff_item in commit.parents[0].diff(commit):
                if diff_item.a_path: # Path in parent
                    changed_files.append(diff_item.a_path)
                if diff_item.b_path and diff_item.b_path != diff_item.a_path: # Path in commit, if different
                    changed_files.append(diff_item.b_path)
            # Remove duplicates if a_path and b_path were added for some reason (e.g. type change)
            return list(set(changed_files))

        except git.GitCommandError as e:
            raise GitRepoError(f"Error getting changed files for commit '{commit_sha}': {e}")
        except Exception as e:
            raise GitRepoError(f"Invalid commit SHA or error in get_changed_files_in_commit ('{commit_sha}'): {e}")

    def get_all_changed_files_in_range(self, base_rev: str, head_rev: str) -> Set[str]:
        """
        Gets a set of all unique file paths that were changed between base_rev and head_rev.
        """
        commits = self.get_commits_between(base_rev, head_rev)
        all_files: Set[str] = set()
        for commit in commits:
            # Diff commit against its first parent.
            # For merge commits, this diffs against the first parent, which is standard.
            # For the initial commit, diff against an empty tree.
            parent_tree = commit.parents[0].tree if commit.parents else self.repo.tree() # Empty tree for initial commit

            diffs = parent_tree.diff(commit.tree)
            for diff_item in diffs:
                # diff_item.a_path is the old path (None if new file)
                # diff_item.b_path is the new path (None if deleted file)
                if diff_item.b_path: # File exists in the "after" state (added, modified, renamed to)
                    all_files.add(diff_item.b_path)
                elif diff_item.a_path: # File existed in "before" state and was deleted/renamed from
                    all_files.add(diff_item.a_path) # Track deleted files too for some checks
        return all_files

    def get_file_content_at_revision(self, filepath: str, revision: str = 'HEAD') -> Optional[str]:
        """
        Gets the content of a file at a specific revision.
        Returns None if the file does not exist at that revision or is binary.
        """
        try:
            commit = self.repo.commit(revision)
            blob = commit.tree / filepath
            # Check if blob is binary before decoding.
            # GitPython's blob.data_stream is a file-like object for reading bytes.
            # A simple heuristic: check for null bytes in the first KB.
            # More robust binary detection is complex.
            with blob.data_stream as stream:
                initial_chunk = stream.read(1024)
                if b'\0' in initial_chunk:
                    # print(f"Warning: File '{filepath}' at revision '{revision}' appears to be binary. Skipping content read.", file=sys.stderr)
                    return None # Or raise an error, or return bytes
                # Reset stream and read full content if not binary
                stream.seek(0)
                content_bytes = stream.read()
            return content_bytes.decode('utf-8') # Assume utf-8
        except KeyError: # File not found in tree
            return None
        except UnicodeDecodeError:
            # print(f"Warning: Could not decode file '{filepath}' at revision '{revision}' as UTF-8.", file=sys.stderr)
            return None # Or return bytes
        except Exception as e:
            raise GitRepoError(f"Error getting content for file '{filepath}' at revision '{revision}': {e}")

    def get_file_size_at_revision(self, filepath: str, revision: str = 'HEAD') -> Optional[int]:
        """
        Gets the size of a file (in bytes) at a specific revision.
        Returns None if the file does not exist at that revision.
        """
        try:
            commit = self.repo.commit(revision)
            blob = commit.tree / filepath
            return blob.size
        except KeyError: # File not found
            return None
        except Exception as e:
            raise GitRepoError(f"Error getting size for file '{filepath}' at revision '{revision}': {e}")

if __name__ == '__main__':
    # Example Usage (assumes running from within a git repository)
    try:
        print(f"Initializing GitUtils for current directory: {os.getcwd()}")
        utils = GitUtils() # Uses current directory

        print("\n--- Current Branch ---")
        current_branch = utils.get_current_branch_name()
        print(f"Current branch: {current_branch}")

        if current_branch and current_branch != "main" and current_branch != "master":
            # Attempt to get commits between 'main' (or common base) and current branch
            # This part is tricky for a generic example, as 'main' might not exist or be the right base.
            # For testing, you'd typically have a known repo structure.
            # Here, we try to find a common ancestor with a remote main or develop if they exist.

            potential_bases = []
            for remote_ref_name in ["origin/main", "origin/develop", "main", "develop"]:
                try:
                    if utils.repo.commit(remote_ref_name):
                        potential_bases.append(remote_ref_name)
                        break # Found one
                except:
                    pass

            base_branch_for_test = None
            if potential_bases:
                base_branch_for_test = potential_bases[0]
                print(f"\n--- Commits between '{base_branch_for_test}' and '{current_branch}' ---")
                commits = utils.get_commits_between(base_branch_for_test, 'HEAD') # 'HEAD' or current_branch
                if commits:
                    for i, commit in enumerate(commits):
                        details = utils.get_commit_details(commit)
                        print(f"  Commit {i+1}: {details['sha'][:7]} - {details['message_subject']}")
                        # changed_files_in_commit = utils.get_changed_files_in_commit(commit.hexsha)
                        # print(f"    Files: {changed_files_in_commit[:3]}...") # Print first 3

                    print("\n--- All changed files in range ---")
                    all_changed = utils.get_all_changed_files_in_range(base_branch_for_test, 'HEAD')
                    print(f"Total unique files changed: {len(all_changed)}")
                    for f_path in list(all_changed)[:3]: # Print first 3
                        print(f"  - {f_path}")
                        content = utils.get_file_content_at_revision(f_path, 'HEAD')
                        size = utils.get_file_size_at_revision(f_path, 'HEAD')
                        # print(f"    Content (HEAD, first 50 chars): '{content[:50].replace('\\n', ' ')}...' " if content else "    Content: Not available/binary")
                        print(f"    Size (HEAD): {size} bytes" if size is not None else "    Size: Not found")

                else:
                    print(f"No commits found between '{base_branch_for_test}' and '{current_branch}'.")
            else:
                print("Could not determine a base branch (like main/develop) for testing commit ranges.")

        else:
            print("Skipping commit range tests (current branch is main/master or detached).")
            # Test getting content of a known file, e.g., README.md
            readme_content = utils.get_file_content_at_revision("README.md")
            if readme_content:
                print("\n--- README.md (HEAD) ---")
                print(readme_content[:200] + "...")
            else:
                print("\nREADME.md not found or is binary/unreadable.")


    except GitRepoError as e:
        print(f"GitRepoError: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
