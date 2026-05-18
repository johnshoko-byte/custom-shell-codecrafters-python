import sys
import os
import shlex
import subprocess
import readline

EXECUTABLES = set()
TAB_COUNT = 0
LAST_BUFFER = ""
MULTI_MATCH_READY = False
JOBS = []


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
    buffer = readline.get_line_buffer()
    parts = buffer.split()

    # ---------------- COMMAND COMPLETION ----------------
    if len(parts) <= 1 and not buffer.endswith(" "):
        builtins = ["echo", "exit"]
        executables = EXECUTABLES or []

        matches = sorted(
            cmd for cmd in (builtins + list(executables))
            if cmd.startswith(text)
        )

        if not matches:
            sys.stdout.write("\x07")
            sys.stdout.flush()
            return None

        if state < len(matches):
            return matches[state] + " "
        return None

    # ---------------- FILE / DIRECTORY COMPLETION ----------------
    token = text

    # CASE 1: token ends with /
    # example: pig/
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

    # rebuild proper completed path
    if search_dir == ".":
        completed = match
    else:
        completed = os.path.join(search_dir, match)

    full_match_path = os.path.join(search_dir, match)

    # directory
    if os.path.isdir(full_match_path):
        return completed + "/"

    # file
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


def main():
    builtins = ["echo", "exit", "type", "pwd", "cd", "jobs"]

    setup_autocomplete()

    while True:
        try:
            reap_jobs()
            command_line = input("$ ")

            original_command = command_line

        except EOFError:
            break

        if not command_line:
            continue

        args, stdout_file, stderr_file, append_stdout, append_stderr = parse_redirection(
            command_line
        )

        if not args:
            continue

        background = False

        if args[-1] == "&":
            background = True
            args = args[:-1]

            if not args:
                continue
        # ---------------- PIPELINES ----------------
        if "|" in args:

            pipe_index = args.index("|")

            left_cmd = args[:pipe_index]
            right_cmd = args[pipe_index + 1:]

            if not left_cmd or not right_cmd:
                print("Invalid pipeline")
                continue

            left_program = left_cmd[0]
            right_program = right_cmd[0]

            left_exe = find_executable(left_program)
            right_exe = find_executable(right_program)

            if not left_exe:
                print(f"{left_program}: not found")
                continue

            if not right_exe:
                print(f"{right_program}: not found")
                continue

            try:

                p1 = subprocess.Popen(
                    left_cmd,
                    executable=left_exe,
                    stdout=subprocess.PIPE
                )

                p2 = subprocess.Popen(
                    right_cmd,
                    executable=right_exe,
                    stdin=p1.stdout
                )

                p1.stdout.close()

                p2.communicate()
                p1.wait()

            except Exception as e:
                print(f"Pipeline error: {e}")

            continue

        program = args[0]

        if program == "exit":
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
