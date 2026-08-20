#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 [-o outfile] [--add] [--dry] [--together] [--options \"...\"] <folder1> [<folder2> ...]"
    echo "  <folder>       : Directory containing subfolders with YODA files. One job per folder."
    echo "  --together     : (Optional) One job for all folders instead of one job per folder."
    echo "  --options \"...\": (Optional) Extra merge-script flags (default: none). Everything the"
    echo "                   merge script accepts goes here, e.g. \"--rm --quiet --chunked 10\"."
    echo "  -o outfile     : (Optional) Output filename (default: merges.txt)."
    echo "  --add          : (Optional) Append to existing outfile instead of overwriting."
    echo "  --dry          : (Optional) Show what would be written without writing it."
    echo "Every line is a complete yodamerge_runs.sh / rivet-merge_runs.sh command line."
    exit 1
fi

TOGETHER=false
OPTIONS=""
OUTFILE="merges.txt"
APPEND=false
DRY=false
POSITIONAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        --rm|-q|--quiet|--chunked|--chunked=*)
            echo "ERROR: $1 is no longer a separate option. Pass it through --options instead," >&2
            echo "       e.g. --options \"--rm --quiet --chunked 10\"." >&2
            exit 1 ;;
        --together)
            TOGETHER=true; shift ;;
        --options)
            shift
            if [ -z "${1-}" ]; then echo "--options requires an argument" >&2; exit 1; fi
            OPTIONS="$1"; shift ;;
        -o)
            shift
            if [ -z "${1-}" ]; then echo "-o requires an argument" >&2; exit 1; fi
            OUTFILE="$1"; shift ;;
        --add)
            APPEND=true; shift ;;
        --dry)
            DRY=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}"

if [ $# -lt 1 ]; then
    echo "ERROR: no folder given." >&2
    exit 1
fi

FOLDERS=()
for folder in "$@"; do
    if [ ! -d "$folder" ]; then
        echo "ERROR: Directory not found: $folder" >&2
        exit 1
    fi
    if [[ "$folder" =~ ^[0-9]+$ ]]; then
        echo "ERROR: '$folder' is a bare number. The merge scripts read a trailing number as the" >&2
        echo "       job count, so such a folder name cannot be passed. Rename it or use ./$folder." >&2
        exit 1
    fi
    FOLDERS+=("${folder%/}")
done

check_options() {
    local opt prev="" trailing=""
    for opt in $OPTIONS; do
        case "$prev" in
            --chunked|--nmax|-o|--output)
                prev="$opt"; continue ;;
        esac
        case "$opt" in
            -*) ;;
            *)  trailing="$opt" ;;
        esac
        prev="$opt"
    done
    if [[ -n "$trailing" && "$trailing" =~ ^[0-9]+$ ]]; then
        echo "ERROR: --options contains the bare number '$trailing', which the merge scripts read as" >&2
        echo "       the job count. Set the job count with NPROC at submit time instead." >&2
        exit 1
    fi
}
check_options

initial_merges=0
if [ "$APPEND" = true ] && [ -f "$OUTFILE" ]; then
    initial_merges=$(wc -l < "$OUTFILE")
fi

if [ "$DRY" = false ] && [ "$APPEND" = false ] && [ -f "$OUTFILE" ]; then
    rm "$OUTFILE"
fi

if [ "$DRY" = false ]; then
    mkdir -p condor_output
fi

dry_count=0
emit_merge() {
    if [ "$DRY" = true ]; then
        dry_count=$((dry_count + 1))
        echo "Would list: $1"
    else
        printf '%s\n' "$1" >> "$OUTFILE"
    fi
}

echo "Listing merges for ${#FOLDERS[@]} folder$([ ${#FOLDERS[@]} -eq 1 ] && echo "" || echo s)..."
if [ "$TOGETHER" = true ]; then
    emit_merge "${OPTIONS:+$OPTIONS }${FOLDERS[*]}"
    echo "Listed 1 merge for all ${#FOLDERS[@]} folders"
else
    for folder in "${FOLDERS[@]}"; do
        emit_merge "${OPTIONS:+$OPTIONS }$folder"
    done
    echo "Listed ${#FOLDERS[@]} merge$([ ${#FOLDERS[@]} -eq 1 ] && echo "" || echo s) (${FOLDERS[*]})"
fi

if [ "$DRY" = true ]; then
    echo "Dry run: nothing was written to $OUTFILE."
    echo "Total number of merges: $dry_count"
    echo ""
    echo "Submit with:"
    echo "  [NPROC=N] condor_submit ~/sherpa-on-the-rocks/merge/rivet-merge.jdf   (or merge/yodamerge.jdf)"
elif [ -f "$OUTFILE" ]; then
    echo "Done! Results written to $OUTFILE."
    total_merges=$(wc -l < "$OUTFILE")
    if [ "$APPEND" = true ]; then
        added_merges=$((total_merges - initial_merges))
        if [ "$added_merges" -lt 0 ]; then
            added_merges=0
        fi
        echo "Added $added_merges merges."
    fi
    echo "Total number of merges: $total_merges"
    echo ""
    echo "Submit with:"
    echo "  [NPROC=N] condor_submit ~/sherpa-on-the-rocks/merge/rivet-merge.jdf   (or merge/yodamerge.jdf)"
else
    echo "No $OUTFILE found."
fi
