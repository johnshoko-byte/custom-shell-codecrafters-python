import sys
import os
import shlex
import subprocess
import readline

EXECUTABLES = set()

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

    if not parts:
        return None

    token = parts[-1]

    # ---------------- COMMAND COMPLETION ----------------
    if len(parts) == 1 and not buffer.endswith(" "):
        builtins = ["echo", "exit", "type", "pwd", "cd", "jobs"]

        matches = sorted(
            cmd for cmd in (builtins + list(EXECUTABLES))
            if cmd.startswith(text)
        )

        if not matches:
            sys.stdout.write("\a")
            sys.stdout.flush()
            return None

        if state < len(matches):
            return matches[state] + " "
        return None

    # ---------------- FILE / DIRECTORY COMPLETION ----------------
    if "/" in token:
        search_dir, prefix = token.rsplit("/", 1)
        if search_dir == "":
            search_dir = "."
    else:
        search_dir = "."
        prefix = token

    try:
        entries = sorted(os.listdir(search_dir))
    except FileNotFoundError:
        sys.stdout.write("\a")
        sys.stdout.flush()
        return None

    matches = [e for e in entries if e.startswith(prefix)]

    if not matches:
        sys.stdout.write("\a")
        sys.stdout.flush()
        return None

    if state >= len(matches):
        return None

    match = matches[state]

    # ---------------- FIX: IMPORTANT PART ----------------
    if search_dir == ".":
        completed = match
    else:
        completed = search_dir + "/" + match

    full_path = os.path.join(search_dir, match)

    if os.path.isdir(full_path):
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


def get_next_job_number():

    used_numbers = sorted(job["id"] for job in JOBS)

    job_number = 1

    for number in used_numbers:

        if number == job_number:
            job_number += 1
        else:
            break

    return job_number


def reap_jobs():

    jobs_to_remove = []

    total_jobs = len(JOBS)

    for index, job in enumerate(JOBS):

        if job["process"].poll() is not None:

            if index == total_jobs - 1:
                marker = "+"
            elif index == total_jobs - 2:
                marker = "-"
            else:
                marker = " "

            command = job["command"].rstrip()

            if command.endswith("&"):
                command = command[:-1].rstrip()

            print(
                f"[{job['id']}]{marker}  "
                f"{'Done':<24}"
                f"{command}"
            )

            jobs_to_remove.append(job)

    for job in jobs_to_remove:
        JOBS.remove(job)


def main():

    builtins = ["echo", "exit", "type", "pwd", "cd", "jobs"]

    setup_autocomplete()

    while True:

        try:
            reap_jobs()
            command_line = input("$ ")

        except EOFError:
            break

        if not command_line:
            continue

        background = False

        if command_line.rstrip().endswith("&"):
            background = True

        args, stdout_file, stderr_file, append_stdout, append_stderr = parse_redirection(
            command_line
        )

        if not args:
            continue

        if args[-1] == "&":
            args.pop()

        program = args[0]

        # ---------------- BUILTINS ----------------

        if program == "exit":
            break

        elif program == "echo":

            output = " ".join(args[1:])

            write_output(output, stdout_file,
                         stderr_file, append_stdout)

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

            write_output(output, stdout_file,
                         stderr_file, append_stdout)

        elif program == "cd":

            target = os.path.expanduser(
                args[1]
            ) if len(args) > 1 else os.path.expanduser("~")

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

                if job["process"].poll() is None:
                    status = "Running"
                    command = job["command"]

                else:
                    status = "Done"

                    command = job["command"].rstrip()

                    if command.endswith("&"):
                        command = command[:-1].rstrip()

                    jobs_to_remove.append(job)

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

            for job in jobs_to_remove:
                JOBS.remove(job)

        # ---------------- EXTERNAL COMMANDS ----------------

        else:

            exe_path = find_executable(program)

            if not exe_path:
                print(f"{program}: not found")
                continue

            try:

                stdout_mode = 'a' if append_stdout else 'w'
                stderr_mode = 'a' if append_stderr else 'w'

                stdout_f = open(
                    stdout_file, stdout_mode
                ) if stdout_file else None

                stderr_f = open(
                    stderr_file, stderr_mode
                ) if stderr_file else None

                # ---------- BACKGROUND ----------

                if background:

                    job_number = get_next_job_number()

                    process = subprocess.Popen(
                        [program] + args[1:],
                        executable=exe_path,
                        stdout=stdout_f,
                        stderr=stderr_f
                    )

                    JOBS.append({
                        "id": job_number,
                        "pid": process.pid,
                        "process": process,
                        "command": command_line
                    })

                    print(f"[{job_number}] {process.pid}")

                # ---------- FOREGROUND ----------

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
