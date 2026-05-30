import sys
import os
import shlex
import subprocess
import readline
import re

EXECUTABLES = set()
TAB_COUNT = 0
LAST_BUFFER = ""
MULTI_MATCH_READY = False
JOBS = []
HISTORY = []
LAST_HISTORY_WRITE_INDEX = 0
COMPLETIONS = {}
BUILTINS = {"echo", "exit", "type", "pwd", "cd",
            "jobs", "history", "complete", "declare"}
candidates = EXECUTABLES.union(BUILTINS)
COMPLETION_CACHE = []
VARIABLES = {}


def write_output(output, stdout_file=None, stderr_file=None, append_stdout=False):
    mode = 'a' if append_stdout else 'w'

    if stdout_file:
        open(stdout_file, mode).close()
    if stderr_file:
        open(stderr_file, 'w').close()

    if stdout_file:
        with open(stdout_file, mode) as f:
            f.write(output + "\n")
    else:
        print(output)


def longest_common_prefix(strings):
    if not strings:
        return ""

    prefix = strings[0]

    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""

    return prefix


def find_executable(cmd_name):
    for directory in os.environ.get("PATH", "").split(":"):
        full_path = os.path.join(directory, cmd_name)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None


def parse_redirection(command_line):
    tokens = shlex.split(command_line)

    stdout_file = None
    stderr_file = None
    append_stdout = False
    append_stderr = False

    clean_tokens = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in [">", "1>"]:
            stdout_file = tokens[i + 1]
            append_stdout = False
            i += 2

        elif token in [">>", "1>>"]:
            stdout_file = tokens[i + 1]
            append_stdout = True
            i += 2

        elif token == "2>":
            stderr_file = tokens[i + 1]
            append_stderr = False
            i += 2

        elif token == "2>>":
            stderr_file = tokens[i + 1]
            append_stderr = True
            i += 2

        else:
            clean_tokens.append(token)
            i += 1

    return clean_tokens, stdout_file, stderr_file, append_stdout, append_stderr


def completer(text, state):
    global TAB_COUNT, LAST_BUFFER
    buffer = readline.get_line_buffer()
    parts = buffer.split()

    # ---------------- REGISTERED COMPLETERS ----------------
    if len(parts) >= 1:
        command_name = parts[0]

        if command_name in COMPLETIONS:
            if buffer.endswith(" "):
                current_word = ""
            else:
                current_word = parts[-1]

            previous_word = ""
            if len(parts) >= 2:
                if buffer.endswith(" "):
                    previous_word = parts[-1]
                else:
                    previous_word = parts[-2]

            try:
                result = subprocess.run(
                    [
                        COMPLETIONS[command_name],
                        command_name,
                        current_word,
                        previous_word
                    ],
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "COMP_LINE": buffer,
                        "COMP_POINT": str(len(buffer.encode()))
                    }
                )

                matches = sorted([
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip() and line.strip().startswith(current_word)
                ])

                if not matches:
                    return None

                # Single match → complete immediately
                if len(matches) == 1:
                    TAB_COUNT = 0
                    if state == 0:
                        return matches[0] + " "
                    return None

                common = longest_common_prefix(matches)

                # LCP extends current input → complete to it, no bell
                if common != current_word:
                    TAB_COUNT = 0
                    if state == 0:
                        return common
                    return None

                # No LCP gain → bell on first tab, list on second
                if TAB_COUNT == 1:
                    sys.stdout.write("\n" + "  ".join(matches) + "\n")
                    sys.stdout.write("$ " + buffer)
                    sys.stdout.flush()
                    TAB_COUNT = 0
                    return None

                if state == 0:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                    TAB_COUNT = 1
                    return None

                return None

            except Exception:
                return None

    # ---------------- COMMAND COMPLETION ----------------
    if len(parts) <= 1 and not buffer.endswith(" "):

        candidates = EXECUTABLES.union(BUILTINS)

        matches = sorted([
            cmd for cmd in candidates
            if cmd.startswith(text)
        ])

        # No matches → bell
        if not matches:
            sys.stdout.write("\a")
            sys.stdout.flush()
            TAB_COUNT = 0
            return None

        common = longest_common_prefix(matches)

        # Single match → complete with trailing space
        if len(matches) == 1:
            TAB_COUNT = 0
            if state == 0:
                return matches[0] + " "
            return None

        # Partial prefix expansion (xyz_ → xyz_pig)
        if common != text:
            TAB_COUNT = 0
            if state == 0:
                return common
            return None

        # Multiple matches, no further expansion
        # IMPORTANT: check TAB_COUNT before state
        if TAB_COUNT == 1:
            sys.stdout.write("\n" + "  ".join(matches) + "\n")
            sys.stdout.write("$ " + buffer)
            sys.stdout.flush()
            TAB_COUNT = 0
            return None

        # First tab → bell and prepare for second tab
        if state == 0:
            sys.stdout.write("\a")
            sys.stdout.flush()
            TAB_COUNT = 1
            return None

        return None

    # ---------------- FILE / DIRECTORY COMPLETION ----------------
    token = text

    if token.endswith("/"):
        search_dir = token[:-1]
        prefix = ""
    else:
        search_dir = os.path.dirname(token)
        prefix = os.path.basename(token)

    if search_dir == "":
        search_dir = "."

    try:
        entries = sorted(os.listdir(search_dir))
    except FileNotFoundError:
        sys.stdout.write("\x07")
        sys.stdout.flush()
        return None

    matches = [e for e in entries if e.startswith(prefix)]

    if not matches:
        sys.stdout.write("\x07")
        sys.stdout.flush()
        return None

    if state >= len(matches):
        return None

    match = matches[state]

    if search_dir == ".":
        completed = match
    else:
        completed = os.path.join(search_dir, match)

    full_match_path = os.path.join(search_dir, match)

    if os.path.isdir(full_match_path):
        return completed + "/"

    return completed + " "


