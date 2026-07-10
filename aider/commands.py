import glob
import os
import re
import subprocess
import sys
import tempfile
from collections import OrderedDict
from os.path import expanduser
from pathlib import Path

import pyperclip
from PIL import Image, ImageGrab
from prompt_toolkit.completion import Completion, PathCompleter
from prompt_toolkit.document import Document

from aider import models, prompts, voice
from aider.editor import pipe_editor
from aider.format_settings import format_settings
from aider.help import Help, install_help_extra
from aider.io import CommandCompletionException
from aider.llm import litellm
from aider.repo import ANY_GIT_ERROR
from aider.run_cmd import run_cmd
from aider.scrape import Scraper, install_playwright
from aider.utils import is_image_file

from .dump import dump  # noqa: F401


class SwitchCoder(Exception):
    def __init__(self, placeholder=None, **kwargs):
        self.kwargs = kwargs
        self.placeholder = placeholder


class Commands:
    voice = None
    scraper = None

    def clone(self):
        return Commands(
            self.io,
            None,
            voice_language=self.voice_language,
            verify_ssl=self.verify_ssl,
            args=self.args,
            parser=self.parser,
            verbose=self.verbose,
            editor=self.editor,
            original_read_only_fnames=self.original_read_only_fnames,
        )

    def __init__(
        self,
        io,
        coder,
        voice_language=None,
        voice_input_device=None,
        voice_format=None,
        verify_ssl=True,
        args=None,
        parser=None,
        verbose=False,
        editor=None,
        original_read_only_fnames=None,
    ):
        self.io = io
        self.coder = coder
        self.parser = parser
        self.args = args
        self.verbose = verbose

        self.verify_ssl = verify_ssl
        if voice_language == "auto":
            voice_language = None

        self.voice_language = voice_language
        self.voice_format = voice_format
        self.voice_input_device = voice_input_device

        self.help = None
        self.editor = editor
        # Store the original read-only filenames provided via args.read
        self.original_read_only_fnames = set(original_read_only_fnames or [])

    def cmd_model(self, args):
        "Switch the Main Model to a new LLM"

        model_name = args.strip()
        if not model_name:
            announcements = "\n".join(self.coder.get_announcements())
            self.io.tool_output(announcements)
            return

        model = models.Model(
            model_name,
            editor_model=self.coder.main_model.editor_model.name,
            weak_model=self.coder.main_model.weak_model.name,
        )
        models.sanity_check_models(self.io, model)

        # Check if the current edit format is the default for the old model
        old_model_edit_format = self.coder.main_model.edit_format
        current_edit_format = self.coder.edit_format

        new_edit_format = current_edit_format
        if current_edit_format == old_model_edit_format:
            # If the user was using the old model's default, switch to the new model's default
            new_edit_format = model.edit_format

        raise SwitchCoder(main_model=model, edit_format=new_edit_format)

    def cmd_editor_model(self, args):
        "Switch the Editor Model to a new LLM"

        model_name = args.strip()
        model = models.Model(
            self.coder.main_model.name,
            editor_model=model_name,
            weak_model=self.coder.main_model.weak_model.name,
        )
        models.sanity_check_models(self.io, model)
        raise SwitchCoder(main_model=model)

    def cmd_weak_model(self, args):
        "Switch the Weak Model to a new LLM"

        model_name = args.strip()
        model = models.Model(
            self.coder.main_model.name,
            editor_model=self.coder.main_model.editor_model.name,
            weak_model=model_name,
        )
        models.sanity_check_models(self.io, model)
        raise SwitchCoder(main_model=model)

    def cmd_chat_mode(self, args):
        "Switch to a new chat mode"

        from aider import coders

        ef = args.strip()
        valid_formats = OrderedDict(
            sorted(
                (
                    coder.edit_format,
                    coder.__doc__.strip().split("\n")[0] if coder.__doc__ else "No description",
                )
                for coder in coders.__all__
                if getattr(coder, "edit_format", None)
            )
        )

        show_formats = OrderedDict(
            [
                ("help", "Get help about using aider (usage, config, troubleshoot)."),
                ("ask", "Ask questions about your code without making any changes."),
                ("code", "Ask for changes to your code (using the best edit format)."),
                (
                    "architect",
                    (
                        "Work with an architect model to design code changes, and an editor to make"
                        " them."
                    ),
                ),
                (
                    "context",
                    "Automatically identify which files will need to be edited.",
                ),
            ]
        )

        if ef not in valid_formats and ef not in show_formats:
            if ef:
                self.io.tool_error(f'Chat mode "{ef}" should be one of these:\n')
            else:
                self.io.tool_output("Chat mode should be one of these:\n")

            max_format_length = max(len(format) for format in valid_formats.keys())
            for format, description in show_formats.items():
                self.io.tool_output(f"- {format:<{max_format_length}} : {description}")

            self.io.tool_output("\nOr a valid edit format:\n")
            for format, description in valid_formats.items():
                if format not in show_formats:
                    self.io.tool_output(f"- {format:<{max_format_length}} : {description}")

            return

        summarize_from_coder = True
        edit_format = ef

        if ef == "code":
            edit_format = self.coder.main_model.edit_format
            summarize_from_coder = False
        elif ef == "ask":
            summarize_from_coder = False

        raise SwitchCoder(
            edit_format=edit_format,
            summarize_from_coder=summarize_from_coder,
        )

    def completions_model(self):
        models = litellm.model_cost.keys()
        return models

    def cmd_models(self, args):
        "Search the list of available models"

        args = args.strip()

        if args:
            models.print_matching_models(self.io, args)
        else:
            self.io.tool_output("Please provide a partial model name to search for.")

    def cmd_web(self, args, return_content=False):
        "Scrape a webpage, convert to markdown and send in a message"

        url = args.strip()
        if not url:
            self.io.tool_error("Please provide a URL to scrape.")
            return

        self.io.tool_output(f"Scraping {url}...")
        if not self.scraper:
            disable_playwright = getattr(self.args, "disable_playwright", False)
            if disable_playwright:
                res = False
            else:
                res = install_playwright(self.io)
                if not res:
                    self.io.tool_warning("Unable to initialize playwright.")

            self.scraper = Scraper(
                print_error=self.io.tool_error,
                playwright_available=res,
                verify_ssl=self.verify_ssl,
            )

        content = self.scraper.scrape(url) or ""
        content = f"Here is the content of {url}:\n\n" + content
        if return_content:
            return content

        self.io.tool_output("... added to chat.")

        self.coder.cur_messages += [
            dict(role="user", content=content),
            dict(role="assistant", content="Ok."),
        ]

    def is_command(self, inp):
        return inp[0] in "/!"

    def get_raw_completions(self, cmd):
        assert cmd.startswith("/")
        cmd = cmd[1:]
        cmd = cmd.replace("-", "_")

        raw_completer = getattr(self, f"completions_raw_{cmd}", None)
        return raw_completer

    def get_completions(self, cmd):
        assert cmd.startswith("/")
        cmd = cmd[1:]

        cmd = cmd.replace("-", "_")
        fun = getattr(self, f"completions_{cmd}", None)
        if not fun:
            return
        return sorted(fun())

    def get_commands(self):
        commands = []
        for attr in dir(self):
            if not attr.startswith("cmd_"):
                continue
            cmd = attr[4:]
            cmd = cmd.replace("_", "-")
            commands.append("/" + cmd)

        return commands

    def do_run(self, cmd_name, args):
        cmd_name = cmd_name.replace("-", "_")
        cmd_method_name = f"cmd_{cmd_name}"
        cmd_method = getattr(self, cmd_method_name, None)
        if not cmd_method:
            self.io.tool_output(f"Error: Command {cmd_name} not found.")
            return

        try:
            return cmd_method(args)
        except ANY_GIT_ERROR as err:
            self.io.tool_error(f"Unable to complete {cmd_name}: {err}")

    def matching_commands(self, inp):
        words = inp.strip().split()
        if not words:
            return

        first_word = words[0]
        rest_inp = inp[len(words[0]) :].strip()

        all_commands = self.get_commands()
        matching_commands = [cmd for cmd in all_commands if cmd.startswith(first_word)]
        return matching_commands, first_word, rest_inp

    def run(self, inp):
        if inp.startswith("!"):
            self.coder.event("command_run")
            return self.do_run("run", inp[1:])

        res = self.matching_commands(inp)
        if res is None:
            return
        matching_commands, first_word, rest_inp = res
        if len(matching_commands) == 1:
            command = matching_commands[0][1:]
            self.coder.event(f"command_{command}")
            return self.do_run(command, rest_inp)
        elif first_word in matching_commands:
            command = first_word[1:]
            self.coder.event(f"command_{command}")
            return self.do_run(command, rest_inp)
        elif len(matching_commands) > 1:
            self.io.tool_error(f"Ambiguous command: {', '.join(matching_commands)}")
        else:
            self.io.tool_error(f"Invalid command: {first_word}")

    # any method called cmd_xxx becomes a command automatically.
    # each one must take an args param.

    def cmd_commit(self, args=None):
        "Commit edits to the repo made outside the chat (commit message optional)"
        try:
            self.raw_cmd_commit(args)
        except ANY_GIT_ERROR as err:
            self.io.tool_error(f"Unable to complete commit: {err}")

    def raw_cmd_commit(self, args=None):
        if not self.coder.repo:
            self.io.tool_error("No git repository found.")
            return

        if not self.coder.repo.is_dirty():
            self.io.tool_warning("No more changes to commit.")
            return

        commit_message = args.strip() if args else None
        self.coder.repo.commit(message=commit_message, coder=self.coder)

    def cmd_lint(self, args="", fnames=None):
        "Lint and fix in-chat files or all dirty files if none in chat"

        if not self.coder.repo:
            self.io.tool_error("No git repository found.")
            return

        if not fnames:
            fnames = self.coder.get_inchat_relative_files()

        # If still no files, get all dirty files in the repo
        if not fnames and self.coder.repo:
            fnames = self.coder.repo.get_dirty_files()

        if not fnames:
            self.io.tool_warning("No dirty files to lint.")
            return

        fnames = [self.coder.abs_root_path(fname) for fname in fnames]

        lint_coder = None
        for fname in fnames:
            try:
                errors = self.coder.linter.lint(fname)
            except FileNotFoundError as err:
                self.io.tool_error(f"Unable to lint {fname}")
                self.io.tool_output(str(err))
                continue

            if not errors:
                continue

            self.io.tool_output(errors)
            if not self.io.confirm_ask(f"Fix lint errors in {fname}?", default="y"):
                continue

            # Commit everything before we start fixing lint errors
            if self.coder.repo.is_dirty() and self.coder.dirty_commits:
                self.cmd_commit("")

            if not lint_coder:
                lint_coder = self.coder.clone(
                    # Clear the chat history, fnames
                    cur_messages=[],
                    done_messages=[],
                    fnames=None,
                )

            lint_coder.add_rel_fname(fname)
            lint_coder.run(errors)
            lint_coder.abs_fnames = set()

        if lint_coder and self.coder.repo.is_dirty() and self.coder.auto_commits:
            self.cmd_commit("")

    def cmd_clear(self, args):
        "Clear the chat history"

        self._clear_chat_history()
        self.io.tool_output("All chat history cleared.")

    def _drop_all_files(self):
        self.coder.abs_fnames = set()

        # When dropping all files, keep those that were originally provided via args.read
        if self.original_read_only_fnames:
            # Keep only the original read-only files
            to_keep = set()
            for abs_fname in self.coder.abs_read_only_fnames:
                rel_fname = self.coder.get_rel_fname(abs_fname)
                if (
                    abs_fname in self.original_read_only_fnames
                    or rel_fname in self.original_read_only_fnames
                ):
                    to_keep.add(abs_fname)
            self.coder.abs_read_only_fnames = to_keep
        else:
            self.coder.abs_read_only_fnames = set()

    def _clear_chat_history(self):
        self.coder.done_messages = []
        self.coder.cur_messages = []

    def cmd_reset(self, args):
        "Drop all files and clear the chat history"
        self._drop_all_files()
        self._clear_chat_history()
        self.io.tool_output("All files dropped and chat history cleared.")

    def cmd_tokens(self, args):
        "Report on the number of tokens used by the current chat context"

        res = []

        self.coder.choose_fence()

        # system messages
        main_sys = self.coder.fmt_system_prompt(self.coder.gpt_prompts.main_system)
        main_sys += "\n" + self.coder.fmt_system_prompt(self.coder.gpt_prompts.system_reminder)
        msgs = [
            dict(role="system", content=main_sys),
            dict(
                role="system",
                content=self.coder.fmt_system_prompt(self.coder.gpt_prompts.system_reminder),
            ),
        ]

        tokens = self.coder.main_model.token_count(msgs)
        res.append((tokens, "system messages", ""))

        # chat history
        msgs = self.coder.done_messages + self.coder.cur_messages
        if msgs:
            tokens = self.coder.main_model.token_count(msgs)
            res.append((tokens, "chat history", "use /clear to clear"))

        # repo map
        other_files = set(self.coder.get_all_abs_files()) - set(self.coder.abs_fnames)
        if self.coder.repo_map:
            repo_content = self.coder.repo_map.get_repo_map(self.coder.abs_fnames, other_files)
            if repo_content:
                tokens = self.coder.main_model.token_count(repo_content)
                res.append((tokens, "repository map", "use --map-tokens to resize"))

        fence = "`" * 3

        file_res = []
        # files
        for fname in self.coder.abs_fnames:
            relative_fname = self.coder.get_rel_fname(fname)
            content = self.io.read_text(fname)
            if is_image_file(relative_fname):
                tokens = self.coder.main_model.token_count_for_image(fname)
            else:
                # approximate
                content = f"{relative_fname}\n{fence}\n" + content + "{fence}\n"
                tokens = self.coder.main_model.token_count(content)
            file_res.append((tokens, f"{relative_fname}", "/drop to remove"))

        # read-only files
        for fname in self.coder.abs_read_only_fnames:
            relative_fname = self.coder.get_rel_fname(fname)
            content = self.io.read_text(fname)
            if content is not None and not is_image_file(relative_fname):
                # approximate
                content = f"{relative_fname}\n{fence}\n" + content + "{fence}\n"
                tokens = self.coder.main_model.token_count(content)
                file_res.append((tokens, f"{relative_fname} (read-only)", "/drop to remove"))

        file_res.sort()
        res.extend(file_res)

        self.io.tool_output(
            f"Approximate context window usage for {self.coder.main_model.name}, in tokens:"
        )
        self.io.tool_output()

        width = 8
        cost_width = 9

        def fmt(v):
            return format(int(v), ",").rjust(width)

        col_width = max(len(row[1]) for row in res)

        cost_pad = " " * cost_width
        total = 0
        total_cost = 0.0
        for tk, msg, tip in res:
            total += tk
            cost = tk * (self.coder.main_model.info.get("input_cost_per_token") or 0)
            total_cost += cost
            msg = msg.ljust(col_width)
            self.io.tool_output(f"${cost:7.4f} {fmt(tk)} {msg} {tip}")  # noqa: E231

        self.io.tool_output("=" * (width + cost_width + 1))
        self.io.tool_output(f"${total_cost:7.4f} {fmt(total)} tokens total")  # noqa: E231

        limit = self.coder.main_model.info.get("max_input_tokens") or 0
        if not limit:
            return

        remaining = limit - total
        if remaining > 1024:
            self.io.tool_output(f"{cost_pad}{fmt(remaining)} tokens remaining in context window")
        elif remaining > 0:
            self.io.tool_error(
                f"{cost_pad}{fmt(remaining)} tokens remaining in context window (use /drop or"
                " /clear to make space)"
            )
        else:
            self.io.tool_error(
                f"{cost_pad}{fmt(remaining)} tokens remaining, window exhausted (use /drop or"
                " /clear to make space)"
            )
        self.io.tool_output(f"{cost_pad}{fmt(limit)} tokens max context window size")

    def cmd_undo(self, args):
        "Undo the last git commit if it was done by aider"
        try:
            self.raw_cmd_undo(args)
        except ANY_GIT_ERROR as err:
            self.io.tool_error(f"Unable to complete undo: {err}")

    def raw_cmd_undo(self, args):
        if not self.coder.repo:
            self.io.tool_error("No git repository found.")
            return

        last_commit = self.coder.repo.get_head_commit()
        if not last_commit or not last_commit.parents:
            self.io.tool_error("This is the first commit in the repository. Cannot undo.")
            return

        last_commit_hash = self.coder.repo.get_head_commit_sha(short=True)
        last_commit_message = self.coder.repo.get_head_commit_message("(unknown)").strip()
        last_commit_message = (last_commit_message.splitlines() or [""])[0]
        if last_commit_hash not in self.coder.aider_commit_hashes:
            self.io.tool_error("The last commit was not made by aider in this chat session.")
            self.io.tool_output(
                "You could try `/git reset --hard HEAD^` but be aware that this is a destructive"
                " command!"
            )
            return

        if len(last_commit.parents) > 1:
            self.io.tool_error(
                f"The last commit {last_commit.hexsha} has more than 1 parent, can't undo."
            )
            return

        prev_commit = last_commit.parents[0]
        changed_files_last_commit = [item.a_path for item in last_commit.diff(prev_commit)]

        for fname in changed_files_last_commit:
            if self.coder.repo.repo.is_dirty(path=fname):
                self.io.tool_error(
                    f"The file {fname} has uncommitted changes. Please stash them before undoing."
                )
                return

            # Check if the file was in the repo in the previous commit
            try:
                prev_commit.tree[fname]
            except KeyError:
                self.io.tool_error(
                    f"The file {fname} was not in the repository in the previous commit. Cannot"
                    " undo safely."
                )
                return

        local_head = self.coder.repo.repo.git.rev_parse("HEAD")
        current_branch = self.coder.repo.repo.active_branch.name
        try:
            remote_head = self.coder.repo.repo.git.rev_parse(f"origin/{current_branch}")
            has_origin = True
        except ANY_GIT_ERROR:
            has_origin = False

        if has_origin:
            if local_head == remote_head:
                self.io.tool_error(
                    "The last commit has already been pushed to the origin. Undoing is not"
                    " possible."
                )
                return

        # Reset only the files which are part of `last_commit`
        restored = set()
        unrestored = set()
        for file_path in changed_files_last_commit:
            try:
                self.coder.repo.repo.git.checkout("HEAD~1", file_path)
                restored.add(file_path)
            except ANY_GIT_ERROR:
                unrestored.add(file_path)

        if unrestored:
            self.io.tool_error(f"Error restoring {file_path}, aborting undo.")
            self.io.tool_output("Restored files:")
            for file in restored:
                self.io.tool_output(f"  {file}")
            self.io.tool_output("Unable to restore files:")
            for file in unrestored:
                self.io.tool_output(f"  {file}")
            return

        # Move the HEAD back before the latest commit
        self.coder.repo.repo.git.reset("--soft", "HEAD~1")

        self.io.tool_output(f"Removed: {last_commit_hash} {last_commit_message}")

        # Get the current HEAD after undo
        current_head_hash = self.coder.repo.get_head_commit_sha(short=True)
        current_head_message = self.coder.repo.get_head_commit_message("(unknown)").strip()
        current_head_message = (current_head_message.splitlines() or [""])[0]
        self.io.tool_output(f"Now at:  {current_head_hash} {current_head_message}")
        if hasattr(self.coder, "code_graph") and self.coder.code_graph:
            for fname in changed_files_last_commit:
                abs_path = self.coder.abs_root_path(fname)
                try:
                    self.coder.code_graph.update_file(abs_path)
                except Exception as e:
                    self.coder.io.tool_warning(f"CodeGraph update failed for {fname}: {e}")

        if self.coder.main_model.send_undo_reply:
            return prompts.undo_command_reply

    def cmd_diff(self, args=""):
        "Display the diff of changes since the last message"
        try:
            self.raw_cmd_diff(args)
        except ANY_GIT_ERROR as err:
            self.io.tool_error(f"Unable to complete diff: {err}")

    def raw_cmd_diff(self, args=""):
        if not self.coder.repo:
            self.io.tool_error("No git repository found.")
            return

        current_head = self.coder.repo.get_head_commit_sha()
        if current_head is None:
            self.io.tool_error("Unable to get current commit. The repository might be empty.")
            return

        if len(self.coder.commit_before_message) < 2:
            commit_before_message = current_head + "^"
        else:
            commit_before_message = self.coder.commit_before_message[-2]

        if not commit_before_message or commit_before_message == current_head:
            self.io.tool_warning("No changes to display since the last message.")
            return

        self.io.tool_output(f"Diff since {commit_before_message[:7]}...")

        if self.coder.pretty:
            run_cmd(f"git diff {commit_before_message}")
            return

        diff = self.coder.repo.diff_commits(
            self.coder.pretty,
            commit_before_message,
            "HEAD",
        )

        self.io.print(diff)

    def quote_fname(self, fname):
        if " " in fname and '"' not in fname:
            fname = f'"{fname}"'
        return fname

    def completions_raw_read_only(self, document, complete_event):
        # Get the text before the cursor
        text = document.text_before_cursor

        # Skip the first word and the space after it
        after_command = text.split()[-1]

        # Create a new Document object with the text after the command
        new_document = Document(after_command, cursor_position=len(after_command))

        def get_paths():
            return [self.coder.root] if self.coder.root else None

        path_completer = PathCompleter(
            get_paths=get_paths,
            only_directories=False,
            expanduser=True,
        )

        # Adjust the start_position to replace all of 'after_command'
        adjusted_start_position = -len(after_command)

        # Collect all completions
        all_completions = []

        # Iterate over the completions and modify them
        for completion in path_completer.get_completions(new_document, complete_event):
            quoted_text = self.quote_fname(after_command + completion.text)
            all_completions.append(
                Completion(
                    text=quoted_text,
                    start_position=adjusted_start_position,
                    display=completion.display,
                    style=completion.style,
                    selected_style=completion.selected_style,
                )
            )

        # Add completions from the 'add' command
        add_completions = self.completions_add()
        for completion in add_completions:
            if after_command in completion:
                all_completions.append(
                    Completion(
                        text=completion,
                        start_position=adjusted_start_position,
                        display=completion,
                    )
                )

        # Sort all completions based on their text
        sorted_completions = sorted(all_completions, key=lambda c: c.text)

        # Yield the sorted completions
        for completion in sorted_completions:
            yield completion

    def completions_add(self):
        files = set(self.coder.get_all_relative_files())
        files = files - set(self.coder.get_inchat_relative_files())
        files = [self.quote_fname(fn) for fn in files]
        return files

    def glob_filtered_to_repo(self, pattern):
        if not pattern.strip():
            return []
        try:
            if os.path.isabs(pattern):
                # Handle absolute paths
                raw_matched_files = [Path(pattern)]
            else:
                try:
                    raw_matched_files = list(Path(self.coder.root).glob(pattern))
                except (IndexError, AttributeError):
                    raw_matched_files = []
        except ValueError as err:
            self.io.tool_error(f"Error matching {pattern}: {err}")
            raw_matched_files = []

        matched_files = []
        for fn in raw_matched_files:
            matched_files += expand_subdir(fn)

        matched_files = [
            fn.relative_to(self.coder.root)
            for fn in matched_files
            if fn.is_relative_to(self.coder.root)
        ]

        # if repo, filter against it
        if self.coder.repo:
            git_files = self.coder.repo.get_tracked_files()
            matched_files = [fn for fn in matched_files if str(fn) in git_files]

        res = list(map(str, matched_files))
        return res

    def cmd_add(self, args):
        "Add files to the chat so aider can edit them or review them in detail"

        all_matched_files = set()

        filenames = parse_quoted_filenames(args)
        for word in filenames:
            if Path(word).is_absolute():
                fname = Path(word)
            else:
                fname = Path(self.coder.root) / word

            if self.coder.repo and self.coder.repo.ignored_file(fname):
                self.io.tool_warning(f"Skipping {fname} due to aiderignore or --subtree-only.")
                continue

            if fname.exists():
                if fname.is_file():
                    all_matched_files.add(str(fname))
                    continue
                # an existing dir, escape any special chars so they won't be globs
                word = re.sub(r"([\*\?\[\]])", r"[\1]", word)

            matched_files = self.glob_filtered_to_repo(word)
            if matched_files:
                all_matched_files.update(matched_files)
                continue

            if "*" in str(fname) or "?" in str(fname):
                self.io.tool_error(
                    f"No match, and cannot create file with wildcard characters: {fname}"
                )
                continue

            if fname.exists() and fname.is_dir() and self.coder.repo:
                self.io.tool_error(f"Directory {fname} is not in git.")
                self.io.tool_output(f"You can add to git with: /git add {fname}")
                continue

            if self.io.confirm_ask(f"No files matched '{word}'. Do you want to create {fname}?"):
                try:
                    fname.parent.mkdir(parents=True, exist_ok=True)
                    fname.touch()
                    all_matched_files.add(str(fname))
                except OSError as e:
                    self.io.tool_error(f"Error creating file {fname}: {e}")

        for matched_file in sorted(all_matched_files):
            abs_file_path = self.coder.abs_root_path(matched_file)

            if (
                not abs_file_path.startswith(self.coder.root)
                and not is_image_file(matched_file)
                and self.coder.auto_commits
            ):
                self.io.tool_error(
                    f"Can not add {abs_file_path}, which is not within {self.coder.root}"
                )
                continue

            if (
                self.coder.repo
                and self.coder.repo.git_ignored_file(matched_file)
                and not self.coder.add_gitignore_files
            ):
                self.io.tool_error(f"Can't add {matched_file} which is in gitignore")
                continue

            if abs_file_path in self.coder.abs_fnames:
                self.io.tool_error(f"{matched_file} is already in the chat as an editable file")
                continue
            elif abs_file_path in self.coder.abs_read_only_fnames:
                # Determine if file can be promoted to editable
                if self.coder.repo:
                    can_edit = self.coder.repo.path_in_repo(matched_file)
                else:
                    can_edit = abs_file_path.startswith(self.coder.root)

                if can_edit:
                    self.coder.abs_read_only_fnames.remove(abs_file_path)
                    self.coder.abs_fnames.add(abs_file_path)
                    self.io.tool_output(
                        f"Moved {matched_file} from read-only to editable files in the chat"
                    )
                else:
                    self.io.tool_error(
                        f"Cannot add {matched_file} as it's not part of the repository"
                    )
            else:
                if is_image_file(matched_file) and not self.coder.main_model.info.get(
                    "supports_vision"
                ):
                    self.io.tool_error(
                        f"Cannot add image file {matched_file} as the"
                        f" {self.coder.main_model.name} does not support images."
                    )
                    continue
                content = self.io.read_text(abs_file_path)
                if content is None:
                    self.io.tool_error(f"Unable to read {matched_file}")
                else:
                    self.coder.abs_fnames.add(abs_file_path)
                    fname = self.coder.get_rel_fname(abs_file_path)
                    self.io.tool_output(f"Added {fname} to the chat")
                    self.coder.check_added_files()

    def completions_drop(self):
        files = self.coder.get_inchat_relative_files()
        read_only_files = [self.coder.get_rel_fname(fn) for fn in self.coder.abs_read_only_fnames]
        all_files = files + read_only_files
        all_files = [self.quote_fname(fn) for fn in all_files]
        return all_files

    def cmd_drop(self, args=""):
        "Remove files from the chat session to free up context space"

        if not args.strip():
            if self.original_read_only_fnames:
                self.io.tool_output(
                    "Dropping all files from the chat session except originally read-only files."
                )
            else:
                self.io.tool_output("Dropping all files from the chat session.")
            self._drop_all_files()
            return

        filenames = parse_quoted_filenames(args)
        for word in filenames:
            # Expand tilde in the path
            expanded_word = os.path.expanduser(word)

            # Handle read-only files with substring matching and samefile check
            read_only_matched = []
            for f in self.coder.abs_read_only_fnames:
                if expanded_word in f:
                    read_only_matched.append(f)
                    continue

                # Try samefile comparison for relative paths
                try:
                    abs_word = os.path.abspath(expanded_word)
                    if os.path.samefile(abs_word, f):
                        read_only_matched.append(f)
                except (FileNotFoundError, OSError):
                    continue

            for matched_file in read_only_matched:
                self.coder.abs_read_only_fnames.remove(matched_file)
                self.io.tool_output(f"Removed read-only file {matched_file} from the chat")

            # For editable files, use glob if word contains glob chars, otherwise use substring
            if any(c in expanded_word for c in "*?[]"):
                matched_files = self.glob_filtered_to_repo(expanded_word)
            else:
                # Use substring matching like we do for read-only files
                matched_files = [
                    self.coder.get_rel_fname(f) for f in self.coder.abs_fnames if expanded_word in f
                ]

            if not matched_files:
                matched_files.append(expanded_word)

            for matched_file in matched_files:
                abs_fname = self.coder.abs_root_path(matched_file)
                if abs_fname in self.coder.abs_fnames:
                    self.coder.abs_fnames.remove(abs_fname)
                    self.io.tool_output(f"Removed {matched_file} from the chat")

    def cmd_git(self, args):
        "Run a git command (output excluded from chat)"
        combined_output = None
        try:
            args = "git " + args
            env = dict(subprocess.os.environ)
            env["GIT_EDITOR"] = "true"
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                shell=True,
                encoding=self.io.encoding,
                errors="replace",
            )
            combined_output = result.stdout
        except Exception as e:
            self.io.tool_error(f"Error running /git command: {e}")

        if combined_output is None:
            return

        self.io.tool_output(combined_output)

    def cmd_test(self, args):
        "Run a shell command and add the output to the chat on non-zero exit code"
        if not args and self.coder.test_cmd:
            args = self.coder.test_cmd

        if not args:
            return

        if not callable(args):
            if type(args) is not str:
                raise ValueError(repr(args))
            return self.cmd_run(args, True)

        errors = args()
        if not errors:
            return

        self.io.tool_output(errors)
        return errors

    def cmd_run(self, args, add_on_nonzero_exit=False):
        "Run a shell command and optionally add the output to the chat (alias: !)"
        exit_status, combined_output = run_cmd(
            args, verbose=self.verbose, error_print=self.io.tool_error, cwd=self.coder.root
        )

        if combined_output is None:
            return

        # Calculate token count of output
        token_count = self.coder.main_model.token_count(combined_output)
        k_tokens = token_count / 1000

        if add_on_nonzero_exit:
            add = exit_status != 0
        else:
            add = self.io.confirm_ask(f"Add {k_tokens:.1f}k tokens of command output to the chat?")

        if add:
            num_lines = len(combined_output.strip().splitlines())
            line_plural = "line" if num_lines == 1 else "lines"
            self.io.tool_output(f"Added {num_lines} {line_plural} of output to the chat.")

            msg = prompts.run_output.format(
                command=args,
                output=combined_output,
            )

            self.coder.cur_messages += [
                dict(role="user", content=msg),
                dict(role="assistant", content="Ok."),
            ]

            if add_on_nonzero_exit and exit_status != 0:
                # Return the formatted output message for test failures
                return msg
            elif add and exit_status != 0:
                self.io.placeholder = "What's wrong? Fix"

        # Return None if output wasn't added or command succeeded
        return None

    def cmd_exit(self, args):
        "Exit the application"
        self.coder.event("exit", reason="/exit")
        sys.exit()

    def cmd_quit(self, args):
        "Exit the application"
        self.cmd_exit(args)

    def cmd_ls(self, args):
        "List all known files and indicate which are included in the chat session"

        files = self.coder.get_all_relative_files()

        other_files = []
        chat_files = []
        read_only_files = []
        for file in files:
            abs_file_path = self.coder.abs_root_path(file)
            if abs_file_path in self.coder.abs_fnames:
                chat_files.append(file)
            else:
                other_files.append(file)

        # Add read-only files
        for abs_file_path in self.coder.abs_read_only_fnames:
            rel_file_path = self.coder.get_rel_fname(abs_file_path)
            read_only_files.append(rel_file_path)

        if not chat_files and not other_files and not read_only_files:
            self.io.tool_output("\nNo files in chat, git repo, or read-only list.")
            return

        if other_files:
            self.io.tool_output("Repo files not in the chat:\n")
        for file in other_files:
            self.io.tool_output(f"  {file}")

        if read_only_files:
            self.io.tool_output("\nRead-only files:\n")
        for file in read_only_files:
            self.io.tool_output(f"  {file}")

        if chat_files:
            self.io.tool_output("\nFiles in chat:\n")
        for file in chat_files:
            self.io.tool_output(f"  {file}")

    def basic_help(self):
        commands = sorted(self.get_commands())
        pad = max(len(cmd) for cmd in commands)
        pad = "{cmd:" + str(pad) + "}"
        for cmd in commands:
            cmd_method_name = f"cmd_{cmd[1:]}".replace("-", "_")
            cmd_method = getattr(self, cmd_method_name, None)
            cmd = pad.format(cmd=cmd)
            if cmd_method:
                description = cmd_method.__doc__
                self.io.tool_output(f"{cmd} {description}")
            else:
                self.io.tool_output(f"{cmd} No description available.")
        self.io.tool_output()
        self.io.tool_output("Use `/help <question>` to ask questions about how to use aider.")

    def cmd_help(self, args):
        "Ask questions about aider"

        if not args.strip():
            self.basic_help()
            return

        self.coder.event("interactive help")
        from aider.coders.base_coder import Coder

        if not self.help:
            res = install_help_extra(self.io)
            if not res:
                self.io.tool_error("Unable to initialize interactive help.")
                return

            self.help = Help()

        coder = Coder.create(
            io=self.io,
            from_coder=self.coder,
            edit_format="help",
            summarize_from_coder=False,
            map_tokens=512,
            map_mul_no_files=1,
        )
        user_msg = self.help.ask(args)
        user_msg += """
# Announcement lines from when this session of aider was launched:

"""
        user_msg += "\n".join(self.coder.get_announcements()) + "\n"

        coder.run(user_msg, preproc=False)

        if self.coder.repo_map:
            map_tokens = self.coder.repo_map.max_map_tokens
            map_mul_no_files = self.coder.repo_map.map_mul_no_files
        else:
            map_tokens = 0
            map_mul_no_files = 1

        raise SwitchCoder(
            edit_format=self.coder.edit_format,
            summarize_from_coder=False,
            from_coder=coder,
            map_tokens=map_tokens,
            map_mul_no_files=map_mul_no_files,
            show_announcements=False,
        )

    def completions_ask(self):
        raise CommandCompletionException()

    def completions_code(self):
        raise CommandCompletionException()

    def completions_architect(self):
        raise CommandCompletionException()

    def completions_context(self):
        raise CommandCompletionException()

    def cmd_ask(self, args):
        """Ask questions about the code base without editing any files. If no prompt provided, switches to ask mode."""  # noqa
        return self._generic_chat_command(args, "ask")

    def cmd_code(self, args):
        """Ask for changes to your code. If no prompt provided, switches to code mode."""  # noqa
        return self._generic_chat_command(args, self.coder.main_model.edit_format)

    def cmd_architect(self, args):
        """Enter architect/editor mode using 2 different models. If no prompt provided, switches to architect/editor mode."""  # noqa
        return self._generic_chat_command(args, "architect")

    def cmd_context(self, args):
        """Enter context mode to see surrounding code context. If no prompt provided, switches to context mode."""  # noqa
        return self._generic_chat_command(args, "context", placeholder=args.strip() or None)

    def cmd_ok(self, args):
        "Alias for `/code Ok, please go ahead and make those changes.` (any args are appended)"
        msg = "Ok, please go ahead and make those changes."
        extra = (args or "").strip()
        if extra:
            msg = f"{msg} {extra}"
        return self.cmd_code(msg)

    def _generic_chat_command(self, args, edit_format, placeholder=None):
        if not args.strip():
            # Switch to the corresponding chat mode if no args provided
            return self.cmd_chat_mode(edit_format)

        from aider.coders.base_coder import Coder

        coder = Coder.create(
            io=self.io,
            from_coder=self.coder,
            edit_format=edit_format,
            summarize_from_coder=False,
        )

        user_msg = args
        coder.run(user_msg)

        # Use the provided placeholder if any
        raise SwitchCoder(
            edit_format=self.coder.edit_format,
            summarize_from_coder=False,
            from_coder=coder,
            show_announcements=False,
            placeholder=placeholder,
        )

    def get_help_md(self):
        "Show help about all commands in markdown"

        res = """
|Command|Description|
|:------|:----------|
"""
        commands = sorted(self.get_commands())
        for cmd in commands:
            cmd_method_name = f"cmd_{cmd[1:]}".replace("-", "_")
            cmd_method = getattr(self, cmd_method_name, None)
            if cmd_method:
                description = cmd_method.__doc__
                res += f"| **{cmd}** | {description} |\n"
            else:
                res += f"| **{cmd}** | |\n"

        res += "\n"
        return res

    def cmd_voice(self, args):
        "Record and transcribe voice input"

        if not self.voice:
            if "OPENAI_API_KEY" not in os.environ:
                self.io.tool_error("To use /voice you must provide an OpenAI API key.")
                return
            try:
                self.voice = voice.Voice(
                    audio_format=self.voice_format or "wav", device_name=self.voice_input_device
                )
            except voice.SoundDeviceError:
                self.io.tool_error(
                    "Unable to import `sounddevice` and/or `soundfile`, is portaudio installed?"
                )
                return

        try:
            text = self.voice.record_and_transcribe(None, language=self.voice_language)
        except litellm.OpenAIError as err:
            self.io.tool_error(f"Unable to use OpenAI whisper model: {err}")
            return

        if text:
            self.io.placeholder = text

    def cmd_paste(self, args):
        """Paste image/text from the clipboard into the chat.\
        Optionally provide a name for the image."""
        try:
            # Check for image first
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                if args.strip():
                    filename = args.strip()
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in (".jpg", ".jpeg", ".png"):
                        basename = filename
                    else:
                        basename = f"{filename}.png"
                else:
                    basename = "clipboard_image.png"

                temp_dir = tempfile.mkdtemp()
                temp_file_path = os.path.join(temp_dir, basename)
                image_format = "PNG" if basename.lower().endswith(".png") else "JPEG"
                image.save(temp_file_path, image_format)

                abs_file_path = Path(temp_file_path).resolve()

                # Check if a file with the same name already exists in the chat
                existing_file = next(
                    (f for f in self.coder.abs_fnames if Path(f).name == abs_file_path.name), None
                )
                if existing_file:
                    self.coder.abs_fnames.remove(existing_file)
                    self.io.tool_output(f"Replaced existing image in the chat: {existing_file}")

                self.coder.abs_fnames.add(str(abs_file_path))
                self.io.tool_output(f"Added clipboard image to the chat: {abs_file_path}")
                self.coder.check_added_files()

                return

            # If not an image, try to get text
            text = pyperclip.paste()
            if text:
                self.io.tool_output(text)
                return text

            self.io.tool_error("No image or text content found in clipboard.")
            return

        except Exception as e:
            self.io.tool_error(f"Error processing clipboard content: {e}")

    def cmd_read_only(self, args):
        "Add files to the chat that are for reference only, or turn added files to read-only"
        if not args.strip():
            # Convert all files in chat to read-only
            for fname in list(self.coder.abs_fnames):
                self.coder.abs_fnames.remove(fname)
                self.coder.abs_read_only_fnames.add(fname)
                rel_fname = self.coder.get_rel_fname(fname)
                self.io.tool_output(f"Converted {rel_fname} to read-only")
            return

        filenames = parse_quoted_filenames(args)
        all_paths = []

        # First collect all expanded paths
        for pattern in filenames:
            expanded_pattern = expanduser(pattern)
            path_obj = Path(expanded_pattern)
            is_abs = path_obj.is_absolute()
            if not is_abs:
                path_obj = Path(self.coder.root) / path_obj

            matches = []
            # Check for literal path existence first
            if path_obj.exists():
                matches = [path_obj]
            else:
                # If literal path doesn't exist, try globbing
                if is_abs:
                    # For absolute paths, glob it
                    matches = [Path(p) for p in glob.glob(expanded_pattern)]
                else:
                    # For relative paths and globs, use glob from the root directory
                    matches = list(Path(self.coder.root).glob(expanded_pattern))

            if not matches:
                self.io.tool_error(f"No matches found for: {pattern}")
            else:
                all_paths.extend(matches)

        # Then process them in sorted order
        for path in sorted(all_paths):
            abs_path = self.coder.abs_root_path(path)
            if os.path.isfile(abs_path):
                self._add_read_only_file(abs_path, path)
            elif os.path.isdir(abs_path):
                self._add_read_only_directory(abs_path, path)
            else:
                self.io.tool_error(f"Not a file or directory: {abs_path}")

    def _add_read_only_file(self, abs_path, original_name):
        if is_image_file(original_name) and not self.coder.main_model.info.get("supports_vision"):
            self.io.tool_error(
                f"Cannot add image file {original_name} as the"
                f" {self.coder.main_model.name} does not support images."
            )
            return

        if abs_path in self.coder.abs_read_only_fnames:
            self.io.tool_error(f"{original_name} is already in the chat as a read-only file")
            return
        elif abs_path in self.coder.abs_fnames:
            self.coder.abs_fnames.remove(abs_path)
            self.coder.abs_read_only_fnames.add(abs_path)
            self.io.tool_output(
                f"Moved {original_name} from editable to read-only files in the chat"
            )
        else:
            self.coder.abs_read_only_fnames.add(abs_path)
            self.io.tool_output(f"Added {original_name} to read-only files.")

    def _add_read_only_directory(self, abs_path, original_name):
        added_files = 0
        for root, _, files in os.walk(abs_path):
            for file in files:
                file_path = os.path.join(root, file)
                if (
                    file_path not in self.coder.abs_fnames
                    and file_path not in self.coder.abs_read_only_fnames
                ):
                    self.coder.abs_read_only_fnames.add(file_path)
                    added_files += 1

        if added_files > 0:
            self.io.tool_output(
                f"Added {added_files} files from directory {original_name} to read-only files."
            )
        else:
            self.io.tool_output(f"No new files added from directory {original_name}.")

    def cmd_map(self, args):
        "Print out the current repository map"
        repo_map = self.coder.get_repo_map()
        if repo_map:
            self.io.tool_output(repo_map)
        else:
            self.io.tool_output("No repository map available.")

    def cmd_map_refresh(self, args):
        "Force a refresh of the repository map"
        repo_map = self.coder.get_repo_map(force_refresh=True)
        if repo_map:
            self.io.tool_output("The repo map has been refreshed, use /map to view it.")

    def cmd_settings(self, args):
        "Print out the current settings"
        settings = format_settings(self.parser, self.args)
        announcements = "\n".join(self.coder.get_announcements())

        # Build metadata for the active models (main, editor, weak)
        model_sections = []
        active_models = [
            ("Main model", self.coder.main_model),
            ("Editor model", getattr(self.coder.main_model, "editor_model", None)),
            ("Weak model", getattr(self.coder.main_model, "weak_model", None)),
        ]
        for label, model in active_models:
            if not model:
                continue
            info = getattr(model, "info", {}) or {}
            if not info:
                continue
            model_sections.append(f"{label} ({model.name}):")
            for k, v in sorted(info.items()):
                model_sections.append(f"  {k}: {v}")
            model_sections.append("")  # blank line between models

        model_metadata = "\n".join(model_sections)

        output = f"{announcements}\n{settings}"
        if model_metadata:
            output += "\n" + model_metadata
        self.io.tool_output(output)

    def completions_raw_load(self, document, complete_event):
        return self.completions_raw_read_only(document, complete_event)

    def cmd_load(self, args):
        "Load and execute commands from a file"
        if not args.strip():
            self.io.tool_error("Please provide a filename containing commands to load.")
            return

        try:
            with open(args.strip(), "r", encoding=self.io.encoding, errors="replace") as f:
                commands = f.readlines()
        except FileNotFoundError:
            self.io.tool_error(f"File not found: {args}")
            return
        except Exception as e:
            self.io.tool_error(f"Error reading file: {e}")
            return

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd or cmd.startswith("#"):
                continue

            self.io.tool_output(f"\nExecuting: {cmd}")
            try:
                self.run(cmd)
            except SwitchCoder:
                self.io.tool_error(
                    f"Command '{cmd}' is only supported in interactive mode, skipping."
                )

    def completions_raw_save(self, document, complete_event):
        return self.completions_raw_read_only(document, complete_event)

    def cmd_save(self, args):
        "Save commands to a file that can reconstruct the current chat session's files"
        if not args.strip():
            self.io.tool_error("Please provide a filename to save the commands to.")
            return

        try:
            with open(args.strip(), "w", encoding=self.io.encoding) as f:
                f.write("/drop\n")
                # Write commands to add editable files
                for fname in sorted(self.coder.abs_fnames):
                    rel_fname = self.coder.get_rel_fname(fname)
                    f.write(f"/add       {rel_fname}\n")

                # Write commands to add read-only files
                for fname in sorted(self.coder.abs_read_only_fnames):
                    # Use absolute path for files outside repo root, relative path for files inside
                    if Path(fname).is_relative_to(self.coder.root):
                        rel_fname = self.coder.get_rel_fname(fname)
                        f.write(f"/read-only {rel_fname}\n")
                    else:
                        f.write(f"/read-only {fname}\n")

            self.io.tool_output(f"Saved commands to {args.strip()}")
        except Exception as e:
            self.io.tool_error(f"Error saving commands to file: {e}")

    def cmd_multiline_mode(self, args):
        "Toggle multiline mode (swaps behavior of Enter and Meta+Enter)"
        self.io.toggle_multiline_mode()

    def cmd_copy(self, args):
        "Copy the last assistant message to the clipboard"
        all_messages = self.coder.done_messages + self.coder.cur_messages
        assistant_messages = [msg for msg in reversed(all_messages) if msg["role"] == "assistant"]

        if not assistant_messages:
            self.io.tool_error("No assistant messages found to copy.")
            return

        last_assistant_message = assistant_messages[0]["content"]

        try:
            pyperclip.copy(last_assistant_message)
            preview = (
                last_assistant_message[:50] + "..."
                if len(last_assistant_message) > 50
                else last_assistant_message
            )
            self.io.tool_output(f"Copied last assistant message to clipboard. Preview: {preview}")
        except pyperclip.PyperclipException as e:
            self.io.tool_error(f"Failed to copy to clipboard: {str(e)}")
            self.io.tool_output(
                "You may need to install xclip or xsel on Linux, or pbcopy on macOS."
            )
        except Exception as e:
            self.io.tool_error(f"An unexpected error occurred while copying to clipboard: {str(e)}")

    def cmd_report(self, args):
        "Report a problem by opening a GitHub Issue"
        from aider.report import report_github_issue

        announcements = "\n".join(self.coder.get_announcements())
        issue_text = announcements

        if args.strip():
            title = args.strip()
        else:
            title = None

        report_github_issue(issue_text, title=title, confirm=False)

    def cmd_editor(self, initial_content=""):
        "Open an editor to write a prompt"

        user_input = pipe_editor(initial_content, suffix="md", editor=self.editor)
        if user_input.strip():
            self.io.set_placeholder(user_input.rstrip())

    def cmd_edit(self, args=""):
        "Alias for /editor: Open an editor to write a prompt"
        return self.cmd_editor(args)

    def cmd_think_tokens(self, args):
        """Set the thinking token budget, eg: 8096, 8k, 10.5k, 0.5M, or 0 to disable."""
        model = self.coder.main_model

        if not args.strip():
            # Display current value if no args are provided
            formatted_budget = model.get_thinking_tokens()
            if formatted_budget is None:
                self.io.tool_output("Thinking tokens are not currently set.")
            else:
                budget = model.get_raw_thinking_tokens()
                self.io.tool_output(
                    f"Current thinking token budget: {budget:,} tokens ({formatted_budget})."
                )
            return

        value = args.strip()
        model.set_thinking_tokens(value)

        # Handle the special case of 0 to disable thinking tokens
        if value == "0":
            self.io.tool_output("Thinking tokens disabled.")
        else:
            formatted_budget = model.get_thinking_tokens()
            budget = model.get_raw_thinking_tokens()
            self.io.tool_output(
                f"Set thinking token budget to {budget:,} tokens ({formatted_budget})."
            )

        self.io.tool_output()

        # Output announcements
        announcements = "\n".join(self.coder.get_announcements())
        self.io.tool_output(announcements)

    def cmd_reasoning_effort(self, args):
        "Set the reasoning effort level (values: number or low/medium/high depending on model)"
        model = self.coder.main_model

        if not args.strip():
            # Display current value if no args are provided
            reasoning_value = model.get_reasoning_effort()
            if reasoning_value is None:
                self.io.tool_output("Reasoning effort is not currently set.")
            else:
                self.io.tool_output(f"Current reasoning effort: {reasoning_value}")
            return

        value = args.strip()
        model.set_reasoning_effort(value)
        reasoning_value = model.get_reasoning_effort()
        self.io.tool_output(f"Set reasoning effort to {reasoning_value}")
        self.io.tool_output()

        # Output announcements
        announcements = "\n".join(self.coder.get_announcements())
        self.io.tool_output(announcements)

    def cmd_copy_context(self, args=None):
        """Copy the current chat context as markdown, suitable to paste into a web UI"""

        chunks = self.coder.format_chat_chunks()

        markdown = ""

        # Only include specified chunks in order
        for messages in [chunks.repo, chunks.readonly_files, chunks.chat_files]:
            for msg in messages:
                # Only include user messages
                if msg["role"] != "user":
                    continue

                content = msg["content"]

                # Handle image/multipart content
                if isinstance(content, list):
                    for part in content:
                        if part.get("type") == "text":
                            markdown += part["text"] + "\n\n"
                else:
                    markdown += content + "\n\n"

        args = args or ""
        markdown += f"""
Just tell me how to edit the files to make the changes.
Don't give me back entire files.
Just show me the edits I need to make.

{args}
"""

        try:
            pyperclip.copy(markdown)
            self.io.tool_output("Copied code context to clipboard.")
        except pyperclip.PyperclipException as e:
            self.io.tool_error(f"Failed to copy to clipboard: {str(e)}")
            self.io.tool_output(
                "You may need to install xclip or xsel on Linux, or pbcopy on macOS."
            )
        except Exception as e:
            self.io.tool_error(f"An unexpected error occurred while copying to clipboard: {str(e)}")

    def cmd_codebase(self, args):
        """Tạo báo cáo HTML tổng quan về codebase với đồ thị và phân tích chi tiết."""
        import json
        import os
        import webbrowser
        from datetime import datetime
        from html import escape

        if not hasattr(self.coder, "code_graph") or not self.coder.code_graph:
            self.io.tool_output("❌ Code Graph Engine is not available for this project.")
            return

        cg = self.coder.code_graph
        if not cg.is_indexed():
            cg.index()

        raw_db = cg.db._db if hasattr(cg.db, "_db") else cg.db

        # ===== 1. THU THẬP DỮ LIỆU =====
        symbols = [dict(s) for s in raw_db.conn.execute("""
            SELECT * FROM symbols
            WHERE file_path NOT LIKE '%node_modules%'
            AND file_path NOT LIKE '%/.venv/%'
            AND file_path NOT LIKE '%/site-packages/%'
            AND file_path NOT LIKE '%.dotcode/%'
            AND file_path NOT LIKE '%aider/website/%'
            AND file_path NOT LIKE '%aider/_posts/%'
            AND file_path NOT LIKE '%.min.js%'
            AND kind IN ('class', 'function', 'method')
            ORDER BY pagerank DESC
            LIMIT 500
        """).fetchall()]

        symbol_ids = {s["id"] for s in symbols}

        # Tạo node FILE
        file_set = {}
        for sym in symbols:
            fp = sym.get("file_path", "")
            if fp not in file_set:
                fp_clean = fp.replace('/', '_').replace('\\', '_')
                file_set[fp] = {
                    "id": f"FILE::{fp_clean}",
                    "label": os.path.basename(fp),
                    "kind": "file",
                    "title": f"FILE: {fp}",
                    "pagerank": 0.0,
                }
        file_nodes = list(file_set.values())

        # Tạo module nodes
        module_nodes = []
        if cg.graphrag and cg.graphrag.communities:
            for cid, cdata in cg.graphrag.communities.items():
                summary = cdata.get("summary", "")
                if summary:
                    short_label = summary[:50].split(".")[0] if summary else f"Module {cid}"
                    module_nodes.append(
                        {
                            "id": f"MODULE::{cid}",
                            "label": short_label,
                            "kind": "module",
                            "title": f"MODULE {cid}: {escape(summary[:200])}",
                            "pagerank": 0.5,
                        }
                    )

        total_symbols = len(symbols)
        classes = sum(1 for s in symbols if s.get("kind") == "class")
        functions = sum(1 for s in symbols if s.get("kind") == "function")
        methods = sum(1 for s in symbols if s.get("kind") == "method")

        languages = set()
        for s in symbols:
            fp = s.get("file_path", "")
            ext = os.path.splitext(fp)[1].lower()
            if ext in (".py",):
                languages.add("Python")
            elif ext in (".ts", ".tsx"):
                languages.add("TypeScript")
            elif ext in (".js", ".jsx"):
                languages.add("JavaScript")
            elif ext == ".rs":
                languages.add("Rust")
            elif ext == ".go":
                languages.add("Go")

        files = set(s.get("file_path", "") for s in symbols)
        total_files = len(files)

        # ===== LẤY TẤT CẢ EDGES =====
        edges = []

        # 1. Quan hệ thật từ DB: calls, contains, imports, references
        for e in raw_db.conn.execute("""
            SELECT source_id, target_id, type
            FROM edges
            WHERE type IN ('calls', 'contains', 'imports', 'references')
        """).fetchall():
            source_id, target_id, edge_type = e[0], e[1], e[2]
            if source_id in symbol_ids and target_id in symbol_ids:
                edges.append({"source": source_id, "target": target_id, "type": edge_type})

        # 2. Thêm quan hệ FILE -> symbol
        for sym in symbols:
            fp = sym.get("file_path", "")
            if not fp:
                continue
            file_node = file_set.get(fp)
            if file_node:
                edges.append(
                    {"source": file_node["id"], "target": sym["id"], "type": "file_contains"}
                )

        # 3. Thêm quan hệ MODULE -> symbol
        if cg.graphrag and cg.graphrag.communities:
            for cid, cdata in cg.graphrag.communities.items():
                module_id = f"MODULE::{cid}"
                for node_id in cdata.get("nodes", []):
                    if node_id in symbol_ids:
                        edges.append(
                            {"source": module_id, "target": node_id, "type": "module_contains"}
                        )

        total_edges = len(edges)

        # Communities
        communities_data = []
        if cg.graphrag and cg.graphrag.communities:
            for cid, cdata in sorted(cg.graphrag.communities.items()):
                nodes = cdata.get("nodes", [])
                summary = cdata.get("summary", "")
                key_names = []
                for node_id in nodes[:5]:
                    sym = cg.db.get_symbol(node_id) if hasattr(cg.db, "get_symbol") else None
                    if sym:
                        name = sym.name if hasattr(sym, "name") else sym.get("name", "?")
                        kind = (
                            sym.kind.value
                            if hasattr(sym, "kind") and hasattr(sym.kind, "value")
                            else sym.get("kind", "?")
                        )
                        key_names.append(f"{kind} {name}")
                communities_data.append(
                    {
                        "id": cid,
                        "summary": summary,
                        "key_symbols": key_names,
                        "node_count": len(nodes),
                    }
                )

        # ===== 2. GỌI LLM ĐỂ TẠO BÁO CÁO THÔNG MINH =====
        smart_summary = ""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if api_key and communities_data:
            try:
                comm_text = "\n".join(
                    [
                        f"- Module {c['id']}: {c['summary'][:150]} ({c['node_count']} symbols)"
                        for c in communities_data[:10]
                    ]
                )
                user_lang = getattr(self.coder, "chat_language", "en") or "en"
                lang_name = "Vietnamese" if user_lang.startswith("vi") else "English"
                prompt = f"""You are a software architecture expert. Create a brief summary of this codebase.

    STATISTICS:
    - Files: {total_files}
    - Symbols: {total_symbols} ({functions} functions, {methods} methods, {classes} classes)
    - Relationships: {total_edges}
    - Languages: {', '.join(sorted(languages)) if languages else 'Unknown'}
    - Modules: {len(communities_data)}

    MODULE LIST:
    {comm_text if comm_text else 'No module data available'}

    Write a summary in {lang_name}, including:
    1. Project scale and complexity
    2. Main modules and their functions
    3. Technologies used
    4. Architecture observations

    Keep it under 200 words. Return ONLY the summary, no explanations."""
                import requests as req

                response = req.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 400,
                        "temperature": 0.3,
                    },
                    timeout=15,
                )
                if response.status_code == 200:
                    data = response.json()
                    smart_summary = data["choices"][0]["message"]["content"].strip()
            except Exception:
                smart_summary = "Không thể tạo báo cáo thông minh do LLM không khả dụng."

        if not smart_summary:
            smart_summary = (
                f"Dự án gồm {total_files} file, {total_symbols} symbol và {total_edges} quan hệ. "
                f"Hệ thống có {classes} class, {functions} function và {methods} method. "
                "Các node có PageRank cao thường là những thành phần quan trọng trong kiến trúc."
            )

        # ===== 3. MÀU SẮC =====
        color_map = {
            "class": {
                "background": "#e74c3c",
                "border": "#c0392b",
                "highlight": {"background": "#ff6b5f", "border": "#ffffff"},
            },
            "function": {
                "background": "#3498db",
                "border": "#2471a3",
                "highlight": {"background": "#5dade2", "border": "#ffffff"},
            },
            "method": {
                "background": "#2ecc71",
                "border": "#1e8449",
                "highlight": {"background": "#58d68d", "border": "#ffffff"},
            },
            "file": {
                "background": "#f39c12",
                "border": "#d68910",
                "highlight": {"background": "#f7dc6f", "border": "#ffffff"},
            },
            "module": {
                "background": "#9b59b6",
                "border": "#7d3c98",
                "highlight": {"background": "#af7ac5", "border": "#ffffff"},
            },
        }
        simple_color_map = {
            "class": "#e74c3c",
            "function": "#3498db",
            "method": "#2ecc71",
            "file": "#f39c12",
            "module": "#9b59b6",
        }
        shape_map = {
            "class": "dot",
            "function": "ellipse",
            "method": "box",
            "file": "square",
            "module": "diamond",
        }
        edge_color_map = {
            "calls": "#2f80ed",
            "contains": "#8e44ad",
            "imports": "#e67e22",
            "references": "#1abc9c",
            "file_contains": "#f39c12",
            "module_contains": "#9b59b6",
        }

        # ===== 4. CHUẨN BỊ DATA CHO ĐỒ THỊ =====
        nodes_json = []
        for sym in symbols:
            kind = sym.get("kind", "function")
            pagerank = sym.get("pagerank", 0) or 0
            name = sym.get("name", "")
            file_path = sym.get("file_path", "")
            line = sym.get("start_line", 0)
            nodes_json.append(
                {
                    "id": sym["id"],
                    "label": name,
                    "color": color_map.get(
                        kind,
                        {
                            "background": "#95a5a6",
                            "border": "#7f8c8d",
                            "highlight": {"background": "#bdc3c7", "border": "#ffffff"},
                        },
                    ),
                    "shape": shape_map.get(kind, "ellipse"),
                    "title": (
                        f"{kind.upper()}: {name}\nFile: {file_path}\nLine: {line}\nPageRank:"
                        f" {pagerank:.4f}"
                    ),
                    "size": max(12, min(45, pagerank * 250 + 12)),
                    "kind": kind,
                    "file": file_path,
                    "pagerank": pagerank,
                    "font": {"color": "#ffffff", "size": 14},
                }
            )

        for fn in file_nodes:
            nodes_json.append(
                {
                    "id": fn["id"],
                    "label": fn["label"],
                    "color": color_map.get(
                        "file",
                        {
                            "background": "#f39c12",
                            "border": "#d68910",
                            "highlight": {"background": "#f7dc6f", "border": "#ffffff"},
                        },
                    ),
                    "shape": "square",
                    "title": fn["title"],
                    "size": 20,
                    "kind": "file",
                    "file": "",
                    "pagerank": 0.5,
                    "font": {"color": "#ffffff", "size": 14},
                }
            )

        for mn in module_nodes:
            nodes_json.append(
                {
                    "id": mn["id"],
                    "label": mn["label"],
                    "color": color_map.get(
                        "module",
                        {
                            "background": "#9b59b6",
                            "border": "#7d3c98",
                            "highlight": {"background": "#af7ac5", "border": "#ffffff"},
                        },
                    ),
                    "shape": "diamond",
                    "title": mn["title"],
                    "size": 25,
                    "kind": "module",
                    "file": "",
                    "pagerank": 0.8,
                    "font": {"color": "#ffffff", "size": 14},
                }
            )

        edges_json = []
        for e in edges:
            edges_json.append({"source": e["source"], "target": e["target"], "type": e["type"]})

        # ===== 5. HÀM RENDER DANH SÁCH =====
        def render_symbol_list(title, items, color, limit=12):
            if not items:
                return f"<h3>{title}</h3><div class='summary-box'>Không có dữ liệu.</div>"
            html_items = ""
            for s in items[:limit]:
                name = escape(str(s.get("name", "")))
                kind = escape(str(s.get("kind", "")))
                pagerank = s.get("pagerank", 0) or 0
                file_path = escape(str(s.get("file_path", "")))
                html_items += f"""
                <div class="sym" title="{file_path}">
                    <span class="dot" style="background:{color}"></span>
                    <span>{kind} <b>{name}</b></span>
                    <span style="color:#777;margin-left:auto">{pagerank:.4f}</span>
                </div>"""
            return f"<h3>{title}</h3><div class='top-symbols'>{html_items}</div>"

        def render_communities(items, limit=10):
            if not items:
                return "<div class='summary-box'>Không có dữ liệu module.</div>"
            html_items = ""
            for c in items[:limit]:
                cid = escape(str(c.get("id", "")))
                summary = escape(str(c.get("summary", "")))[:180]
                key_symbols = escape(", ".join(c.get("key_symbols", [])[:5]))
                node_count = c.get("node_count", 0)
                html_items += f"""
                <div class="community-card">
                    <h4>Module {cid}</h4><p>{summary}...</p>
                    <div class="keys">Nodes: {node_count}</div>
                    <div class="keys">🔑 {key_symbols}</div>
                </div>"""
            return html_items

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ===== 6. TẠO HTML =====
        html = f"""<!DOCTYPE html>
    <html lang="vi">
    <head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DotCode - Codebase Report</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet">
    <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f23; color: #e0e0e0; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-bottom: 3px solid #e74c3c; }}
    .header h1 {{ font-size: 2em; color: #e74c3c; }} .header p {{ color: #a0a0a0; margin-top: 5px; }}
    .container {{ display: flex; height: calc(100vh - 100px); }}
    .sidebar {{ width: 320px; background: #1a1a2e; overflow-y: auto; padding: 15px; border-right: 1px solid #2a2a4e; }}
    .sidebar h3 {{ color: #e74c3c; margin-top: 16px; margin-bottom: 10px; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; }}
    .stat {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2a4e; font-size: 0.85em; }}
    .stat .label {{ color: #a0a0a0; }} .stat .value {{ color: white; font-weight: bold; }}
    .summary-box {{ background: #16213e; border-radius: 8px; padding: 12px; margin: 10px 0; font-size: 0.8em; line-height: 1.5; color: #c0c0c0; }}
    .community-card {{ background: #16213e; border-radius: 8px; padding: 12px; margin: 10px 0; border-left: 3px solid #e74c3c; }}
    .community-card h4 {{ color: #e74c3c; font-size: 0.9em; margin-bottom: 5px; }}
    .community-card p {{ font-size: 0.75em; color: #a0a0a0; line-height: 1.4; }}
    .community-card .keys {{ font-size: 0.7em; color: #58a6ff; margin-top: 5px; }}
    .top-symbols {{ margin-top: 8px; }}
    .top-symbols .sym {{ display: flex; align-items: center; gap: 6px; padding: 5px 0; font-size: 0.75em; border-bottom: 1px solid rgba(255,255,255,0.04); }}
    .top-symbols .dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
    #graph {{ flex: 1; background: #0f0f23; }}
    .btn {{ display: inline-block; padding: 7px 12px; border-radius: 4px; border: none; cursor: pointer; font-size: 0.75em; margin-right: 5px; color: white; font-weight: bold; }}
    .btn-green {{ background: #2ecc71; }} .btn-red {{ background: #e74c3c; }} .btn-blue {{ background: #3498db; }} .btn-orange {{ background: #f39c12; }} .btn-purple {{ background: #9b59b6; }}
    .legend {{ display: flex; gap: 10px; font-size: 0.72em; margin-top: 8px; flex-wrap: wrap; }}
    .legend-item {{ display: flex; align-items: center; gap: 4px; }} .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    .controls {{ margin-top: 15px; }}
    </style>
    </head>
    <body>
    <div class="header">
    <h1>📊 DotCode Codebase Report</h1>
    <p>Generated on {now_str} · {total_files} files · {total_symbols} symbols · {total_edges} relationships</p>
    </div>
    <div class="container">
    <div class="sidebar">
        <h3>📋 Tổng quan thông minh</h3>
        <div class="summary-box">{escape(smart_summary).replace(chr(10), "<br>")}</div>
        <h3>📊 Thống kê</h3>
        <div class="stat"><span class="label">Files</span><span class="value">{total_files}</span></div>
        <div class="stat"><span class="label">Symbols</span><span class="value">{total_symbols}</span></div>
        <div class="stat"><span class="label">Classes</span><span class="value">{classes}</span></div>
        <div class="stat"><span class="label">Functions</span><span class="value">{functions}</span></div>
        <div class="stat"><span class="label">Methods</span><span class="value">{methods}</span></div>
        <div class="stat"><span class="label">Relationships</span><span class="value">{total_edges}</span></div>
        <div class="stat"><span class="label">Languages</span><span class="value">{', '.join(sorted(languages)) if languages else 'Unknown'}</span></div>
        <div class="stat"><span class="label">Modules</span><span class="value">{len(communities_data)}</span></div>
        <div class="controls">
        <button class="btn btn-green" id="methodBtn" onclick="toggleKind('method')">Ẩn methods</button>
        <button class="btn btn-red" id="functionBtn" onclick="toggleKind('function')">Ẩn functions</button>
        <button class="btn btn-orange" id="fileBtn" onclick="toggleKind('file')">Ẩn files</button>
        <button class="btn btn-purple" id="moduleBtn" onclick="toggleKind('module')" {'style="display:none"' if not module_nodes else ""}>Ẩn modules</button>
        <button class="btn btn-blue" onclick="resetView()">Reset view</button>
        </div>
        <div class="controls">
        <button class="btn btn-blue" id="callsEdgeBtn" onclick="toggleEdgeType('calls')">Ẩn calls</button>
        <button class="btn btn-purple" id="containsEdgeBtn" onclick="toggleEdgeType('contains')">Ẩn contains</button>
        <button class="btn btn-orange" id="importsEdgeBtn" onclick="toggleEdgeType('imports')">Ẩn imports</button>
        <button class="btn btn-green" id="refsEdgeBtn" onclick="toggleEdgeType('references')">Ẩn references</button>
        <button class="btn btn-orange" id="fileEdgeBtn" onclick="toggleEdgeType('file_contains')">Hiện file links</button>
        </div>
        <div class="legend">
        <div class="legend-item"><span class="legend-dot" style="background:#e74c3c"></span> Class</div>
        <div class="legend-item"><span class="legend-dot" style="background:#3498db"></span> Function</div>
        <div class="legend-item"><span class="legend-dot" style="background:#2ecc71"></span> Method</div>
        <div class="legend-item"><span class="legend-dot" style="background:#f39c12"></span> File</div>
        <div class="legend-item"><span class="legend-dot" style="background:#9b59b6"></span> Module</div>
        </div>
        <h3>🧩 Modules</h3>
        {render_communities(communities_data)}
        {render_symbol_list("🔴 Top Classes", sorted([s for s in symbols if s.get("kind") == "class"], key=lambda x: x.get("pagerank", 0) or 0, reverse=True), simple_color_map["class"])}
        {render_symbol_list("🔵 Top Functions", sorted([s for s in symbols if s.get("kind") == "function"], key=lambda x: x.get("pagerank", 0) or 0, reverse=True), simple_color_map["function"])}
        {render_symbol_list("🟢 Top Methods", sorted([s for s in symbols if s.get("kind") == "method"], key=lambda x: x.get("pagerank", 0) or 0, reverse=True), simple_color_map["method"])}
    </div>
    <div id="graph"></div>
    </div>
    <script>
    const nodesData = {json.dumps(nodes_json, ensure_ascii=False)};
    const edgesData = {json.dumps(edges_json, ensure_ascii=False)};
    const edgeColorMap = {json.dumps(edge_color_map)};

    const nodes = new vis.DataSet(nodesData);
    const edges = new vis.DataSet(edgesData.map(e => ({{
        from: e.source,
        to: e.target,
        color: {{
            color: edgeColorMap[e.type] || "#555",
            highlight: "#ffffff"
        }},
        arrows: {{
            to: {{
                enabled: true,
                scaleFactor: 0.5
            }}
        }},

        // Không hiện chữ trực tiếp trên cạnh để đỡ rối
        label: "",

        // Khi rê chuột vào cạnh mới hiện loại quan hệ
        title: e.type,

        font: {{
            size: 8,
            color: "#aaaaaa",
            strokeWidth: 0
        }},

        dashes: e.type === "file_contains" || e.type === "module_contains",

        width:
            e.type === "calls" ? 2 :
            e.type === "contains" ? 1.5 :
            e.type === "imports" ? 1 :
            e.type === "references" ? 1 :
            e.type === "file_contains" ? 0.6 :
            e.type === "module_contains" ? 0.6 :
            1,

        hidden: e.type === "file_contains",

        type: e.type
    }})));

    const container = document.getElementById("graph");
    const network = new vis.Network(container, {{ nodes, edges }}, {{
    nodes: {{ borderWidth: 2, shadow: true, font: {{ color: "#ffffff", size: 14, face: "Segoe UI" }} }},
    edges: {{ smooth: {{ type: "dynamic" }} }},
    physics: {{
        solver: "forceAtlas2Based",
        forceAtlas2Based: {{ gravitationalConstant: -80, springLength: 120, springConstant: 0.02, damping: 0.95, avoidOverlap: 1 }},
        stabilization: {{ iterations: 300, updateInterval: 10 }},
    }},
    layout: {{ improvedLayout: true }},
    interaction: {{ hover: true, tooltipDelay: 120, navigationButtons: true, keyboard: true }}
    }});

    network.once("stabilizationIterationsDone", function() {{ network.setOptions({{ physics: false }}); }});
    let dragTimer;
    network.on("dragStart", function() {{ network.setOptions({{ physics: true }}); clearTimeout(dragTimer); }});
    network.on("dragEnd", function() {{ dragTimer = setTimeout(function() {{ network.setOptions({{ physics: false }}); }}, 2000); }});

    const hiddenState = {{}};
    function toggleKind(kind) {{
        hiddenState[kind] = !hiddenState[kind];
        const allNodes = network.body.data.nodes.get();
        const updates = allNodes.filter(n => n.kind === kind).map(n => ({{ id: n.id, hidden: hiddenState[kind] }}));
        network.body.data.nodes.update(updates);
        const btnMap = {{ method: 'methodBtn', function: 'functionBtn', file: 'fileBtn', module: 'moduleBtn' }};
        const labels = {{ method: 'methods', function: 'functions', file: 'files', module: 'modules' }};
        const btn = document.getElementById(btnMap[kind]);
        if (btn) btn.textContent = hiddenState[kind] ? 'Hiện ' + labels[kind] : 'Ẩn ' + labels[kind];
    }}

    const hiddenEdgeState = {{}};
    function toggleEdgeType(type) {{
        hiddenEdgeState[type] = !hiddenEdgeState[type];
        const allEdges = network.body.data.edges.get();
        const updates = allEdges.filter(e => e.type === type).map(e => ({{ id: e.id, hidden: hiddenEdgeState[type] }}));
        network.body.data.edges.update(updates);
        const btnMap = {{ calls: "callsEdgeBtn", contains: "containsEdgeBtn", imports: "importsEdgeBtn", references: "refsEdgeBtn", file_contains: "fileEdgeBtn" }};
        const labelMap = {{ calls: "calls", contains: "contains", imports: "imports", references: "references", file_contains: "file links" }};
        const btn = document.getElementById(btnMap[type]);
        if (btn) btn.textContent = hiddenEdgeState[type] ? "Hiện " + labelMap[type] : "Ẩn " + labelMap[type];
    }}

    function resetView() {{ network.fit({{ animation: {{ duration: 800, easingFunction: "easeInOutQuad" }} }}); }}
    </script>
    </body>
    </html>"""

        # ===== 7. LƯU VÀ MỞ FILE HTML =====
        output_dir = os.path.join(cg.root, ".dotcode")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "codebase_report.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        webbrowser.open("file://" + os.path.abspath(output_path))
        self.io.tool_output(f"✅ Đã tạo báo cáo: {output_path}")
        self.io.tool_output(
            f"📊 Symbols: {total_symbols}, Classes: {classes}, "
            f"Functions: {functions}, Methods: {methods}, "
            f"Files: {len(file_nodes)}, Modules: {len(module_nodes)}, "
            f"Edges: {total_edges}"
        )


def expand_subdir(file_path):
    if file_path.is_file():
        yield file_path
        return

    if file_path.is_dir():
        for file in file_path.rglob("*"):
            if file.is_file():
                yield file


def parse_quoted_filenames(args):
    filenames = re.findall(r"\"(.+?)\"|(\S+)", args)
    filenames = [name for sublist in filenames for name in sublist if name]
    return filenames


def get_help_md():
    md = Commands(None, None).get_help_md()
    return md


def main():
    md = get_help_md()
    print(md)


if __name__ == "__main__":
    status = main()
    sys.exit(status)
