import sys
import os
import subprocess


def main():
    builtins = ["echo", "exit", "type", "pwd"]

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        command_line = input().strip()
        if not command_line:
            continue

        args = command_line.split()
        program = args[0]

        # Handle builtins
        if program == "exit":
            break
        elif program == "echo":
            print(" ".join(args[1:]))
        elif program == "type":
            cmd_name = args[1] if len(args) > 1 else ""
            if cmd_name in builtins:
                print(f"{cmd_name} is a shell builtin")
            else:
                # Search PATH
                paths = os.environ.get("PATH", "").split(":")
                found = False
                for directory in paths:
                    full_path = os.path.join(directory, cmd_name)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        print(f"{cmd_name} is {full_path}")
                        found = True
                        break
                if not found:
                    print(f"{cmd_name}: not found")
        elif program == "pwd":
            print(os.getcwd())

        # External programs
        else:
            # Search PATH
            paths = os.environ.get("PATH", "").split(":")
            found = False
            for directory in paths:
                full_path = os.path.join(directory, program)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    found = True
                    try:
                        subprocess.run([program] + args[1:],
                                       executable=full_path)
                    except Exception as e:
                        print(f"Error running {program}: {e}")
                    break
            if not found:
                print(f"{program}: not found")


if __name__ == "__main__":
    main()
