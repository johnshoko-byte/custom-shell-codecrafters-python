#  Custom Shell (Python)

A POSIX-like shell built from scratch in Python as part of the Codecrafters "Build Your Own Shell" challenge.

This project simulates a real Unix shell, including command execution, built-in commands, and advanced tab completion behavior.

---

##  Features

- Execute external programs using `PATH`
- Built-in commands:
  - `cd`
  - `pwd`
  - `echo`
  - `type`
  - `exit`
- File and directory tab completion
- Nested path completion (e.g. `dir/subdir/file`)
- Multiple match handling with tab completion UI
- Bell feedback (`\x07`) for invalid or ambiguous input
- Basic output redirection support (`>`, `>>`, `2>`, `2>>`)

---

## Example Usage

```bash
$ echo hello world
hello world

$ pwd
/home/user

$ cd project/

$ ls doc<TAB>
$ ls documents/