def get_executables():
    executables = set()

    for directory in os.environ.get("PATH", "").split(":"):
        if not os.path.isdir(directory):
            continue

        try:
            for file in os.listdir(directory):
                full_path = os.path.join(directory, file)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    executables.add(file)
        except PermissionError:
            continue

    return executables


def setup_autocomplete():
    global EXECUTABLES

    EXECUTABLES = get_executables()

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    readline.set_completer_delims(" \t\n")


def reap_jobs():
    global JOBS

    jobs_to_remove = []

    total_jobs = len(JOBS)

    for index, job in enumerate(JOBS):

        # process finished
        if job["process"].poll() is not None:

            # markers
            if index == total_jobs - 1:
                marker = "+"
            elif index == total_jobs - 2:
                marker = "-"
            else:
                marker = " "

            # remove trailing &
            command = job["command"].rstrip()

            if command.endswith("&"):
                command = command[:-1].rstrip()

            print(
                f"[{job['id']}]{marker}  "
                f"{'Done':<24}"
                f"{command}"
            )

            jobs_to_remove.append(job)

    # remove AFTER printing
    for job in jobs_to_remove:
        JOBS.remove(job)


def get_next_job_number():
    used_numbers = sorted(job["id"] for job in JOBS)

    job_number = 1

    for number in used_numbers:
        if number == job_number:
            job_number += 1
        else:
            break

    return job_number


