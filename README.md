# SomnoStar Sleep Study Transfer Utility

**By Adam J. Girardo**

A manually initiated Windows XP / Python 2.7 console utility for transferring completed sleep-study folders from an acquisition workstation to a network share, verifying the copy, and archiving the local original.

## Requirements

- Windows XP workstation with Python 2.7 at `C:\Python27\python.exe`
- Access to the destination SMB share and sufficient permissions to create folders and files
- A completed SomnoStar study containing `Patient.dat`

## Configuration

Configure the destination and, if necessary, source and backup using environment variables before running the launcher:

```bat
set SOMNOSTAR_SOURCE=C:\D
set SOMNOSTAR_BACKUP=C:\D\backup
set SOMNOSTAR_DESTINATION=\\YOUR-SERVER\YOUR-SHARE
RUN_TRANSFER.bat
```

The default destination is a placeholder and **must be configured** before use. These values may also be set as Windows system environment variables.

## Workflow

1. Finds the most recently modified qualifying study in the source directory, excluding the backup directory.
2. Requires a `Patient.dat` file, study size greater than 33 MiB, and at least 120 seconds since the newest study file modification.
3. Shows study information and requests the operator type `TRANSFER`.
4. Copies to a new uniquely named destination folder and displays progress, throughput, and ETA.
5. Verifies file names and sizes, source stability, and `SIGNAL.raw` SHA-256 where present.
6. Writes a transfer audit marker, then moves the original study into the local backup directory and verifies it.

The utility does **not** intentionally delete study files. On failure, it can leave a partial destination folder; inspect it before retrying.

## Privacy and security

This utility processes protected health information (PHI), including identifiers read from `Patient.dat`, and may write patient identifiers into transfer audit markers. Run it only on authorized systems and protected network shares, following your organization's security and retention requirements. Do not commit real study folders, `Patient.dat`, logs, audit markers, or patient screenshots to this repository.

The decoder is specific to the study format tested during development. Do not assume compatibility with other systems.

## Status

Source release candidate derived from the tested production package. Review configuration and validate in your own environment before deployment. No warranty or regulatory certification is implied.