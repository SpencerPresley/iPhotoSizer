"""Tests for terminal app name detection via process tree walking."""

import subprocess
from unittest.mock import patch

from iphoto_sizer.core import get_terminal_app_name


class TestGetTerminalAppName:
    """Test get_terminal_app_name() which walks the process tree to find the .app bundle."""

    def _mock_ps(self, process_chain: list[tuple[int, int, str]]):
        """Build a mock for subprocess.run that simulates a process tree.

        Args:
            process_chain: List of (pid, ppid, command_path) tuples representing
                           the process tree. The function looks up by PID, so each
                           entry should have a unique pid.
        """
        lookup = {pid: (ppid, comm) for pid, ppid, comm in process_chain}

        def fake_run(cmd, **_kwargs):
            # cmd is ["ps", "-p", "<pid>", "-o", "ppid=,comm="]
            pid = int(cmd[2])
            if pid in lookup:
                ppid, comm = lookup[pid]
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=f"  {ppid} {comm}\n", stderr=""
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        return fake_run

    # -- Happy path: finds .app bundle in process tree --

    def test_finds_app_in_grandparent(self):
        """Typical case: python -> zsh -> Ghostty.app/Contents/MacOS/ghostty."""
        chain = [
            (100, 50, "/usr/bin/python3"),                                  # self
            (50, 10, "/bin/zsh"),                                           # shell
            (10, 1, "/Applications/Ghostty.app/Contents/MacOS/ghostty"),    # terminal
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() == "Ghostty"

    def test_finds_app_in_direct_parent(self):
        """Terminal spawns python directly without an intermediate shell."""
        chain = [
            (100, 10, "/usr/bin/python3"),
            (10, 1, "/Applications/iTerm.app/Contents/MacOS/iTerm2"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() == "iTerm"

    def test_finds_app_deep_in_tree(self):
        """Multiple intermediate processes (e.g., tmux, ssh, etc.)."""
        chain = [
            (100, 90, "/usr/bin/python3"),
            (90, 80, "/bin/zsh"),
            (80, 70, "/usr/local/bin/tmux"),
            (70, 60, "/bin/zsh"),
            (60, 10, "/usr/local/bin/tmux: server"),
            (10, 1, "/Applications/Ghostty.app/Contents/MacOS/ghostty"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() == "Ghostty"

    def test_apple_terminal(self):
        """macOS built-in Terminal.app."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 10, "/bin/zsh"),
            (10, 1, "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() == "Terminal"

    def test_vscode_terminal(self):
        """VS Code integrated terminal has a different .app path structure."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 10, "/bin/zsh"),
            (10, 1, "/Applications/Visual Studio Code.app/Contents/Frameworks/"
                     "Code Helper (Plugin).app/Contents/MacOS/Code Helper (Plugin)"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            # Should find the outermost .app bundle
            assert get_terminal_app_name() == "Visual Studio Code"

    def test_app_in_subdirectory(self):
        """App installed in a non-standard location still found."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 10, "/bin/zsh"),
            (10, 1, "/Users/someone/Downloads/WezTerm.app/Contents/MacOS/wezterm-gui"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() == "WezTerm"

    # -- No .app found --

    def test_returns_none_when_no_app_bundle(self):
        """Running from a context with no .app in the tree (e.g., SSH, cron)."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 10, "/bin/zsh"),
            (10, 1, "/usr/sbin/sshd"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() is None

    def test_returns_none_when_tree_is_just_init(self):
        """Process tree leads directly to PID 1 with no .app."""
        chain = [
            (100, 1, "/usr/bin/python3"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() is None

    # -- Edge cases and robustness --

    def test_ps_returns_empty_output(self):
        """ps returns no output (process vanished between calls)."""
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")):
            assert get_terminal_app_name() is None

    def test_ps_raises_os_error(self):
        """subprocess.run raises OSError — function should not propagate."""
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=OSError("no ps")):
            assert get_terminal_app_name() is None

    def test_ps_raises_runtime_error(self):
        """Any unexpected exception is swallowed — this is best-effort."""
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=RuntimeError("weird")):
            assert get_terminal_app_name() is None

    def test_getpid_raises(self):
        """Even os.getpid() failing shouldn't crash."""
        with patch("os.getpid", side_effect=RuntimeError("broken")):
            assert get_terminal_app_name() is None

    def test_ps_returns_malformed_output(self):
        """ps returns something unexpected (single token, no space)."""
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, stdout="garbage\n", stderr="")):
            assert get_terminal_app_name() is None

    def test_does_not_infinite_loop_on_pid_cycle(self):
        """If a PID somehow references itself as parent, don't loop forever."""
        chain = [
            (100, 100, "/usr/bin/python3"),  # points to itself
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() is None

    def test_stops_at_pid_0(self):
        """PID 0 is the kernel — should stop walking."""
        chain = [
            (100, 1, "/usr/bin/python3"),
            (1, 0, "/sbin/launchd"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() is None

    def test_dot_app_in_filename_not_in_path_component(self):
        """A command whose name contains '.app' but it's not a bundle path."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 1, "/usr/local/bin/myhelper.application"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            # ".application" is not ".app/", should not match
            assert get_terminal_app_name() is None

    def test_strips_dot_app_suffix_from_result(self):
        """Returned name should be 'Ghostty' not 'Ghostty.app'."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 1, "/Applications/Ghostty.app/Contents/MacOS/ghostty"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            result = get_terminal_app_name()
            assert result is not None
            assert not result.endswith(".app")

    def test_app_name_with_spaces(self):
        """App names with spaces should be preserved."""
        chain = [
            (100, 50, "/usr/bin/python3"),
            (50, 1, "/Applications/My Cool Terminal.app/Contents/MacOS/cool"),
        ]
        with patch("os.getpid", return_value=100), \
             patch("iphoto_sizer.core.subprocess.run", side_effect=self._mock_ps(chain)):
            assert get_terminal_app_name() == "My Cool Terminal"


class TestLoadPhotosDbTerminalMessage:
    """Test that load_photos_db uses the detected app name in the error message."""

    def test_uses_detected_app_name_in_error(self, capsys):
        with patch("iphoto_sizer.core.osxphotos.PhotosDB", side_effect=RuntimeError("no access")), \
             patch("iphoto_sizer.core.get_terminal_app_name", return_value="Ghostty"):
            import pytest
            with pytest.raises(SystemExit):
                from iphoto_sizer.core import load_photos_db
                load_photos_db()
        stderr = capsys.readouterr().err
        assert '"Ghostty"' in stderr
        assert "Full Disk Access" in stderr

    def test_falls_back_when_app_not_detected(self, capsys):
        with patch("iphoto_sizer.core.osxphotos.PhotosDB", side_effect=RuntimeError("no access")), \
             patch("iphoto_sizer.core.get_terminal_app_name", return_value=None):
            import pytest
            with pytest.raises(SystemExit):
                from iphoto_sizer.core import load_photos_db
                load_photos_db()
        stderr = capsys.readouterr().err
        assert "your terminal app" in stderr
        assert "Full Disk Access" in stderr