def run_builtin(args, builtins):
    cmd = args[0]

    if cmd == "echo":
        return (" ".join(args[1:]) + "\n").encode()

    elif cmd == "pwd":
        return (os.getcwd() + "\n").encode()

    elif cmd == "type":
        target = args[1] if len(args) > 1 else ""

        if target in builtins:
            return f"{target} is a shell builtin\n".encode()

        path = find_executable(target)

        if path:
            return f"{target} is {path}\n".encode()

        return f"{target}: not found\n".encode()

    elif cmd == "history":

        output = ""

        # ---------------- history -r FILE ----------------
        if len(args) >= 3 and args[1] == "-r":

            path = args[2]

            try:
                with open(path, "r") as f:

                    for line in f:
                        line = line.rstrip("\n")

                        if line.strip() == "":
                            continue

                        HISTORY.append(line)

            except FileNotFoundError:
                output += f"history: {path}: No such file\n"

        # ---------------- history -w FILE ----------------
        elif len(args) >= 3 and args[1] == "-w":

            path = args[2]

            try:
                with open(path, "w") as f:

                    for command in HISTORY:
                        f.write(command + "\n")

            except Exception as e:
                output += f"history: {e}\n"
        # ---------------- history -a FILE ----------------
        elif len(args) >= 3 and args[1] == "-a":

            global LAST_HISTORY_WRITE_INDEX

            path = args[2]

            try:
                with open(path, "a") as f:

                    for command in HISTORY[LAST_HISTORY_WRITE_INDEX:]:
                        f.write(command + "\n")

                LAST_HISTORY_WRITE_INDEX = len(HISTORY)

            except Exception as e:
                output += f"history: {e}\n"
        # ---------------- history N ----------------
        elif len(args) > 1:

            try:
                n = int(args[1])

                start_index = max(0, len(HISTORY) - n)

                for index, command in enumerate(
                    HISTORY[start_index:],
                    start=start_index + 1
                ):
                    output += f"    {index}  {command}\n"

            except ValueError:
                output += "history: invalid argument\n"

        # ---------------- plain history ----------------
        else:

            for index, command in enumerate(HISTORY, start=1):
                output += f"    {index}  {command}\n"

        return output.encode()

    elif cmd == "declare":
        if len(args) >= 2 and args[1] == "-p":
            if len(args) < 3:
                return b""
            var_name = args[2]
            if var_name in VARIABLES:
                return f'declare -- {var_name}="{VARIABLES[var_name]}"\n'.encode()
            return f"declare: {var_name}: not found\n".encode()
        elif len(args) >= 2 and "=" in args[1]:
            var_name, value = args[1].split("=", 1)
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                return f"declare: `{args[1]}': not a valid identifier\n".encode()
            VARIABLES[var_name] = value
            return b""
        return b""

    elif cmd == "complete":

        if len(args) >= 4 and args[1] == "-C":
            script_path = args[2]
            command_name = args[3]
            COMPLETIONS[command_name] = script_path
            return b""

        elif len(args) >= 3 and args[1] == "-p":
            command_name = args[2]
            if command_name in COMPLETIONS:
                return (
                    f"complete -C '{COMPLETIONS[command_name]}' "
                    f"{command_name}\n"
                ).encode()
            return (
                f"complete: {command_name}: "
                f"no completion specification\n"
            ).encode()

        # ADD THIS
        elif len(args) >= 3 and args[1] == "-r":
            command_name = args[2]
            COMPLETIONS.pop(command_name, None)
            return b""

        return b""


def load_history_file():

    histfile = os.environ.get("HISTFILE")

    if not histfile:
        return

    if not os.path.exists(histfile):
        return

    try:
        with open(histfile, "r") as f:

            for line in f:
                line = line.rstrip("\n")

                if line.strip() == "":
                    continue

                HISTORY.append(line)

    except Exception:
        pass


def save_history_file():

    histfile = os.environ.get("HISTFILE")

    if not histfile:
        return

    try:
        with open(histfile, "w") as f:

            for command in HISTORY:
                f.write(command + "\n")

    except Exception:
        pass


def expand_variables(token):
    def replace(match):
        var_name = match.group(1) or match.group(2)
        return VARIABLES.get(var_name, "")
    return re.sub(r'\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)', replace, token)


def main():
    builtins = ["echo", "exit", "type", "pwd",
                "cd", "jobs", "history", "complete", "declare"]

    setup_autocomplete()
    setup_autocomplete()
    load_history_file()

    while True:
        try:
            reap_jobs()
            command_line = input("$ ")

            original_command = command_line

        except EOFError:
            break

        if not command_line:
            continue

        HISTORY.append(command_line)

        args, stdout_file, stderr_file, append_stdout, append_stderr = parse_redirection(
            command_line
        )
        args = [expanded for a in args if (expanded := expand_variables(a))]
        if not args:
            continue

        background = False

        if args[-1] == "&":
            background = True
            args = args[:-1]

            if not args:
                continue
        # ================= PIPELINE =================
        if "|" in args:

            # split pipeline commands
            commands = []
            current = []

            for token in args:
                if token == "|":
                    commands.append(current)
                    current = []
                else:
                    current.append(token)

            commands.append(current)

            processes = []
            prev_output = None

            try:

                for i, cmd in enumerate(commands):

                    program = cmd[0]
                    is_builtin = program in builtins
                    is_last = (i == len(commands) - 1)

                    # ---------------- BUILTIN ----------------
                    if is_builtin:

                        output = run_builtin(cmd, builtins)

                        # builtin ignores stdin for this stage
                        prev_output = output

                        # if last command, print result
                        if is_last:
                            sys.stdout.buffer.write(output)

                        continue

                    # ---------------- EXTERNAL ----------------
                    exe = find_executable(program)

                    if not exe:
                        print(f"{program}: not found")
                        break

                    # builtin output feeding into process
                    if isinstance(prev_output, bytes):

                        p = subprocess.Popen(
                            cmd,
                            executable=exe,
                            stdin=subprocess.PIPE,
                            stdout=None if is_last else subprocess.PIPE
                        )

                        stdout_data, _ = p.communicate(input=prev_output)

                    else:

                        p = subprocess.Popen(
                            cmd,
                            executable=exe,
                            stdin=prev_output,
                            stdout=None if is_last else subprocess.PIPE
                        )

                        stdout_data = None

                    if hasattr(prev_output, "close"):
                        prev_output.close()

                    if not is_last:
                        prev_output = p.stdout if stdout_data is None else stdout_data

                    processes.append(p)

                # wait for all processes
                for p in processes:
                    p.wait()

            except Exception as e:
                print(f"Pipeline error: {e}")

            continue

        program = args[0]

        if program == "exit":
            save_history_file()
            break

        elif program == "echo":
            output = " ".join(args[1:])
            write_output(output, stdout_file, stderr_file, append_stdout)

        elif program == "pwd":
            write_output(os.getcwd(), stdout_file, stderr_file)

        elif program == "type":
            cmd = args[1] if len(args) > 1 else ""

            if cmd in builtins:
                output = f"{cmd} is a shell builtin"
            else:
                path = find_executable(cmd)
                if path:
                    output = f"{cmd} is {path}"
                else:
                    output = f"{cmd}: not found"

            write_output(output, stdout_file, stderr_file, append_stdout)

        elif program == "cd":
            target = os.path.expanduser(args[1]) if len(
                args) > 1 else os.path.expanduser("~")

            try:
                os.chdir(target)
            except FileNotFoundError:
                error_msg = f"cd: {args[1]}: No such file or directory"

                if stderr_file:
                    write_output(error_msg, stderr_file)
                else:
                    print(error_msg)

        elif program == "jobs":

            jobs_to_remove = []

            total_jobs = len(JOBS)

            for index, job in enumerate(JOBS):

                # ---------- STATUS ----------
                if job["process"].poll() is None:
                    status = "Running"
                    command = job["command"]
                else:
                    status = "Done"

                    command = job["command"].rstrip()

                    if command.endswith("&"):
                        command = command[:-1].rstrip()

                    jobs_to_remove.append(job)

                # ---------- MARKERS ----------
                if index == total_jobs - 1:
                    marker = "+"
                elif index == total_jobs - 2:
                    marker = "-"
                else:
                    marker = " "

                print(
                    f"[{job['id']}]{marker}  "
                    f"{status:<24}"
                    f"{command}"
                )

            # remove done jobs AFTER printing everything
            for job in jobs_to_remove:
                JOBS.remove(job)

        elif program == "history":

            # ---------------- history -r FILE ----------------
            if len(args) >= 3 and args[1] == "-r":

                path = args[2]

                try:
                    with open(path, "r") as f:

                        for line in f:
                            line = line.rstrip("\n")

                            # ignore empty lines
                            if line.strip() == "":
                                continue

                            HISTORY.append(line)

                except FileNotFoundError:
                    print(f"history: {path}: No such file")

            # ---------------- history -w FILE ----------------
            elif len(args) >= 3 and args[1] == "-w":

                path = args[2]

                try:
                    with open(path, "w") as f:

                        for command in HISTORY:
                            f.write(command + "\n")

                except Exception as e:
                    print(f"history: {e}")
            # ---------------- history -a FILE ----------------
            elif len(args) >= 3 and args[1] == "-a":

                global LAST_HISTORY_WRITE_INDEX

                path = args[2]

                try:
                    with open(path, "a") as f:

                        for command in HISTORY[LAST_HISTORY_WRITE_INDEX:]:
                            f.write(command + "\n")

                    LAST_HISTORY_WRITE_INDEX = len(HISTORY)

                except Exception as e:
                    print(f"history: {e}")
            # ---------------- history N ----------------
            elif len(args) > 1:

                try:
                    n = int(args[1])

                    start_index = max(0, len(HISTORY) - n)

                    for index, command in enumerate(
                        HISTORY[start_index:],
                        start=start_index + 1
                    ):
                        print(f"    {index}  {command}")

                except ValueError:
                    print("history: invalid argument")

            # ---------------- plain history ----------------
            else:

                for index, command in enumerate(HISTORY, start=1):
                    print(f"    {index}  {command}")

        elif program == "declare":
            if len(args) >= 2 and args[1] == "-p":
                if len(args) >= 3:
                    var_name = args[2]
                    if var_name in VARIABLES:
                        print(f'declare -- {var_name}="{VARIABLES[var_name]}"')
                    else:
                        print(f"declare: {var_name}: not found")
            elif len(args) >= 2 and "=" in args[1]:
                var_name, value = args[1].split("=", 1)
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                    print(f"declare: `{args[1]}': not a valid identifier")
                else:
                    VARIABLES[var_name] = value

        elif program == "complete":

            if len(args) >= 4 and args[1] == "-C":
                script_path = args[2]
                command_name = args[3]
                COMPLETIONS[command_name] = script_path

            elif len(args) >= 3 and args[1] == "-p":
                command_name = args[2]
                if command_name in COMPLETIONS:
                    print(
                        f"complete -C '{COMPLETIONS[command_name]}' {command_name}")
                else:
                    print(
                        f"complete: {command_name}: no completion specification")

            # ADD THIS
            elif len(args) >= 3 and args[1] == "-r":
                command_name = args[2]
                COMPLETIONS.pop(command_name, None)

        else:

            exe_path = find_executable(program)

            if not exe_path:
                print(f"{program}: not found")
                continue

            try:
                stdout_mode = 'a' if append_stdout else 'w'
                stderr_mode = 'a' if append_stderr else 'w'

                stdout_f = open(
                    stdout_file, stdout_mode) if stdout_file else None

                stderr_f = open(
                    stderr_file, stderr_mode) if stderr_file else None

                # BACKGROUND PROCESS
                if background:

                    job_number = get_next_job_number()

                    process = subprocess.Popen(
                        [program] + args[1:],
                        executable=exe_path,
                        stdout=stdout_f,
                        stderr=stderr_f
                    )

                    print(f"[{job_number}] {process.pid}")

                    JOBS.append({
                        "id": job_number,
                        "pid": process.pid,
                        "process": process,
                        "command": original_command
                    })

                # FOREGROUND PROCESS
                else:
                    subprocess.run(
                        [program] + args[1:],
                        executable=exe_path,
                        stdout=stdout_f,
                        stderr=stderr_f
                    )

                if stdout_f:
                    stdout_f.close()

                if stderr_f:
                    stderr_f.close()

            except Exception as e:
                print(f"Error running {program}: {e}")


if __name__ == "__main__":
    main()
